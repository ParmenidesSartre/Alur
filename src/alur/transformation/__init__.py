"""
Transformation utilities for Silver layer data processing.

Provides helper functions for common silver layer operations:
- Deduplication
- Null handling
- Type casting
- Metadata addition
"""

from typing import List, Dict, Optional, Union, Any, Type
from pyspark.sql import DataFrame, Window
from pyspark.sql import functions as F
from pyspark.sql.column import Column

from alur.utils.spark_helpers import add_metadata_columns


def deduplicate(
    df: DataFrame,
    keys: List[str],
    order_by: Optional[Union[str, Column]] = None,
    strategy: str = "latest"
) -> DataFrame:
    """
    Deduplicate DataFrame by keys.

    Args:
        df: Input DataFrame
        keys: Columns to use as deduplication keys
        order_by: Column to order by (default: _ingested_at desc)
        strategy: 'latest' (keep latest), 'first' (keep first), 'distinct' (arbitrary)

    Returns:
        Deduplicated DataFrame

    Example:
        # Keep latest record by order_id
        df = deduplicate(df, keys=["order_id"], strategy="latest")

        # Keep first record with custom order
        df = deduplicate(df, keys=["customer_id"],
                        order_by=F.asc("created_at"),
                        strategy="first")
    """
    if strategy == "distinct":
        return df.dropDuplicates(keys)

    elif strategy == "latest" or strategy == "first":
        if order_by is None:
            if "_ingested_at" not in df.columns:
                raise ValueError(
                    f"Cannot use strategy '{strategy}' without order_by column. "
                    f"Either provide order_by parameter or ensure DataFrame has '_ingested_at' column."
                )
            order_by = F.desc("_ingested_at") if strategy == "latest" else F.asc("_ingested_at")

        window = Window.partitionBy(*keys).orderBy(order_by)

        return (df
            .withColumn("_dedup_rank", F.row_number().over(window))
            .filter(F.col("_dedup_rank") == 1)
            .drop("_dedup_rank")
        )

    else:
        raise ValueError(f"Unknown deduplication strategy: {strategy}. Use 'latest', 'first', or 'distinct'.")


def fill_nulls(
    df: DataFrame,
    fill_values: Dict[str, Any]
) -> DataFrame:
    """
    Fill null values with specified defaults.

    Args:
        df: Input DataFrame
        fill_values: Dict mapping column names to fill values

    Returns:
        DataFrame with nulls filled

    Example:
        df = fill_nulls(df, {
            "status": "unknown",
            "notes": "",
            "quantity": 0
        })
    """
    return df.fillna(fill_values)


def cast_types(
    df: DataFrame,
    target: Optional[Type] = None,
    type_map: Optional[Dict[str, str]] = None
) -> DataFrame:
    """
    Cast columns to target types.

    Args:
        df: Input DataFrame
        target: Target table class (uses contract schema)
        type_map: Manual type mapping (column_name -> spark type string)

    Returns:
        DataFrame with casted types

    Example:
        # Using contract
        df = cast_types(df, target=OrdersSilver)

        # Manual mapping
        df = cast_types(df, type_map={
            "amount": "integer",
            "created_at": "timestamp"
        })
    """
    if target:
        schema = target.to_iceberg_schema()
        for field in schema.fields:
            if field.name in df.columns:
                df = df.withColumn(field.name, F.col(field.name).cast(field.dataType))

    elif type_map:
        for col_name, spark_type in type_map.items():
            if col_name in df.columns:
                df = df.withColumn(col_name, F.col(col_name).cast(spark_type))

    else:
        raise ValueError("Must provide either 'target' or 'type_map'")

    return df


def add_silver_metadata(
    df: DataFrame,
    source_bronze_table: Optional[str] = None,
    transformation_name: Optional[str] = None,
    exclude: Optional[List[str]] = None
) -> DataFrame:
    """
    Add standard Silver layer metadata columns.

    Metadata columns:
    - _transformed_at: When transformation ran
    - _source_bronze_table: Source bronze table name
    - _transformation_name: Pipeline that created this record

    Args:
        df: Input DataFrame
        source_bronze_table: Name of source bronze table
        transformation_name: Name of transformation pipeline
        exclude: List of metadata columns to exclude

    Returns:
        DataFrame with metadata columns added

    Example:
        df = add_silver_metadata(
            df,
            source_bronze_table="orders",
            transformation_name="transform_orders"
        )
    """
    exclude = exclude or []

    # Build metadata column map
    metadata_cols = {}

    if "_transformed_at" not in exclude:
        metadata_cols["_transformed_at"] = F.current_timestamp()

    if "_source_bronze_table" not in exclude and source_bronze_table:
        metadata_cols["_source_bronze_table"] = F.lit(source_bronze_table)

    if "_transformation_name" not in exclude and transformation_name:
        metadata_cols["_transformation_name"] = F.lit(transformation_name)

    # Use generic metadata addition function
    return add_metadata_columns(df, metadata_cols, exclude=exclude)


def transform_to_silver(
    df: DataFrame,
    target: Type,
    dedup_by: Optional[List[str]] = None,
    dedup_strategy: str = "latest",
    fill_nulls_map: Optional[Dict[str, Any]] = None,
    filters: Optional[List[Column]] = None,
    validate: bool = True,
    source_bronze_table: Optional[str] = None
) -> DataFrame:
    """
    High-level helper for common silver transformations.

    Applies:
    1. Deduplication (if dedup_by provided)
    2. Null filling (if fill_nulls_map provided)
    3. Business rule filters (if filters provided)
    4. Type casting (if validate=True)
    5. Silver metadata addition

    Args:
        df: Input DataFrame
        target: Target silver table class
        dedup_by: Columns to deduplicate on
        dedup_strategy: Deduplication strategy ('latest', 'first', 'distinct')
        fill_nulls_map: Dict of column -> fill value
        filters: List of filter conditions to apply
        validate: Whether to cast types from target schema

    Returns:
        Transformed DataFrame ready for silver layer

    Example:
        df = transform_to_silver(
            orders_bronze,
            target=OrdersSilver,
            dedup_by=["order_id"],
            dedup_strategy="latest",
            fill_nulls_map={"status": "unknown"},
            filters=[F.col("amount") >= 0],
            validate=True
        )
    """
    result = df

    # 1. Deduplication
    if dedup_by:
        result = deduplicate(result, keys=dedup_by, strategy=dedup_strategy)

    # 2. Fill nulls
    if fill_nulls_map:
        result = fill_nulls(result, fill_nulls_map)

    # 3. Apply filters
    if filters:
        for filter_condition in filters:
            result = result.filter(filter_condition)

    # 4. Type casting
    if validate:
        result = cast_types(result, target=target)

    # 5. Add metadata
    table_name = target.get_table_name() if hasattr(target, 'get_table_name') else "unknown"
    result = add_silver_metadata(
        result,
        source_bronze_table=source_bronze_table,
        transformation_name=table_name
    )

    return result


__all__ = [
    "deduplicate",
    "fill_nulls",
    "cast_types",
    "add_silver_metadata",
    "transform_to_silver",
]
