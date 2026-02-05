"""
Bronze Layer Ingestion for Alur Framework.

Simplified design using AWS Glue native features:
- Glue Job Bookmarks for idempotency (no DynamoDB needed)
- S3 for data storage
- Contract-driven schema validation

Glue Job Bookmarks automatically track which files have been processed.
No custom state management required.
"""

from typing import Optional, List, Dict, Any, Type, Union
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import StructType
import logging
import time

from alur.utils.aws_helpers import AWSClientFactory, S3Path
from alur.utils.spark_helpers import create_empty_dataframe, add_metadata_columns

logger = logging.getLogger(__name__)


class SchemaValidationError(Exception):
    """Raised when schema validation fails during bronze ingestion."""
    pass


def add_bronze_metadata(
    df: DataFrame,
    source_system: Optional[str] = None,
    source_file: Optional[str] = None,
    exclude: Optional[List[str]] = None,
    custom_metadata: Optional[Dict[str, Any]] = None
) -> DataFrame:
    """
    Add standard Bronze layer metadata columns to a DataFrame.

    Args:
        df: Input DataFrame
        source_system: Name of source system
        source_file: Source file path (auto-detected if None)
        exclude: Metadata columns to exclude
        custom_metadata: Additional metadata columns

    Returns:
        DataFrame with bronze metadata columns
    """
    exclude = exclude or []
    metadata_cols = {}

    if "_ingested_at" not in exclude:
        metadata_cols["_ingested_at"] = F.current_timestamp()

    if "_source_system" not in exclude and source_system:
        metadata_cols["_source_system"] = F.lit(source_system)

    if "_source_file" not in exclude:
        if source_file:
            metadata_cols["_source_file"] = F.lit(source_file)
        elif "_source_file" not in df.columns:
            metadata_cols["_source_file"] = F.input_file_name()

    if custom_metadata:
        for col_name, col_value in custom_metadata.items():
            if col_name not in exclude:
                metadata_cols[col_name] = F.lit(col_value)

    return add_metadata_columns(df, metadata_cols)


def validate_schema(
    df: DataFrame,
    target: Type,
    strict_mode: bool = True
) -> None:
    """
    Validate DataFrame schema against a table contract.

    Args:
        df: DataFrame to validate
        target: Target table class
        strict_mode: Fail on errors (True) or warn only (False)
    """
    if not hasattr(target, '_fields'):
        raise ValueError(f"{target.__name__} is not a valid table contract")

    expected_fields = target._fields
    df_columns = set(df.columns)
    expected_columns = set(expected_fields.keys())

    # Exclude metadata columns from validation
    metadata_cols = {'_ingested_at', '_source_system', '_source_file'}
    expected_columns = {c for c in expected_columns if c not in metadata_cols}
    df_columns = {c for c in df_columns if c not in metadata_cols}

    errors = []

    # Check for missing required columns
    missing = expected_columns - df_columns
    for col in sorted(missing):
        field = expected_fields[col]
        if not field.nullable:
            errors.append(f"Missing required column: {col}")

    # Check for type mismatches
    df_schema = {f.name: f.dataType for f in df.schema.fields}
    for col in expected_columns.intersection(df_columns):
        expected_type = expected_fields[col].to_spark_type()
        actual_type = df_schema.get(col)
        if actual_type and str(expected_type) != str(actual_type):
            msg = f"Type mismatch '{col}': expected {expected_type}, got {actual_type}"
            if strict_mode:
                errors.append(msg)
            else:
                logger.warning(msg)

    if errors:
        raise SchemaValidationError("Validation failed:\n" + "\n".join(errors))


def load_to_bronze(
    spark: SparkSession,
    source_path: Union[str, List[str]],
    source_system: str,
    target: Optional[Type] = None,
    options: Optional[Dict[str, str]] = None,
    schema: Optional[StructType] = None,
    custom_metadata: Optional[Dict[str, Any]] = None,
    validate: bool = True,
    strict_mode: bool = True
) -> DataFrame:
    """
    Load CSV files into Bronze layer with schema validation.

    Idempotency is handled by AWS Glue Job Bookmarks (built-in).
    Configure your Glue job with job bookmarks enabled for automatic
    file tracking - no custom state management needed.

    Args:
        spark: SparkSession
        source_path: S3 path(s) to CSV files
            - Single: "s3://bucket/path/*.csv"
            - Multiple: ["s3://bucket/a/*.csv", "s3://bucket/b/*.csv"]
        source_system: Name of source system for metadata
        target: Target BronzeTable class for schema validation
        options: Spark CSV read options
        schema: Explicit Spark schema (overrides target schema)
        custom_metadata: Additional metadata columns
        validate: Enable schema validation
        strict_mode: Fail on validation errors (True) or warn (False)

    Returns:
        DataFrame with bronze metadata

    Example:
        df = load_to_bronze(
            spark,
            source_path="s3://landing/orders/*.csv",
            source_system="sales_db",
            target=OrdersBronze
        )

    Note:
        For idempotency, enable Glue Job Bookmarks in your job configuration.
        This automatically tracks processed files without any custom code.
    """
    start_time = time.time()

    # Normalize source paths
    source_paths = [source_path] if isinstance(source_path, str) else source_path

    # Validate paths are S3 CSV
    for path in source_paths:
        if not path.lower().startswith("s3://"):
            raise ValueError(f"Only S3 paths supported: {path}")
        if not (".csv" in path.lower()):
            raise ValueError(f"Only CSV files supported: {path}")

    logger.info(f"Loading from {len(source_paths)} source path(s)")

    # Determine schema
    read_schema = schema
    if target and not read_schema:
        full_schema = target.to_iceberg_schema()
        # Filter out metadata columns
        clean_fields = [f for f in full_schema.fields if not f.name.startswith('_')]
        read_schema = StructType(clean_fields)
        logger.info(f"Using schema from {target.__name__}")

    # Configure CSV reader
    default_options = {
        "header": "true",
        "mode": "PERMISSIVE",
        "inferSchema": "false" if read_schema else "true"
    }
    merged_options = {**default_options, **(options or {})}

    # Read data
    reader = spark.read.options(**merged_options)
    if read_schema:
        reader = reader.schema(read_schema)

    if len(source_paths) == 1:
        df = reader.csv(source_paths[0])
    else:
        df = reader.csv(source_paths)

    row_count = df.count()
    logger.info(f"Read {row_count} rows")

    if row_count == 0:
        logger.info("No data to process")
        return create_empty_dataframe(spark, target=target)

    # Add metadata
    df = add_bronze_metadata(
        df,
        source_system=source_system,
        custom_metadata=custom_metadata
    )

    # Validate schema
    if target and validate:
        validate_schema(df, target=target, strict_mode=strict_mode)

    duration = time.time() - start_time
    logger.info(f"Bronze ingestion complete: {row_count} rows in {duration:.2f}s")

    return df


__all__ = [
    "add_bronze_metadata",
    "load_to_bronze",
    "validate_schema",
    "SchemaValidationError",
]
