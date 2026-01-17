"""
Bronze Layer Ingestion Helpers for Alur Framework.

Provides utilities for loading raw data into Bronze tables with standard metadata.
Bronze layer philosophy: Raw data as-is + metadata. NO transformations.
"""

from typing import Optional, List, Dict, Any, Callable
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import StructType, TimestampType, StringType
from datetime import datetime
import os


def add_bronze_metadata(
    df: DataFrame,
    source_system: Optional[str] = None,
    source_file: Optional[str] = None,
    exclude: Optional[List[str]] = None,
    custom_metadata: Optional[Dict[str, Any]] = None
) -> DataFrame:
    """
    Add standard Bronze layer metadata columns to a DataFrame.

    Bronze metadata pattern:
    - _ingested_at: Timestamp when data was ingested
    - _source_system: Name of source system (e.g., 'sales_db', 'api', 'sftp')
    - _source_file: Original file name or identifier
    - Custom metadata: Any additional tracking fields

    Args:
        df: Input DataFrame to add metadata to
        source_system: Name of the source system
        source_file: Source file name or identifier
        exclude: List of metadata columns to exclude (e.g., ['_source_file', '_ingested_at'])
        custom_metadata: Dictionary of custom metadata columns to add

    Returns:
        DataFrame with metadata columns added

    Example:
        >>> raw_df = spark.read.csv("s3://landing/orders.csv", header=True)
        >>> bronze_df = add_bronze_metadata(
        ...     raw_df,
        ...     source_system="sales_db",
        ...     source_file="orders_2024_01_15.csv"
        ... )
        >>> # Result has: _ingested_at, _source_system, _source_file columns
        >>>
        >>> # Exclude specific metadata columns
        >>> bronze_df = add_bronze_metadata(
        ...     api_df,
        ...     source_system="payments_api",
        ...     exclude=["_source_file"]  # Not applicable for API data
        ... )
    """
    result_df = df
    exclude = exclude or []

    # Add ingestion timestamp
    if "_ingested_at" not in exclude:
        result_df = result_df.withColumn(
            "_ingested_at",
            F.current_timestamp()
        )

    # Add source system
    if "_source_system" not in exclude and source_system:
        result_df = result_df.withColumn(
            "_source_system",
            F.lit(source_system)
        )

    # Add source file
    if "_source_file" not in exclude and source_file:
        result_df = result_df.withColumn(
            "_source_file",
            F.lit(source_file)
        )

    # Add custom metadata columns
    if custom_metadata:
        for col_name, col_value in custom_metadata.items():
            result_df = result_df.withColumn(col_name, F.lit(col_value))

    return result_df


def _merge_options(default_options: Dict[str, str], user_options: Optional[Dict[str, str]]) -> Dict[str, str]:
    """Helper to merge default and user options."""
    return {**default_options, **(user_options or {})}


def _detect_format(source_path: str) -> str:
    """Auto-detect file format from path extension."""
    path_lower = source_path.lower()
    if path_lower.endswith('.csv') or '*.csv' in path_lower:
        return 'csv'
    elif path_lower.endswith('.json') or '*.json' in path_lower:
        return 'json'
    elif path_lower.endswith('.parquet') or '*.parquet' in path_lower:
        return 'parquet'
    else:
        raise ValueError(
            f"Cannot auto-detect format from path: {source_path}. "
            "Please specify format explicitly using format='csv'|'json'|'parquet'"
        )


