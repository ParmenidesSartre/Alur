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
    add_ingestion_timestamp: bool = True,
    add_source_system: bool = True,
    add_source_file: bool = True,
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
        add_ingestion_timestamp: Add _ingested_at timestamp column
        add_source_system: Add _source_system column
        add_source_file: Add _source_file column
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
    """
    result_df = df

    # Add ingestion timestamp
    if add_ingestion_timestamp:
        result_df = result_df.withColumn(
            "_ingested_at",
            F.current_timestamp()
        )

    # Add source system
    if add_source_system and source_system:
        result_df = result_df.withColumn(
            "_source_system",
            F.lit(source_system)
        )

    # Add source file
    if add_source_file and source_file:
        result_df = result_df.withColumn(
            "_source_file",
            F.lit(source_file)
        )

    # Add custom metadata columns
    if custom_metadata:
        for col_name, col_value in custom_metadata.items():
            result_df = result_df.withColumn(col_name, F.lit(col_value))

    return result_df


def load_csv_to_bronze(
    spark: SparkSession,
    source_path: str,
    source_system: str,
    options: Optional[Dict[str, str]] = None,
    schema: Optional[StructType] = None,
    add_metadata: bool = True
) -> DataFrame:
    """
    Load CSV files into Bronze layer with standard metadata.

    Args:
        spark: SparkSession instance
        source_path: S3 or local path to CSV file(s). Supports wildcards (*.csv)
        source_system: Name of source system for metadata
        options: CSV reader options (header, delimiter, etc.)
        schema: Optional schema for CSV reading
        add_metadata: Whether to add Bronze metadata columns

    Returns:
        DataFrame ready for Bronze layer with metadata

    Example:
        >>> df = load_csv_to_bronze(
        ...     spark,
        ...     source_path="s3://landing/orders/*.csv",
        ...     source_system="sales_db",
        ...     options={"header": "true", "inferSchema": "true"}
        ... )
    """
    # Default CSV options
    default_options = {
        "header": "true",
        "inferSchema": "true",
        "mode": "PERMISSIVE"  # Handle bad records
    }

    # Merge with user options
    csv_options = {**default_options, **(options or {})}

    # Read CSV
    reader = spark.read.options(**csv_options)

    if schema:
        reader = reader.schema(schema)

    df = reader.csv(source_path)

    # Add metadata
    if add_metadata:
        # Extract filename from path for metadata
        source_file = os.path.basename(source_path)
        df = add_bronze_metadata(
            df,
            source_system=source_system,
            source_file=source_file
        )

    return df


def load_json_to_bronze(
    spark: SparkSession,
    source_path: str,
    source_system: str,
    options: Optional[Dict[str, str]] = None,
    schema: Optional[StructType] = None,
    add_metadata: bool = True,
    multiline: bool = False
) -> DataFrame:
    """
    Load JSON files into Bronze layer with standard metadata.

    Args:
        spark: SparkSession instance
        source_path: S3 or local path to JSON file(s). Supports wildcards (*.json)
        source_system: Name of source system for metadata
        options: JSON reader options
        schema: Optional schema for JSON reading
        add_metadata: Whether to add Bronze metadata columns
        multiline: Whether JSON files are multiline format

    Returns:
        DataFrame ready for Bronze layer with metadata

    Example:
        >>> df = load_json_to_bronze(
        ...     spark,
        ...     source_path="s3://landing/events/*.json",
        ...     source_system="event_api",
        ...     multiline=True
        ... )
    """
    # Default JSON options
    default_options = {
        "mode": "PERMISSIVE",
        "multiLine": "true" if multiline else "false"
    }

    # Merge with user options
    json_options = {**default_options, **(options or {})}

    # Read JSON
    reader = spark.read.options(**json_options)

    if schema:
        reader = reader.schema(schema)

    df = reader.json(source_path)

    # Add metadata
    if add_metadata:
        source_file = os.path.basename(source_path)
        df = add_bronze_metadata(
            df,
            source_system=source_system,
            source_file=source_file
        )

    return df


def load_parquet_to_bronze(
    spark: SparkSession,
    source_path: str,
    source_system: str,
    add_metadata: bool = True
) -> DataFrame:
    """
    Load Parquet files into Bronze layer with standard metadata.

    Args:
        spark: SparkSession instance
        source_path: S3 or local path to Parquet file(s)
        source_system: Name of source system for metadata
        add_metadata: Whether to add Bronze metadata columns

    Returns:
        DataFrame ready for Bronze layer with metadata

    Example:
        >>> df = load_parquet_to_bronze(
        ...     spark,
        ...     source_path="s3://landing/exports/*.parquet",
        ...     source_system="data_export"
        ... )
    """
    df = spark.read.parquet(source_path)

    # Add metadata
    if add_metadata:
        source_file = os.path.basename(source_path)
        df = add_bronze_metadata(
            df,
            source_system=source_system,
            source_file=source_file
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
            ...     loader_fn=lambda path: load_csv_to_bronze(spark, path, "sales_db")
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
    # File loaders
    "load_csv_to_bronze",
    "load_json_to_bronze",
    "load_parquet_to_bronze",
    # Bad records handling
    "handle_bad_records",
    # Incremental loading
    "IncrementalLoader",
]
