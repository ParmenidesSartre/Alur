"""
Bronze Layer Ingestion Helpers for Alur Framework.

Provides utilities for loading raw data into Bronze tables with standard metadata.
Bronze layer philosophy: Raw data as-is + metadata. NO transformations.

Batch-only mode:
- CSV input only
- S3 paths only (s3://bucket/prefix/*.csv)
"""

from typing import Optional, List, Dict, Any, Callable, Type
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import StructType, DataType
import boto3
import logging
import fnmatch
import time
from urllib.parse import urlparse

# Configure logging
logger = logging.getLogger(__name__)


class SchemaValidationError(Exception):
    """Raised when schema validation fails during bronze ingestion."""
    pass


def _list_s3_files(s3_path: str) -> List[Dict[str, Any]]:
    """
    Helper: List individual files from S3 to get metadata (ETag/LastModified).
    Supports wildcards (e.g., s3://bucket/folder/*.csv).
    """
    parsed = urlparse(s3_path)
    bucket = parsed.netloc
    prefix = parsed.path.lstrip('/')
    
    # Handle simple wildcards for prefix filtering
    search_prefix = prefix
    if '*' in prefix:
        search_prefix = prefix.split('*')[0]
    
    s3 = boto3.client('s3')
    paginator = s3.get_paginator('list_objects_v2')
    
    files = []
    try:
        for page in paginator.paginate(Bucket=bucket, Prefix=search_prefix):
            if 'Contents' not in page:
                continue
                
            for obj in page['Contents']:
                key = obj['Key']
                # Match the full pattern (e.g. *.csv)
                if not fnmatch.fnmatch(key, prefix):
                    continue
                # Skip 0 byte files or folders
                if obj['Size'] == 0 or key.endswith('/'):
                    continue
                    
                files.append({
                    'path': f"s3://{bucket}/{key}",
                    'key': key,
                    'last_modified': obj['LastModified'].isoformat(),
                    'size': obj['Size']
                })
    except Exception as e:
        logger.warning(f"Failed to list S3 files: {e}. Falling back to Spark wildcard read.")
        return [] # Return empty to trigger fallback

    return files


