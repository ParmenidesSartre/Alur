"""
Runtime adapters for different execution environments.
Handles Local vs AWS differences for reading/writing data and managing state.
"""

from abc import ABC, abstractmethod
from typing import Type, Optional, Any, Dict
from pyspark.sql import DataFrame
import os
import sqlite3
import json
import time
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger('alur')


class RuntimeAdapter(ABC):
    """Abstract base class for runtime adapters."""

    @abstractmethod
    def read_table(self, table_cls: Type) -> DataFrame:
        """
        Read a table into a Spark DataFrame.

        Args:
            table_cls: Table class definition

        Returns:
            Spark DataFrame
        """
        pass

    @abstractmethod
    def write_table(self, df: DataFrame, table_cls: Type, mode: str = "append") -> None:
        """
        Write a DataFrame to a table.

        Args:
            df: Spark DataFrame to write
            table_cls: Target table class
            mode: Write mode ('append', 'overwrite')
        """
        pass

    @abstractmethod
    def get_state(self, key: str) -> Optional[Any]:
        """
        Get state value for incremental processing (e.g., watermark).

        Args:
            key: State key

        Returns:
            State value or None if not found
        """
        pass

    @abstractmethod
    def set_state(self, key: str, value: Any) -> None:
        """
        Set state value for incremental processing.

        Args:
            key: State key
            value: State value (must be JSON serializable)
        """
        pass

    @abstractmethod
    def table_exists(self, table_cls: Type) -> bool:
        """
        Check if a table exists.

        Args:
            table_cls: Table class definition

        Returns:
            True if table exists, False otherwise
        """
        pass