def load_to_bronze(
    spark: SparkSession,
    source_path: str,
    source_system: str,
    format: Optional[str] = None,
    options: Optional[Dict[str, str]] = None,
    schema: Optional[StructType] = None,
    exclude_metadata: Optional[List[str]] = None,
    custom_metadata: Optional[Dict[str, Any]] = None
) -> DataFrame:
    """
    Load files into Bronze layer with standard metadata.

    Supports CSV, JSON, and Parquet formats with automatic format detection.

    Args:
        spark: SparkSession instance
        source_path: S3 or local path to file(s). Supports wildcards (*.csv, *.json, etc.)
        source_system: Name of source system for metadata
        format: File format ('csv', 'json', 'parquet'). Auto-detected from path if not provided.
        options: Format-specific reader options (e.g., header, delimiter for CSV)
        schema: Optional schema for reading (not applicable to Parquet)
        exclude_metadata: List of metadata columns to exclude (e.g., ['_source_file'])
        custom_metadata: Dictionary of custom metadata columns to add

    Returns:
        DataFrame ready for Bronze layer with metadata

    Examples:
        >>> # CSV with auto-detection
        >>> df = load_to_bronze(
        ...     spark,
        ...     source_path="s3://landing/orders/*.csv",
        ...     source_system="sales_db"
        ... )
        >>>
        >>> # JSON with explicit format and options
        >>> df = load_to_bronze(
        ...     spark,
        ...     source_path="s3://landing/events.json",
        ...     source_system="event_api",
        ...     format="json",
        ...     options={"multiLine": "true"}
        ... )
        >>>
        >>> # With custom metadata and exclusions
        >>> df = load_to_bronze(
        ...     spark,
        ...     source_path="s3://landing/exports/*.parquet",
        ...     source_system="data_export",
        ...     exclude_metadata=["_source_file"],
        ...     custom_metadata={"_batch_id": "batch_001"}
        ... )
    """
    # Auto-detect format if not specified
    file_format = format.lower() if format else _detect_format(source_path)

    # Format-specific loading
    if file_format == 'csv':
        default_options = {
            "header": "true",
            "inferSchema": "true",
            "mode": "PERMISSIVE"
        }
        merged_options = _merge_options(default_options, options)
        reader = spark.read.options(**merged_options)
        if schema:
            reader = reader.schema(schema)
        df = reader.csv(source_path)

    elif file_format == 'json':
        default_options = {
            "mode": "PERMISSIVE",
        }
        merged_options = _merge_options(default_options, options)
        reader = spark.read.options(**merged_options)
        if schema:
            reader = reader.schema(schema)
        df = reader.json(source_path)

    elif file_format == 'parquet':
        df = spark.read.parquet(source_path)

    else:
        raise ValueError(
            f"Unsupported format: {file_format}. "
            "Supported formats: 'csv', 'json', 'parquet'"
        )

    # Add metadata
    source_file = os.path.basename(source_path)
    df = add_bronze_metadata(
        df,
        source_system=source_system,
        source_file=source_file,
        exclude=exclude_metadata,
        custom_metadata=custom_metadata
    )

    return df


def handle_bad_records(
    df: DataFrame,
    bad_records_path: Optional[str] = None,
    filter_corrupted: bool = True
) -> DataFrame:
    """
    Handle bad/corrupted records in Bronze ingestion.

    When reading with mode=PERMISSIVE, Spark adds a _corrupt_record column
    for malformed data. This helper filters or separates bad records.

    Args:
        df: DataFrame that may contain _corrupt_record column
        bad_records_path: Optional path to save bad records
        filter_corrupted: If True, filter out bad records. If False, keep all.

    Returns:
        DataFrame with bad records handled

    Example:
        >>> raw_df = spark.read.csv("data.csv", mode="PERMISSIVE")
        >>> clean_df = handle_bad_records(
        ...     raw_df,
        ...     bad_records_path="s3://errors/bad_records/"
        ... )
    """
    # Check if _corrupt_record column exists
    if "_corrupt_record" not in df.columns:
        return df

    # Save bad records if path provided
    if bad_records_path:
        bad_records = df.filter(F.col("_corrupt_record").isNotNull())
        if bad_records.count() > 0:
            bad_records.write.mode("append").parquet(bad_records_path)

    # Filter out bad records if requested
    if filter_corrupted:
        df = df.filter(F.col("_corrupt_record").isNull())
        df = df.drop("_corrupt_record")

    return df


