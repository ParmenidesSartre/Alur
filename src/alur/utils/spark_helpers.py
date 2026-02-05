"""
Spark DataFrame utility functions.
Common operations for creating, manipulating, and adding metadata to DataFrames.
"""

from typing import Optional, Type, Dict, Any, List
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import StructType


def create_empty_dataframe(
    spark: SparkSession,
    target: Optional[Type] = None,
    schema: Optional[StructType] = None
) -> DataFrame:
    """
    Create an empty DataFrame with the correct schema.

    Args:
        spark: SparkSession
        target: Table class with to_iceberg_schema() method
        schema: Explicit Spark StructType schema

    Returns:
        Empty DataFrame with specified schema

    Example:
        # Using table contract
        df = create_empty_dataframe(spark, target=OrdersBronze)

        # Using explicit schema
        schema = StructType([...])
        df = create_empty_dataframe(spark, schema=schema)

        # Empty DataFrame with no schema
        df = create_empty_dataframe(spark)
    """
    if target:
        if not hasattr(target, 'to_iceberg_schema'):
            raise ValueError(f"{target.__name__} must have to_iceberg_schema() method")
        return spark.createDataFrame([], schema=target.to_iceberg_schema())

    if schema:
        return spark.createDataFrame([], schema=schema)

    return spark.createDataFrame([], schema=StructType([]))


def add_metadata_columns(
    df: DataFrame,
    columns: Dict[str, Any],
    exclude: Optional[List[str]] = None
) -> DataFrame:
    """
    Add metadata columns to a DataFrame with conditional exclusion.

    This is a generic function used by both add_bronze_metadata and add_silver_metadata
    to eliminate code duplication.

    Args:
        df: Input DataFrame
        columns: Dictionary of column_name -> column_value (can be literal or Column expression)
        exclude: List of column names to exclude from addition

    Returns:
        DataFrame with metadata columns added

    Example:
        # Add simple metadata
        df = add_metadata_columns(df, {
            "_ingested_at": F.current_timestamp(),
            "_source_system": F.lit("sales"),
            "_version": F.lit("1.0")
        })

        # With exclusions
        df = add_metadata_columns(
            df,
            columns={
                "_ingested_at": F.current_timestamp(),
                "_source_system": F.lit("sales"),
            },
            exclude=["_source_system"]  # Won't add _source_system
        )
    """
    result_df = df
    exclude = exclude or []

    for col_name, col_value in columns.items():
        if col_name not in exclude:
            # Check if column already exists to avoid duplicates
            if col_name not in result_df.columns:
                result_df = result_df.withColumn(col_name, col_value)

    return result_df


__all__ = [
    "create_empty_dataframe",
    "add_metadata_columns",
]