class LocalAdapter(RuntimeAdapter):
    """Local filesystem adapter using Parquet files and SQLite for state."""

    def __init__(self, base_path: str = "/tmp/alur", state_db_path: Optional[str] = None):
        """
        Initialize LocalAdapter.

        Args:
            base_path: Base directory for data storage
            state_db_path: Path to SQLite database for state management
        """
        self.base_path = base_path
        self.state_db_path = state_db_path or os.path.join(base_path, "state.db")

        # Create base directory if it doesn't exist
        os.makedirs(base_path, exist_ok=True)

        # Initialize state database
        self._init_state_db()

    def _init_state_db(self) -> None:
        """Initialize SQLite database for state management."""
        conn = sqlite3.connect(self.state_db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS state (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()

    def read_table(self, table_cls: Type) -> DataFrame:
        """
        Read a table from local filesystem.

        Args:
            table_cls: Table class definition

        Returns:
            Spark DataFrame
        """
        from .spark import get_spark_session

        spark = get_spark_session(local=True)
        path = table_cls.get_local_path(base_path=self.base_path)

        if not os.path.exists(path):
            # Return empty DataFrame with the correct schema
            return spark.createDataFrame([], schema=table_cls.to_iceberg_schema())

        # Read based on format
        format_type = getattr(table_cls, "_format", "parquet")

        if format_type == "parquet":
            return spark.read.parquet(path)
        elif format_type == "iceberg":
            # For local, we'll use parquet as a fallback for Iceberg
            # In production, this would use actual Iceberg tables
            return spark.read.parquet(path)
        else:
            raise ValueError(f"Unsupported format: {format_type}")

    def write_table(self, df: DataFrame, table_cls: Type, mode: str = "append") -> None:
        """
        Write a DataFrame to local filesystem.

        Args:
            df: Spark DataFrame to write
            table_cls: Target table class
            mode: Write mode ('append', 'overwrite')
        """
        path = table_cls.get_local_path(base_path=self.base_path)
        format_type = getattr(table_cls, "_format", "parquet")

        # Create parent directory
        os.makedirs(os.path.dirname(path), exist_ok=True)

        if format_type == "parquet":
            # Get partition columns if any
            partition_cols = table_cls.get_partition_by()

            writer = df.write.mode(mode)
            if partition_cols:
                writer = writer.partitionBy(*partition_cols)

            writer.parquet(path)

        elif format_type == "iceberg":
            if mode == "merge":
                raise ValueError("merge mode is not supported in bronze-only mode")

            partition_cols = table_cls.get_partition_by()
            writer = df.write.mode(mode)
            if partition_cols:
                writer = writer.partitionBy(*partition_cols)
            writer.parquet(path)
        else:
            raise ValueError(f"Unsupported format: {format_type}")

    def get_state(self, key: str) -> Optional[Any]:
        """
        Get state value from SQLite.

        Args:
            key: State key

        Returns:
            State value or None
        """
        conn = sqlite3.connect(self.state_db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM state WHERE key = ?", (key,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return json.loads(row[0])
        return None

    def set_state(self, key: str, value: Any) -> None:
        """
        Set state value in SQLite.

        Args:
            key: State key
            value: State value (must be JSON serializable)
        """
        conn = sqlite3.connect(self.state_db_path)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO state (key, value) VALUES (?, ?)",
            (key, json.dumps(value))
        )
        conn.commit()
        conn.close()

    def table_exists(self, table_cls: Type) -> bool:
        """
        Check if a table exists locally.

        Args:
            table_cls: Table class definition

        Returns:
            True if table exists
        """
        path = table_cls.get_local_path(base_path=self.base_path)
        return os.path.exists(path)


class AWSAdapter(RuntimeAdapter):
    """AWS adapter using S3, Glue Catalog, and DynamoDB for state."""

    def __init__(self, region: str = "us-east-1", state_table: str = "alur-ingestion-state"):
        """
        Initialize AWSAdapter.

        Args:
            region: AWS region
            state_table: DynamoDB table name for ingestion state tracking
        """
        import boto3

        self.region = region
        self.state_table = state_table
        # S3 client without explicit region - will use bucket's region automatically
        self.s3_client = boto3.client("s3")
        self.glue_client = boto3.client("glue", region_name=region)
        self.dynamodb = boto3.resource("dynamodb", region_name=region)

    def read_table(self, table_cls: Type) -> DataFrame:
        """
        Read a table from Glue Catalog/S3 with retry logic.

        Args:
            table_cls: Table class definition

        Returns:
            Spark DataFrame
        """
        from .spark import get_spark_session
        from config import settings

        spark = get_spark_session(local=False)
        table_name = table_cls.get_table_name()
        database = "bronze_layer"

        logger.info(f"Reading table: {database}.{table_name}")

        # Try reading from Glue Catalog first
        try:
            df = spark.read.table(f"{database}.{table_name}")
            logger.info(f"Successfully read {df.count()} rows from Glue Catalog")
            return df
        except Exception as catalog_error:
            logger.warning(f"Glue Catalog read failed, falling back to direct S3 read: {catalog_error}")

            # Fallback to direct S3 read (bronze-only)
            from alur.core.contracts import BronzeTable

            if not issubclass(table_cls, BronzeTable):
                raise ValueError(
                    f"Unsupported table layer for {table_cls.__name__} (bronze-only mode)"
                )

            bucket = getattr(settings, 'BRONZE_BUCKET', 'alur-bronze-dev')
            layer = 'bronze'

            path = f"s3://{bucket}/{table_name}/"
            format_type = getattr(table_cls, "_format", "parquet")

            # Retry logic for S3 read
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    logger.info(f"Attempting S3 read (attempt {attempt + 1}/{max_retries}): {path}")
                    df = spark.read.format(format_type).load(path)
                    logger.info(f"Successfully read from S3")
                    return df
                except Exception as s3_error:
                    if attempt == max_retries - 1:
                        # Last attempt failed, provide detailed error
                        error_msg = f"""
[ERROR] Failed to read table '{table_name}' from {layer} layer

Location: {path}
Format: {format_type}
Database: {database}
Region: {getattr(settings, 'AWS_REGION', 'unknown')}

Possible causes:
1. Table doesn't exist - run pipeline to create data first
2. S3 bucket '{bucket}' not found - verify config/settings.py
3. Wrong region configured - check AWS_REGION in settings
4. No data in table yet - pipeline may not have run
5. Insufficient AWS permissions to read from S3

Original error: {str(s3_error)}
"""
                        logger.error(error_msg)
                        raise RuntimeError(error_msg)

                    # Wait before retry
                    wait_time = 2 ** attempt  # Exponential backoff
                    logger.warning(f"Read failed, retrying in {wait_time}s...")
                    time.sleep(wait_time)

    def write_table(self, df: DataFrame, table_cls: Type, mode: str = "append") -> None:
        """
        Write a DataFrame to S3/Glue Catalog with validation.

        Args:
            df: Spark DataFrame to write
            table_cls: Target table class
            mode: Write mode
        """
        from config import settings
        from alur.core.contracts import BronzeTable

        table_name = table_cls.get_table_name()

        # Validate DataFrame schema
        expected_fields = set(table_cls._fields.keys())
        actual_fields = set(df.columns)

        missing = expected_fields - actual_fields
        if missing:
            raise ValueError(
                f"DataFrame missing required fields for table '{table_name}': {missing}\n"
                f"Expected: {sorted(expected_fields)}\n"
                f"Got: {sorted(actual_fields)}"
            )

        extra = actual_fields - expected_fields
        if extra:
            logger.warning(f"DataFrame has extra fields that will be ignored: {extra}")

        # Get correct bucket from settings based on table layer (bronze-only)
        if not issubclass(table_cls, BronzeTable):
            raise ValueError(
                f"Unsupported table layer for {table_cls.__name__} (bronze-only mode)"
            )

        bucket = getattr(settings, 'BRONZE_BUCKET', 'alur-bronze-dev')
        layer = 'bronze'

        path = f"s3://{bucket}/{table_name}/"
        format_type = getattr(table_cls, "_format", "parquet")
        partition_cols = table_cls.get_partition_by()

        # Validate partition columns exist in DataFrame
        for col in partition_cols:
            if col not in df.columns:
                raise ValueError(
                    f"Partition column '{col}' not found in DataFrame.\n"
                    f"Available columns: {df.columns}"
                )

        row_count = df.count()
        logger.info(f"Writing {row_count} rows to {layer} table '{table_name}'")
        logger.info(f"Target: {path} (format: {format_type}, mode: {mode})")

        if mode == "merge":
            raise ValueError("merge mode is not supported in bronze-only mode")

        try:
            writer = df.write.mode(mode).format(format_type)
            if partition_cols:
                logger.info(f"Partitioning by: {partition_cols}")
                writer = writer.partitionBy(*partition_cols)

            writer.save(path)
            logger.info(f"Successfully wrote {row_count} rows to {path}")

            # Mark files as processed for idempotency (if enabled)
            if hasattr(df, '_alur_files_to_track'):
                tracking_info = df._alur_files_to_track
                if tracking_info.get('enable_idempotency'):
                    logger.info("Marking files as processed for idempotency...")

                    ingestion_key = tracking_info['ingestion_key']
                    files_processed = tracking_info['files']

                    for file_info in files_processed:
                        file_path = file_info['path']
                        file_size = file_info.get('size', 0)
                        # Get ETag from S3 metadata
                        try:
                            from urllib.parse import urlparse
                            parsed = urlparse(file_path)
                            bucket = parsed.netloc
                            key = parsed.path.lstrip('/')

                            obj_metadata = self.s3_client.head_object(Bucket=bucket, Key=key)
                            file_etag = obj_metadata.get('ETag', '').strip('"')
                        except Exception as e:
                            logger.warning(f"Could not get ETag for {file_path}: {e}")
                            file_etag = "unknown"

                        # Estimate rows per file (total rows / num files)
                        rows_per_file = row_count // len(files_processed) if files_processed else row_count

                        try:
                            self.mark_file_processed(
                                ingestion_key=ingestion_key,
                                file_path=file_path,
                                file_size=file_size,
                                file_etag=file_etag,
                                rows_ingested=rows_per_file
                            )
                        except Exception as e:
                            logger.warning(f"Failed to mark file as processed: {file_path}: {e}")

                    logger.info(f"Marked {len(files_processed)} file(s) as processed")

            # Automatically register partitions in Glue Catalog
            # This eliminates the need for users to manually run MSCK REPAIR TABLE
            if partition_cols:
                logger.info("Registering partitions in Glue Catalog...")

                # Use Spark SQL MSCK REPAIR TABLE
                # This is the most compatible approach across AWS environments
                try:
                    from .spark import get_spark_session
                    spark = get_spark_session(local=False)

                    database = "bronze_layer"

                    # Refresh table metadata first
                    try:
                        spark.catalog.refreshTable(f"{database}.{table_name}")
                    except Exception:
                        pass  # Table might not be in cache yet

                    # Run MSCK REPAIR TABLE using Spark SQL
                    repair_query = f"MSCK REPAIR TABLE `{database}`.`{table_name}`"
                    spark.sql(repair_query)

                    logger.info(f"Partitions registered successfully for {database}.{table_name}")

                except Exception as repair_error:
                    # Log warning but don't fail the write
                    error_str = str(repair_error)
                    logger.warning(f"Failed to auto-register partitions: {error_str}")
                    logger.warning("Data written successfully, but partitions may need manual registration")
                    logger.warning(f"Run in Athena: MSCK REPAIR TABLE {database}.{table_name}")

                    # If error is due to Lake Formation or permissions, provide more context
                    if "Lake Formation" in error_str or "AccessDenied" in error_str:
                        logger.warning("Note: Partition registration requires Lake Formation permissions.")
                        logger.warning("Contact your AWS administrator to grant ALTER permissions on the table.")
        except Exception as e:
            error_msg = f"""
[ERROR] Failed to write to table '{table_name}'

Target: {path}
Mode: {mode}
Format: {format_type}
Rows: {row_count}
Partitions: {partition_cols or 'None'}

Possible causes:
1. S3 bucket '{bucket}' doesn't exist - run 'alur deploy' first
2. Insufficient permissions to write to S3
3. Invalid data types in DataFrame
4. Partition column has null values

Original error: {str(e)}
"""
            logger.error(error_msg)
            raise RuntimeError(error_msg)

    def get_state(self, key: str) -> Optional[Any]:
        """
        Get state value from DynamoDB.

        Args:
            key: State key

        Returns:
            State value or None
        """
        table = self.dynamodb.Table(self.state_table)
        response = table.get_item(Key={"key": key})
        item = response.get("Item")
        return json.loads(item["value"]) if item else None

    def set_state(self, key: str, value: Any) -> None:
        """
        Set state value in DynamoDB.

        Args:
            key: State key
            value: State value
        """
        table = self.dynamodb.Table(self.state_table)
        table.put_item(Item={"key": key, "value": json.dumps(value)})

    def is_file_processed(self, ingestion_key: str, file_path: str) -> bool:
        """
        Check if a file has already been processed.

        Args:
            ingestion_key: Unique key for this ingestion (e.g., target table name)
            file_path: S3 path of the file

        Returns:
            True if file was already processed
        """
        table = self.dynamodb.Table(self.state_table)

        try:
            response = table.get_item(
                Key={
                    "ingestion_key": ingestion_key,
                    "file_path": file_path
                }
            )
            return "Item" in response
        except Exception as e:
            logger.warning(f"Error checking file state: {e}")
            return False  # On error, assume not processed (fail-safe)

    def mark_file_processed(
        self,
        ingestion_key: str,
        file_path: str,
        file_size: int,
        file_etag: str,
        rows_ingested: int
    ) -> None:
        """
        Mark a file as successfully processed.

        Args:
            ingestion_key: Unique key for this ingestion (e.g., target table name)
            file_path: S3 path of the file
            file_size: File size in bytes
            file_etag: S3 ETag for file version tracking
            rows_ingested: Number of rows ingested from this file
        """
        import time

        table = self.dynamodb.Table(self.state_table)

        try:
            table.put_item(
                Item={
                    "ingestion_key": ingestion_key,
                    "file_path": file_path,
                    "file_size": file_size,
                    "file_etag": file_etag,
                    "rows_ingested": rows_ingested,
                    "processed_at": int(time.time()),
                    "processed_at_iso": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
                }
            )
            logger.info(f"Marked file as processed: {file_path}")
        except Exception as e:
            logger.warning(f"Failed to mark file as processed: {e}")
            # Don't fail the job if state tracking fails

    def get_processed_files(self, ingestion_key: str) -> list:
        """
        Get list of all processed files for an ingestion key.

        Args:
            ingestion_key: Unique key for this ingestion

        Returns:
            List of file paths that have been processed
        """
        table = self.dynamodb.Table(self.state_table)

        try:
            response = table.query(
                KeyConditionExpression="ingestion_key = :key",
                ExpressionAttributeValues={":key": ingestion_key}
            )
            return [item["file_path"] for item in response.get("Items", [])]
        except Exception as e:
            logger.warning(f"Error querying processed files: {e}")
            return []

    def table_exists(self, table_cls: Type) -> bool:
        """
        Check if a table exists in Glue Catalog.

        Args:
            table_cls: Table class definition

        Returns:
            True if table exists
        """
        database = "alur_datalake"
        table_name = table_cls.get_table_name()

        try:
            self.glue_client.get_table(DatabaseName=database, Name=table_name)
            return True
        except self.glue_client.exceptions.EntityNotFoundException:
            return False


__all__ = [
    "RuntimeAdapter",
    "LocalAdapter",
    "AWSAdapter",
]
