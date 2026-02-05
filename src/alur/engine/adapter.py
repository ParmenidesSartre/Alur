"""
Runtime adapter for AWS Glue execution environment.

Simplified design using only:
- S3 for data storage
- Glue Catalog for table metadata
- S3 marker files for state (optional)
- Glue Job Bookmarks for idempotency (built-in)

No DynamoDB dependency.
"""

from abc import ABC, abstractmethod
from typing import Type, Optional, Any, Dict
from pyspark.sql import DataFrame
import json
import time
import logging

from alur.utils.aws_helpers import AWSClientFactory, S3Path

logger = logging.getLogger(__name__)


class RuntimeAdapter(ABC):
    """Abstract base class for runtime adapters."""

    @abstractmethod
    def read_table(self, table_cls: Type) -> DataFrame:
        """Read a table into a Spark DataFrame."""
        pass

    @abstractmethod
    def write_table(self, df: DataFrame, table_cls: Type, mode: str = "append") -> None:
        """Write a DataFrame to a table."""
        pass

    @abstractmethod
    def table_exists(self, table_cls: Type) -> bool:
        """Check if a table exists."""
        pass


class AWSAdapter(RuntimeAdapter):
    """
    AWS adapter using S3 and Glue Catalog.

    Idempotency is handled by Glue Job Bookmarks (built into AWS Glue).
    No external state management needed.
    """

    def __init__(self, region: str = "us-east-1"):
        """
        Initialize AWSAdapter.

        Args:
            region: AWS region
        """
        self.region = region
        self.s3_client = AWSClientFactory.get_s3_client()
        self.glue_client = AWSClientFactory.get_glue_client(region)

    def read_table(self, table_cls: Type) -> DataFrame:
        """
        Read a table from Glue Catalog/S3.

        Args:
            table_cls: Table class definition

        Returns:
            Spark DataFrame
        """
        from .spark import get_spark_session
        from config import settings

        spark = get_spark_session(local=False)
        table_name = table_cls.get_table_name()

        # Determine layer and database
        from alur.core.contracts import BronzeTable, SilverTable, GoldTable

        if issubclass(table_cls, BronzeTable):
            database = "bronze_layer"
            bucket = getattr(settings, 'BRONZE_BUCKET', 'alur-bronze-dev')
        elif issubclass(table_cls, SilverTable):
            database = "silver_layer"
            bucket = getattr(settings, 'SILVER_BUCKET', 'alur-silver-dev')
        elif issubclass(table_cls, GoldTable):
            database = "gold_layer"
            bucket = getattr(settings, 'GOLD_BUCKET', 'alur-gold-dev')
        else:
            raise ValueError(f"Unknown table layer for {table_cls.__name__}")

        logger.info(f"Reading table: {database}.{table_name}")

        # Try Glue Catalog first
        try:
            df = spark.read.table(f"{database}.{table_name}")
            logger.info(f"Read from Glue Catalog: {database}.{table_name}")
            return df
        except Exception as e:
            logger.warning(f"Glue Catalog read failed, trying direct S3: {e}")

        # Fallback to direct S3 read
        path = f"s3://{bucket}/{table_name}/"
        format_type = getattr(table_cls, "_format", "parquet")

        try:
            df = spark.read.format(format_type).load(path)
            logger.info(f"Read from S3: {path}")
            return df
        except Exception as e:
            raise RuntimeError(
                f"Failed to read table '{table_name}'\n"
                f"Tried: {database}.{table_name} (Glue) and {path} (S3)\n"
                f"Error: {e}"
            )

    def write_table(
        self,
        df: DataFrame,
        table_cls: Type,
        mode: str = "append"
    ) -> None:
        """
        Write a DataFrame to S3 and register in Glue Catalog.

        Args:
            df: Spark DataFrame to write
            table_cls: Target table class
            mode: Write mode ('append', 'overwrite', 'merge')
        """
        from config import settings
        from alur.core.contracts import BronzeTable, SilverTable, GoldTable

        table_name = table_cls.get_table_name()

        # Determine bucket and layer
        if issubclass(table_cls, BronzeTable):
            bucket = getattr(settings, 'BRONZE_BUCKET', 'alur-bronze-dev')
            layer = 'bronze'
        elif issubclass(table_cls, SilverTable):
            bucket = getattr(settings, 'SILVER_BUCKET', 'alur-silver-dev')
            layer = 'silver'
        elif issubclass(table_cls, GoldTable):
            bucket = getattr(settings, 'GOLD_BUCKET', 'alur-gold-dev')
            layer = 'gold'
        else:
            raise ValueError(f"Unknown table layer for {table_cls.__name__}")

        path = f"s3://{bucket}/{table_name}/"
        format_type = getattr(table_cls, "_format", "parquet")
        partition_cols = table_cls.get_partition_by()

        row_count = df.count()
        logger.info(f"Writing {row_count} rows to {layer}/{table_name}")

        # Handle merge mode for Iceberg tables
        if mode == "merge":
            self._write_merge(df, table_cls, layer)
            return

        # Standard write
        try:
            writer = df.write.mode(mode).format(format_type)
            if partition_cols:
                writer = writer.partitionBy(*partition_cols)

            writer.save(path)
            logger.info(f"Wrote {row_count} rows to {path}")

            # Register partitions in Glue Catalog
            if partition_cols:
                self._register_partitions(table_name, layer)

        except Exception as e:
            raise RuntimeError(f"Failed to write table '{table_name}': {e}")

    def _write_merge(self, df: DataFrame, table_cls: Type, layer: str) -> None:
        """Execute MERGE INTO for Iceberg tables."""
        from .spark import get_spark_session

        table_name = table_cls.get_table_name()
        database = f"{layer}_layer"
        merge_keys = getattr(table_cls, 'get_merge_keys', lambda: None)()

        if not merge_keys:
            raise ValueError(f"Merge requires primary_key in {table_cls.__name__}.Meta")

        if not self.table_exists(table_cls):
            logger.info(f"Table doesn't exist, creating with initial data")
            self.write_table(df, table_cls, mode="overwrite")
            return

        spark = get_spark_session(local=False)
        temp_view = f"__{table_name}_merge_source"
        df.createOrReplaceTempView(temp_view)

        merge_condition = " AND ".join([f"t.{k} = s.{k}" for k in merge_keys])
        update_cols = [c for c in df.columns if c not in merge_keys]
        set_clause = ", ".join([f"t.{c} = s.{c}" for c in update_cols])
        insert_cols = ", ".join(df.columns)
        insert_vals = ", ".join([f"s.{c}" for c in df.columns])

        merge_sql = f"""
        MERGE INTO {database}.{table_name} AS t
        USING {temp_view} AS s ON {merge_condition}
        WHEN MATCHED THEN UPDATE SET {set_clause}
        WHEN NOT MATCHED THEN INSERT ({insert_cols}) VALUES ({insert_vals})
        """

        spark.sql(merge_sql)
        logger.info(f"Merged into {database}.{table_name}")

    def _register_partitions(self, table_name: str, layer: str) -> None:
        """Register new partitions in Glue Catalog."""
        from .spark import get_spark_session

        try:
            spark = get_spark_session(local=False)
            database = f"{layer}_layer"
            spark.sql(f"MSCK REPAIR TABLE `{database}`.`{table_name}`")
            logger.info(f"Registered partitions for {database}.{table_name}")
        except Exception as e:
            logger.warning(f"Failed to register partitions: {e}")

    def table_exists(self, table_cls: Type) -> bool:
        """Check if a table exists in Glue Catalog."""
        from alur.core.contracts import BronzeTable, SilverTable, GoldTable

        table_name = table_cls.get_table_name()

        if issubclass(table_cls, BronzeTable):
            database = "bronze_layer"
        elif issubclass(table_cls, SilverTable):
            database = "silver_layer"
        elif issubclass(table_cls, GoldTable):
            database = "gold_layer"
        else:
            return False

        try:
            self.glue_client.get_table(DatabaseName=database, Name=table_name)
            return True
        except self.glue_client.exceptions.EntityNotFoundException:
            return False
        except Exception as e:
            logger.warning(f"Error checking table existence: {e}")
            return False


__all__ = ["AWSAdapter", "RuntimeAdapter"]
