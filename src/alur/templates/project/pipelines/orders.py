"""
Example pipeline for processing orders.
"""

from alur.decorators import pipeline
from contracts.bronze import OrdersBronze
from contracts.silver import OrdersSilver
from pyspark.sql import functions as F


@pipeline(
    sources={"orders": OrdersBronze},
    target=OrdersSilver,
    resource_profile="medium"
)
def clean_orders(orders):
    """
    Clean and deduplicate orders from bronze to silver layer.

    Args:
        orders: Bronze orders DataFrame

    Returns:
        Cleaned orders DataFrame
    """
    # Filter out invalid records
    cleaned = orders.filter(
        (F.col("order_id").isNotNull()) &
        (F.col("customer_id").isNotNull()) &
        (F.col("quantity") > 0) &
        (F.col("amount") > 0)
    )

    # Fill null status with 'unknown'
    cleaned = cleaned.withColumn(
        "status",
        F.coalesce(F.col("status"), F.lit("unknown"))
    )

    # Add updated_at timestamp
    cleaned = cleaned.withColumn(
        "updated_at",
        F.current_timestamp()
    )

    # Remove Bronze metadata columns (not needed in silver)
    cleaned = cleaned.drop("_ingested_at", "_source_system", "_source_file")

    return cleaned
