"""
Spark session factory for Alur framework.
Handles SparkSession creation for local and AWS environments.
"""

from typing import Optional
from pyspark.sql import SparkSession


_spark_session: Optional[SparkSession] = None


def get_spark_session(
    local: bool = True,
    app_name: str = "AlurFramework",
    config: Optional[dict] = None,
) -> SparkSession:
    """
    Get or create a SparkSession.

    This function implements a singleton pattern to reuse the same SparkSession
    throughout the application lifecycle.

    Args:
        local: If True, create local SparkSession. If False, create for cluster mode
        app_name: Application name for the Spark session
        config: Additional Spark configuration as key-value pairs

    Returns:
        SparkSession instance
    """
    global _spark_session

    if _spark_session is not None:
        return _spark_session

    builder = SparkSession.builder.appName(app_name)

    if local:
        # Local mode configuration
        builder = builder.master("local[*]")
        builder = builder.config("spark.driver.memory", "2g")
        builder = builder.config("spark.executor.memory", "2g")
        builder = builder.config("spark.sql.warehouse.dir", "/tmp/alur/spark-warehouse")
        builder = builder.config("spark.sql.shuffle.partitions", "4")

        # Enable Hive support for local testing
        builder = builder.enableHiveSupport()

    else:
        # Cluster mode configuration (AWS Glue/EMR)
        builder = builder.config("spark.sql.catalog.glue", "org.apache.iceberg.spark.SparkCatalog")
        builder = builder.config("spark.sql.catalog.glue.catalog-impl", "org.apache.iceberg.aws.glue.GlueCatalog")
        builder = builder.config("spark.sql.catalog.glue.warehouse", "s3://alur-datalake/")
        builder = builder.config("spark.sql.extensions", "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions")

        # Enable Hive support
        builder = builder.enableHiveSupport()

    # Apply additional custom config
    if config:
        for key, value in config.items():
            builder = builder.config(key, value)

    _spark_session = builder.getOrCreate()

    # Set log level to reduce noise
    _spark_session.sparkContext.setLogLevel("WARN")

    return _spark_session


def stop_spark_session() -> None:
    """
    Stop the current SparkSession.
    Useful for testing or cleanup.
    """
    global _spark_session

    if _spark_session is not None:
        _spark_session.stop()
        _spark_session = None


def create_local_spark_session(app_name: str = "AlurLocal") -> SparkSession:
    """
    Create a new local SparkSession (for testing purposes).

    Args:
        app_name: Application name

    Returns:
        New SparkSession instance
    """
    global _spark_session
    stop_spark_session()  # Stop existing session first
    return get_spark_session(local=True, app_name=app_name)


def create_aws_spark_session(
    app_name: str = "AlurAWS",
    warehouse_bucket: str = "alur-datalake",
) -> SparkSession:
    """
    Create a new AWS SparkSession for Glue/EMR.

    Args:
        app_name: Application name
        warehouse_bucket: S3 bucket for Iceberg warehouse

    Returns:
        New SparkSession instance
    """
    global _spark_session
    stop_spark_session()  # Stop existing session first

    config = {
        "spark.sql.catalog.glue.warehouse": f"s3://{warehouse_bucket}/",
    }

    return get_spark_session(local=False, app_name=app_name, config=config)


__all__ = [
    "get_spark_session",
    "stop_spark_session",
    "create_local_spark_session",
    "create_aws_spark_session",
]
