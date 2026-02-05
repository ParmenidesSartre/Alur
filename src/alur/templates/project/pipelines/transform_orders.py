"""
Silver layer transformation pipeline for orders.

This pipeline cleans, validates, and deduplicates bronze orders.
Silver transformations: Deduplication, null handling, type validation, business rules.
"""

from alur.decorators import pipeline
from alur.transformation import transform_to_silver, deduplicate, fill_nulls, add_silver_metadata
from alur.quality import expect, no_duplicates_in_column, no_nulls_in_column
from pyspark.sql import functions as F
from contracts.bronze import OrdersBronze
from contracts.silver import OrdersSilver


# Simple example using helper function
@expect(
    name="no_duplicate_orders",
    check_fn=no_duplicates_in_column("order_id"),
    description="Orders must be unique after deduplication"
)
@expect(
    name="no_null_order_ids",
    check_fn=no_nulls_in_column("order_id"),
    description="All orders must have valid IDs"
)
@pipeline(sources={"orders": OrdersBronze}, target=OrdersSilver)
def transform_orders_simple(orders):
    """
    Transform bronze orders to silver layer (simple version).

    Uses high-level helper for common transformations.
    """
    return transform_to_silver(
        orders,
        target=OrdersSilver,
        dedup_by=["order_id"],
        dedup_strategy="latest",
        fill_nulls_map={"status": "unknown"},
        filters=[F.col("amount") >= 0],
        validate=True,
        source_bronze_table="orders"
    )


# Advanced example with manual composition
@pipeline(sources={"orders": OrdersBronze}, target=OrdersSilver)
def transform_orders_advanced(orders):
    """
    Transform bronze orders to silver layer (advanced version).

    Uses composable utilities for fine-grained control.
    """
    # 1. Deduplicate (keep latest by _ingested_at)
    df = deduplicate(
        orders,
        keys=["order_id"],
        order_by=F.desc("_ingested_at"),
        strategy="latest"
    )

    # 2. Fill nulls
    df = fill_nulls(df, {"status": "unknown", "notes": ""})

    # 3. Business rules
    df = df.filter(F.col("amount") >= 0)
    df = df.filter(F.col("quantity") > 0)

    # 4. Normalize status values
    df = df.withColumn(
        "status",
        F.when(F.col("status").isin(["completed", "shipped"]), "fulfilled")
         .otherwise(F.col("status"))
    )

    # 5. Add silver metadata
    df = add_silver_metadata(
        df,
        source_bronze_table="orders",
        transformation_name="transform_orders_advanced"
    )

    return df