def add_bronze_metadata(
    df: DataFrame,
    source_system: Optional[str] = None,
    source_file: Optional[str] = None,
    exclude: Optional[List[str]] = None,
    custom_metadata: Optional[Dict[str, Any]] = None
) -> DataFrame:
    """
    Add standard Bronze layer metadata columns to a DataFrame.
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
    if "_source_file" not in exclude:
        if source_file:
            # Literal value provided
            result_df = result_df.withColumn("_source_file", F.lit(source_file))
        elif "_source_file" not in result_df.columns:
            # Auto-detect using Spark function (best for multi-file reads)
            result_df = result_df.withColumn("_source_file", F.input_file_name())

    # Add custom metadata columns
    if custom_metadata:
        for col_name, col_value in custom_metadata.items():
            result_df = result_df.withColumn(col_name, F.lit(col_value))

    return result_df


def _merge_options(default_options: Dict[str, str], user_options: Optional[Dict[str, str]]) -> Dict[str, str]:
    """Helper to merge default and user options."""
    return {**default_options, **(user_options or {})}


def _validate_csv_s3_source_path(source_path: str) -> None:
    path_lower = source_path.lower()
    if not path_lower.startswith("s3://"):
        raise ValueError(f"Only s3:// paths are supported in batch-only mode: {source_path}")
    if not (path_lower.endswith(".csv") or "*.csv" in path_lower):
        raise ValueError(f"Only CSV sources are supported in batch-only mode: {source_path}")


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
        # Default fallback or raise error
        if '*' not in path_lower:
             raise ValueError(f"Cannot auto-detect format from: {source_path}")
        return 'parquet' # Safe default


def _validate_csv_headers_from_s3(s3_path: str, target: Type) -> Dict[str, Any]:
    """
    Validate CSV headers against contract schema before reading data.

    Returns dict with:
        - is_valid: bool
        - missing_columns: list
        - extra_columns: list
        - error_message: str (if invalid)
    """
    import csv
    import io

    # Parse S3 path
    parsed = urlparse(s3_path)
    bucket = parsed.netloc
    key = parsed.path.lstrip('/')

    # Get expected columns from contract (exclude metadata columns)
    expected_fields = target._fields
    expected_columns = {col for col in expected_fields.keys() if not col.startswith('_')}

    # Read first line from S3 to get headers
    s3 = boto3.client('s3')
    try:
        # Read only first 1KB (headers should be in first line)
        response = s3.get_object(Bucket=bucket, Key=key, Range='bytes=0-1024')
        first_chunk = response['Body'].read().decode('utf-8')

        # Parse CSV header
        csv_reader = csv.reader(io.StringIO(first_chunk))
        headers = next(csv_reader)
        actual_columns = set(h.strip() for h in headers)

        # Check for missing and extra columns
        missing_columns = expected_columns - actual_columns
        extra_columns = actual_columns - expected_columns

        # Identify required vs optional missing columns
        required_missing = []
        optional_missing = []
        for col in missing_columns:
            field = expected_fields[col]
            if not field.nullable:
                required_missing.append(col)
            else:
                optional_missing.append(col)

        # Determine if valid
        is_valid = len(required_missing) == 0

        # Build error message if invalid
        error_message = None
        if not is_valid:
            parts = []
            if required_missing:
                parts.append(f"Missing required columns: {', '.join(sorted(required_missing))}")
            if extra_columns:
                parts.append(f"Unexpected columns: {', '.join(sorted(extra_columns))}")
            error_message = "; ".join(parts)

        return {
            'is_valid': is_valid,
            'missing_columns': list(missing_columns),
            'extra_columns': list(extra_columns),
            'required_missing': required_missing,
            'optional_missing': optional_missing,
            'error_message': error_message,
            'actual_headers': list(actual_columns),
            'expected_headers': list(expected_columns)
        }

    except Exception as e:
        logger.warning(f"Could not validate CSV headers for {s3_path}: {e}")
        # Return as valid to allow fallback to Spark validation
        return {
            'is_valid': True,
            'missing_columns': [],
            'extra_columns': [],
            'error_message': None,
            'validation_skipped': True,
            'skip_reason': str(e)
        }


def _get_spark_type_name(data_type: DataType) -> str:
    """Get a human-readable name for a Spark data type."""
    type_name = str(data_type)
    # Simplify common types
    if "StringType" in type_name: return "string"
    elif "IntegerType" in type_name: return "integer"
    elif "LongType" in type_name: return "long"
    elif "DoubleType" in type_name: return "double"
    elif "BooleanType" in type_name: return "boolean"
    elif "TimestampType" in type_name: return "timestamp"
    elif "DateType" in type_name: return "date"
    elif "DecimalType" in type_name: return "decimal"
    else: return type_name


def validate_schema(
    df: DataFrame,
    target: Type,
    strict_mode: bool = True,
    exclude_metadata: bool = False
) -> None:
    """
    Validate DataFrame schema against a table contract.
    """
    # Get expected schema from contract
    if not hasattr(target, '_fields'):
        raise ValueError(f"{target.__name__} is not a valid table contract")

    expected_fields = target._fields
    df_columns = set(df.columns)
    expected_columns = set(expected_fields.keys())

    # Optionally exclude metadata columns from validation
    metadata_columns = {'_ingested_at', '_source_system', '_source_file'}
    if exclude_metadata:
        expected_columns = {col for col in expected_columns if col not in metadata_columns}
        df_columns = {col for col in df_columns if col not in metadata_columns}

    errors = []
    warnings = []

    # Check for missing required columns
    missing_columns = expected_columns - df_columns
    if missing_columns:
        for col_name in sorted(missing_columns):
            field = expected_fields[col_name]
            if not field.nullable:
                errors.append(
                    f"Missing required column '{col_name}' (type: {_get_spark_type_name(field.to_spark_type())})"
                )
            else:
                warnings.append(
                    f"Missing optional column '{col_name}' (type: {_get_spark_type_name(field.to_spark_type())})"
                )

    # Check for extra columns
    extra_columns = df_columns - expected_columns
    if extra_columns and strict_mode:
        errors.append(f"Unexpected columns found: {', '.join(sorted(extra_columns))}")
    elif extra_columns:
        warnings.append(f"Extra columns will be ignored: {', '.join(sorted(extra_columns))}")

    # Check for type mismatches
    df_schema_dict = {field.name: field.dataType for field in df.schema.fields}
    for col_name in expected_columns.intersection(df_columns):
        expected_type = expected_fields[col_name].to_spark_type()
        actual_type = df_schema_dict[col_name]

        expected_type_str = _get_spark_type_name(expected_type)
        actual_type_str = _get_spark_type_name(actual_type)

        if expected_type_str != actual_type_str:
            msg = f"Type mismatch '{col_name}': expected {expected_type_str}, got {actual_type_str}"
            if strict_mode:
                errors.append(msg)
            else:
                warnings.append(f"{msg} (will attempt automatic casting)")

    # Report results
    if errors or warnings:
        logger.info(f"Schema Validation for {target.__name__}: {len(errors)} errors, {len(warnings)} warnings")
        if errors:
            raise SchemaValidationError(f"Validation failed:\n" + "\n".join(errors))


def load_to_bronze(
    spark: SparkSession,
    source_path: str,
    source_system: str,
    target: Optional[Type] = None,
    format: Optional[str] = None,
    options: Optional[Dict[str, str]] = None,
    schema: Optional[StructType] = None,
    exclude_metadata: Optional[List[str]] = None,
    custom_metadata: Optional[Dict[str, Any]] = None,
    validate: bool = True,
    strict_mode: bool = True,
    check_duplicates: bool = True,
    force_reprocess: bool = False
) -> DataFrame:
    """
    Load files into Bronze layer with schema enforcement.

    Note: check_duplicates and force_reprocess parameters are not yet implemented.
    """
    # Validate unimplemented parameters - fail loudly instead of silently ignoring
    if check_duplicates is not True:
        raise NotImplementedError(
            "check_duplicates parameter is not yet implemented. "
            "Currently all files matching the source_path pattern will be processed. "
            "For idempotent ingestion, use the batch_ingestion module or implement "
            "your own deduplication logic."
        )
    if force_reprocess is not False:
        raise NotImplementedError(
            "force_reprocess parameter is not yet implemented. "
            "All files matching the source_path pattern will be processed."
        )

    _validate_csv_s3_source_path(source_path)

    start_time = time.time()
    logger.info(f"Starting bronze ingestion from {source_path}")

    # 1. List Files (Optional)
    found_files = _list_s3_files(source_path) if source_path.startswith("s3://") else []
    if found_files:
        files_to_process = found_files
    else:
        # Fallback: rely on Spark to glob everything
        files_to_process = [{'path': source_path, 'last_modified': 'unknown', 'size': 0}]

    if not files_to_process:
        logger.info("No new files found to process.")
        # Return empty DF with correct schema
        if target:
            return spark.createDataFrame([], schema=target.to_iceberg_schema())
        return spark.createDataFrame([], schema=StructType([]))

    # 2. Validate CSV Headers (Before Reading Data)
    validated_files = []
    skipped_files = []

    if target and validate and found_files:
        # Only validate if we have explicit file list (not wildcard fallback)
        logger.info(f"Validating CSV headers for {len(files_to_process)} files against {target.__name__} contract...")

        for file_info in files_to_process:
            file_path = file_info['path']
            validation_result = _validate_csv_headers_from_s3(file_path, target)

            if validation_result.get('validation_skipped'):
                # Header validation couldn't be performed, let Spark handle it
                validated_files.append(file_info)
                logger.warning(f"Header validation skipped for {file_path}: {validation_result.get('skip_reason')}")

            elif validation_result['is_valid']:
                # Headers match schema
                validated_files.append(file_info)
                logger.info(f"Schema validation passed: {file_path}")

            else:
                # Headers don't match schema
                error_msg = f"Schema validation failed for {file_path}: {validation_result['error_message']}"

                if strict_mode:
                    # Fail immediately in strict mode
                    raise SchemaValidationError(error_msg)
                else:
                    # Log and skip file in non-strict mode
                    logger.warning(f"SKIPPING FILE - {error_msg}")
                    skipped_files.append({'file': file_path, 'reason': validation_result['error_message']})

        # Update files to process with only validated files
        files_to_process = validated_files

        if skipped_files:
            logger.warning(f"Skipped {len(skipped_files)} files due to schema validation failures:")
            for skip_info in skipped_files:
                logger.warning(f"  - {skip_info['file']}: {skip_info['reason']}")

        if not files_to_process:
            logger.warning("No files passed schema validation. Returning empty DataFrame.")
            if target:
                return spark.createDataFrame([], schema=target.to_iceberg_schema())
            return spark.createDataFrame([], schema=StructType([]))

        logger.info(f"Proceeding to read {len(files_to_process)} validated files")

    # 3. Determine Schema (Contract-Driven or Inferred)
    read_schema = schema
    if target and not read_schema:
        # Use the contract schema for reading! (Schema-on-Read)
        # This prevents "Integer vs String" inference issues
        full_schema = target.to_iceberg_schema()
        # Filter out metadata columns from schema as they don't exist in source
        clean_fields = [f for f in full_schema.fields if not f.name.startswith('_')]
        read_schema = StructType(clean_fields)
        logger.info(f"Enforcing schema from contract {target.__name__}")

    # 4. Read Data
    if format and format.lower() != "csv":
        raise ValueError("Only CSV is supported in batch-only mode")
    file_format = "csv"
    
    # Extract just the paths for Spark
    paths_to_read = [f['path'] for f in files_to_process]
    
    # If we have > 1000 files, passing list to Spark driver can be slow. 
    # For very large batches, logic should be batched, but fitting for SME scope.
    if len(paths_to_read) == 1 and '*' in paths_to_read[0]:
         # It's a wildcard fallback
         path_arg = paths_to_read[0]
    else:
         path_arg = paths_to_read

    default_options = {"mode": "PERMISSIVE"}
    if file_format == 'csv':
        default_options.update({"header": "true", "inferSchema": "true" if not read_schema else "false"})
    
    merged_options = _merge_options(default_options, options)
    reader = spark.read.options(**merged_options)
    
    if read_schema:
        reader = reader.schema(read_schema)

    df = reader.csv(path_arg)

    # 5. Add Metadata
    # Use input_file_name() to handle multiple files correctly
    df = add_bronze_metadata(
        df,
        source_system=source_system,
        source_file=None, # Will auto-generate using input_file_name()
        exclude=exclude_metadata,
        custom_metadata=custom_metadata
    )

    # 6. Validation (Optional post-read check for type mismatches)
    if target and validate:
        # Note: Header validation already done in step 2. This checks for type compatibility.
        validate_schema(df, target=target, strict_mode=strict_mode, exclude_metadata=True)

    duration = time.time() - start_time
    logger.info(f"Ingestion prep complete. Duration: {duration:.2f}s")
    
    return df


__all__ = [
    "add_bronze_metadata",
    "load_to_bronze",
    "validate_schema",
    "SchemaValidationError",
]