class IncrementalLoader:
    """
    Helper for incremental loading into Bronze tables.

    Tracks the last processed file/timestamp to avoid reprocessing data.
    This is useful for daily/hourly file drops where you only want new data.
    """

    def __init__(
        self,
        spark: SparkSession,
        watermark_table: str = "bronze_watermarks",
        watermark_path: Optional[str] = None
    ):
        """
        Initialize incremental loader.

        Args:
            spark: SparkSession instance
            watermark_table: Table name to store watermarks
            watermark_path: Path to store watermark table (defaults to /tmp/watermarks)
        """
        self.spark = spark
        self.watermark_table = watermark_table
        self.watermark_path = watermark_path or "/tmp/alur/watermarks"

    def get_last_watermark(self, source_name: str) -> Optional[str]:
        """
        Get the last watermark for a source.

        Args:
            source_name: Name of the source (e.g., 'orders_csv')

        Returns:
            Last watermark value or None if no previous load
        """
        try:
            watermarks = self.spark.read.parquet(self.watermark_path)
            result = watermarks.filter(F.col("source_name") == source_name)

            if result.count() == 0:
                return None

            return result.select("watermark").first()["watermark"]
        except Exception:
            # Table doesn't exist yet
            return None

    def update_watermark(self, source_name: str, watermark_value: str) -> None:
        """
        Update the watermark for a source.

        Args:
            source_name: Name of the source
            watermark_value: New watermark value (filename, timestamp, etc.)
        """
        from pyspark.sql.types import StructType, StructField, StringType, TimestampType

        # Create new watermark record
        schema = StructType([
            StructField("source_name", StringType(), False),
            StructField("watermark", StringType(), False),
            StructField("updated_at", TimestampType(), False)
        ])

        new_record = self.spark.createDataFrame(
            [(source_name, watermark_value, datetime.now())],
            schema
        )

        # Read existing watermarks
        try:
            existing = self.spark.read.parquet(self.watermark_path)
            # Remove old watermark for this source
            existing = existing.filter(F.col("source_name") != source_name)
            # Append new watermark
            updated = existing.union(new_record)
        except Exception:
            # No existing watermarks
            updated = new_record

        # Write back
        updated.write.mode("overwrite").parquet(self.watermark_path)

    def load_new_files(
        self,
        source_path: str,
        source_name: str,
        loader_fn: Callable[[str], DataFrame],
        watermark_pattern: str = "filename"
    ) -> Optional[DataFrame]:
        """
        Load only new files since last watermark.

        Args:
            source_path: Path pattern to source files (e.g., s3://landing/*.csv)
            source_name: Unique name for this source
            loader_fn: Function to load a file (takes path, returns DataFrame)
            watermark_pattern: 'filename' or 'timestamp'

        Returns:
            DataFrame with new data, or None if no new files

        Example:
            >>> loader = IncrementalLoader(spark)
            >>> df = loader.load_new_files(
            ...     source_path="s3://landing/orders/*.csv",
            ...     source_name="orders_csv",
            ...     loader_fn=lambda path: load_to_bronze(spark, path, "sales_db")
            ... )
        """
        # Get last watermark
        last_watermark = self.get_last_watermark(source_name)

        # List files in source path
        try:
            files = self._list_files(source_path)
        except Exception as e:
            raise RuntimeError(f"Failed to list files at {source_path}: {e}")

        # Filter for new files
        if last_watermark:
            if watermark_pattern == "filename":
                new_files = [f for f in files if f > last_watermark]
            else:
                # For timestamp-based watermarking, implement comparison logic
                new_files = files
        else:
            new_files = files

        if not new_files:
            return None

        # Load all new files
        dfs = []
        for file_path in new_files:
            df = loader_fn(file_path)
            dfs.append(df)

        # Union all DataFrames
        if len(dfs) == 1:
            result_df = dfs[0]
        else:
            result_df = dfs[0]
            for df in dfs[1:]:
                result_df = result_df.union(df)

        # Update watermark to latest file
        latest_file = max(new_files)
        self.update_watermark(source_name, latest_file)

        return result_df

    def _list_files(self, path_pattern: str) -> List[str]:
        """List files matching pattern."""
        # This is a simplified implementation
        # In production, use proper S3 listing or Hadoop FileSystem API

        if path_pattern.startswith("s3://"):
            # Use Spark to list S3 files
            # Note: This requires proper S3 credentials configured
            hadoop_conf = self.spark.sparkContext._jsc.hadoopConfiguration()
            fs = self.spark.sparkContext._jvm.org.apache.hadoop.fs.FileSystem.get(
                self.spark.sparkContext._jvm.java.net.URI(path_pattern.split('*')[0]),
                hadoop_conf
            )
            # Simplified - in production implement full S3 listing
            return []
        else:
            # Local filesystem
            import glob
            return sorted(glob.glob(path_pattern))


__all__ = [
    # Metadata helpers
    "add_bronze_metadata",
    # Unified file loader
    "load_to_bronze",
    # Bad records handling
    "handle_bad_records",
    # Incremental loading
    "IncrementalLoader",
]
