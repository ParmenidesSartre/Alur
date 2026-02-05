"""
Database Ingestion for Bronze Layer.

Uses Glue-native features only:
- GlueContext JDBC connection with Job Bookmarks for incremental tracking
- AWS Secrets Manager for credentials
- No custom state management (no S3 watermarks, no DynamoDB)

Supports: MySQL, PostgreSQL, SQL Server, Oracle, and any JDBC database.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Type
from pyspark.sql import DataFrame, SparkSession
import logging
import json

from alur.utils.aws_helpers import AWSClientFactory

logger = logging.getLogger(__name__)

# JDBC drivers
JDBC_DRIVERS = {
    "mysql": "com.mysql.cj.jdbc.Driver",
    "postgresql": "org.postgresql.Driver",
    "sqlserver": "com.microsoft.sqlserver.jdbc.SQLServerDriver",
    "oracle": "oracle.jdbc.OracleDriver",
}


@dataclass
class DatabaseSource:
    """
    Database source configuration.

    Uses AWS Secrets Manager for secure credential storage.

    Example:
        source = DatabaseSource(
            name="sales_db",
            jdbc_url="jdbc:mysql://host:3306/db",
            secret_name="prod/salesdb/credentials"
        )
    """
    name: str
    jdbc_url: str
    secret_name: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    driver: Optional[str] = None
    properties: Dict[str, str] = field(default_factory=dict)

    def __post_init__(self):
        # Auto-detect driver
        if self.driver is None:
            url_lower = self.jdbc_url.lower()
            if "mysql" in url_lower:
                self.driver = JDBC_DRIVERS["mysql"]
            elif "postgresql" in url_lower:
                self.driver = JDBC_DRIVERS["postgresql"]
            elif "sqlserver" in url_lower:
                self.driver = JDBC_DRIVERS["sqlserver"]
            elif "oracle" in url_lower:
                self.driver = JDBC_DRIVERS["oracle"]

        # Validate credentials
        if not self.secret_name and not (self.username and self.password):
            raise ValueError("Provide secret_name or username/password")

    def get_credentials(self) -> Dict[str, str]:
        """Get credentials from Secrets Manager or direct."""
        if self.secret_name:
            try:
                client = AWSClientFactory.get_secrets_client()
                response = client.get_secret_value(SecretId=self.secret_name)
                secret = json.loads(response["SecretString"])
                return {
                    "username": secret.get("username") or secret.get("user"),
                    "password": secret.get("password") or secret.get("pass"),
                }
            except Exception as e:
                raise RuntimeError(f"Failed to get secret {self.secret_name}: {e}")
        return {"username": self.username, "password": self.password}


def load_from_database(
    glue_context,
    source: DatabaseSource,
    table: str,
    target: Type,
    bookmark_keys: Optional[List[str]] = None,
    bookmark_order: str = "asc",
    columns: Optional[List[str]] = None,
    fetch_size: int = 10000,
    partition_column: Optional[str] = None,
    num_partitions: int = 4,
    lower_bound: Optional[int] = None,
    upper_bound: Optional[int] = None,
    custom_metadata: Optional[Dict[str, Any]] = None,
    validate: bool = True,
    strict_mode: bool = True,
    transformation_ctx: Optional[str] = None
) -> DataFrame:
    """
    Load data from database into Bronze layer using Glue Job Bookmarks.

    Uses GlueContext JDBC with jobBookmarkKeys for automatic incremental
    tracking. No custom watermark storage needed.

    Args:
        glue_context: GlueContext instance
        source: DatabaseSource configuration
        table: Source table name
        target: Target BronzeTable class
        bookmark_keys: Columns for Glue Job Bookmark tracking (e.g. ["updated_at"]).
            Glue tracks MAX(column) and only reads new rows on subsequent runs.
            Omit for full table loads.
        bookmark_order: Sort order for bookmark keys ("asc" or "desc")
        columns: Specific columns to load
        fetch_size: JDBC fetch size
        partition_column: Column for parallel reads
        num_partitions: Number of parallel partitions
        lower_bound: Lower bound for partitioning
        upper_bound: Upper bound for partitioning
        custom_metadata: Additional metadata columns
        validate: Enable schema validation
        strict_mode: Fail on errors or warn
        transformation_ctx: Glue transformation context name (auto-generated if None)

    Returns:
        DataFrame with bronze metadata

    Example:
        df = load_from_database(
            glue_context,
            source=sales_db,
            table="orders",
            target=OrdersBronze,
            bookmark_keys=["updated_at"]
        )
    """
    import time

    start_time = time.time()
    is_incremental = bookmark_keys is not None
    ctx = transformation_ctx or f"db_{source.name}_{table}"

    logger.info(f"Loading from {source.name}.{table}"
                f" (incremental={is_incremental}, ctx={ctx})")

    # Get credentials
    creds = source.get_credentials()

    # Build JDBC connection options
    connection_options = {
        "url": source.jdbc_url,
        "user": creds["username"],
        "password": creds["password"],
        "dbtable": table,
        "fetchsize": str(fetch_size),
    }

    if source.driver:
        connection_options["driver"] = source.driver

    # Add bookmark keys for incremental loading
    if bookmark_keys:
        connection_options["jobBookmarkKeys"] = bookmark_keys
        connection_options["jobBookmarkKeysSortOrder"] = bookmark_order

    # Add column selection
    if columns:
        connection_options["dbtable"] = f"(SELECT {', '.join(columns)} FROM {table}) AS t"

    # Add partitioning for parallel reads
    if partition_column and lower_bound is not None and upper_bound is not None:
        connection_options["hashpartitions"] = str(num_partitions)
        connection_options["hashfield"] = partition_column

    # Add any extra JDBC properties
    connection_options.update(source.properties)

    # Read via GlueContext with bookmark support
    dynamic_frame = glue_context.create_dynamic_frame.from_options(
        connection_type="jdbc",
        connection_options=connection_options,
        transformation_ctx=ctx
    )

    # Convert to Spark DataFrame
    df = dynamic_frame.toDF()
    row_count = df.count()
    logger.info(f"Read {row_count} rows")

    if row_count == 0:
        from alur.utils.spark_helpers import create_empty_dataframe
        return create_empty_dataframe(df.sparkSession, target=target)

    # Add metadata
    from alur.ingestion import add_bronze_metadata
    df = add_bronze_metadata(
        df,
        source_system=source.name,
        source_file=f"jdbc://{source.name}/{table}",
        custom_metadata={
            "_source_table": table,
            "_ingestion_type": "incremental" if is_incremental else "full",
            **(custom_metadata or {})
        }
    )

    # Validate
    if target and validate:
        from alur.ingestion import validate_schema
        validate_schema(df, target=target, strict_mode=strict_mode)

    duration = time.time() - start_time
    logger.info(f"Database load complete: {row_count} rows in {duration:.2f}s")

    return df


# Convenience functions
def create_mysql_source(name: str, host: str, port: int, database: str, secret_name: str, **kwargs) -> DatabaseSource:
    """Create MySQL database source."""
    return DatabaseSource(
        name=name,
        jdbc_url=f"jdbc:mysql://{host}:{port}/{database}",
        secret_name=secret_name,
        **kwargs
    )


def create_postgresql_source(name: str, host: str, port: int, database: str, secret_name: str, **kwargs) -> DatabaseSource:
    """Create PostgreSQL database source."""
    return DatabaseSource(
        name=name,
        jdbc_url=f"jdbc:postgresql://{host}:{port}/{database}",
        secret_name=secret_name,
        **kwargs
    )


def create_sqlserver_source(name: str, host: str, port: int, database: str, secret_name: str, **kwargs) -> DatabaseSource:
    """Create SQL Server database source."""
    return DatabaseSource(
        name=name,
        jdbc_url=f"jdbc:sqlserver://{host}:{port};databaseName={database}",
        secret_name=secret_name,
        **kwargs
    )


__all__ = [
    "DatabaseSource",
    "load_from_database",
    "create_mysql_source",
    "create_postgresql_source",
    "create_sqlserver_source",
]
