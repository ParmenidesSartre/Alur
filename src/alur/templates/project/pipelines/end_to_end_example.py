"""
Complete Bronze → Silver → Gold pipeline example.

Demonstrates:
1. Bronze: Ingest raw CSV from S3
2. Silver: Deduplicate, validate, cleanse, MERGE
3. Gold: Aggregate business metrics

This example shows the full medallion architecture workflow with:
- File-level idempotency (Glue Job Bookmarks)
- Schema validation and type casting
- Data quality checks at each layer
- MERGE/upsert operations for Silver
- Business metric aggregations for Gold
"""

from pyspark.sql import SparkSession, DataFrame
from pyspark.sql import functions as F
from datetime import datetime

from alur import (
    pipeline, schedule,
    load_to_bronze, BronzeTable,
    SilverTable, GoldTable,
    transform_to_silver,
    expect, not_empty, no_nulls_in_column, no_duplicates_in_column,
    column_values_in_range
)


# ============================================================================
# BRONZE LAYER - Raw Ingestion
# ============================================================================

@pipeline(name="ingest_sales", layer="bronze")
@schedule(cron="0 */6 * * *", enabled=True)  # Every 6 hours
def ingest_sales(spark: SparkSession) -> DataFrame:
    """
    Ingest raw sales data from S3 CSV files.

    Features:
    - Idempotency via Glue Job Bookmarks (file-level tracking)
    - Schema validation against BronzeTable contract
    - Metadata addition (_ingested_at, _source_system, _source_file)
    - Automatic partition by ingestion date
    """
    return load_to_bronze(
        spark=spark,
        source_path="s3://raw-data-bucket/sales/*.csv",
        source_system="salesforce",
        target=SalesBronze,
        validate=True
    )


class SalesBronze(BronzeTable):
    """Raw sales transactions (all strings for flexibility)."""
    transaction_id: str
    customer_id: str
    product_id: str
    quantity: str
    unit_price: str
    transaction_date: str
    status: str
    notes: str

    @classmethod
    def get_table_name(cls) -> str:
        return "sales"

    @classmethod
    def get_partition_by(cls) -> list:
        return ["_ingestion_date"]


# ============================================================================
# SILVER LAYER - Cleansing & Conformance
# ============================================================================

@pipeline(name="transform_sales", layer="silver", depends_on=["ingest_sales"])
@schedule(cron="0 */6 * * *", enabled=True)  # Run after Bronze ingestion
@expect(not_empty(), severity="ERROR")
@expect(no_nulls_in_column("transaction_id"), severity="ERROR")
@expect(no_duplicates_in_column("transaction_id"), severity="ERROR")
@expect(column_values_in_range("total_amount", min_value=0), severity="WARN")
def transform_sales(spark: SparkSession) -> DataFrame:
    """
    Transform Bronze sales to Silver with:
    1. Deduplication (latest record per transaction_id)
    2. Type casting (string → proper types)
    3. Null filling (default values for optional fields)
    4. Business logic (calculate total_amount, normalize status)
    5. Quality validation (via @expect decorators)
    6. MERGE operation (idempotent writes via primary key)
    """
    # Read from Bronze
    bronze_df = spark.table("bronze_layer.sales")

    # High-level transformation helper
    silver_df = transform_to_silver(
        df=bronze_df,
        target=SalesSilver,
        dedup_by=["transaction_id"],
        dedup_strategy="latest",
        fill_nulls_map={
            "notes": "",
            "discount_amount": 0.0
        },
        filters=[
            F.col("quantity").cast("int") > 0,  # Filter invalid quantities
            F.col("unit_price").cast("decimal(10,2)") >= 0  # Filter negative prices
        ],
        validate=True,
        source_bronze_table="sales"
    )

    # Apply business logic
    silver_df = (silver_df
        .withColumn("total_amount",
            F.col("quantity") * F.col("unit_price") - F.coalesce(F.col("discount_amount"), F.lit(0.0)))
        .withColumn("status",
            F.upper(F.trim(F.col("status"))))  # Normalize status
        .withColumn("transaction_year",
            F.year("transaction_date"))
        .withColumn("transaction_month",
            F.month("transaction_date"))
    )

    return silver_df


class SalesSilver(SilverTable):
    """Cleaned and validated sales transactions."""
    transaction_id: str
    customer_id: str
    product_id: str
    quantity: int
    unit_price: float  # decimal(10,2)
    discount_amount: float  # decimal(10,2)
    total_amount: float  # decimal(10,2)
    transaction_date: datetime
    transaction_year: int
    transaction_month: int
    status: str
    notes: str

    # Silver metadata (added automatically)
    # _transformed_at: timestamp
    # _source_bronze_table: str
    # _transformation_name: str

    @classmethod
    def get_table_name(cls) -> str:
        return "sales"

    @classmethod
    def get_primary_key(cls) -> list:
        """Primary key for MERGE/upsert operations."""
        return ["transaction_id"]

    @classmethod
    def get_partition_by(cls) -> list:
        """Partition by year for query performance."""
        return ["transaction_year", "transaction_month"]


# ============================================================================
# GOLD LAYER - Business Metrics
# ============================================================================

@pipeline(name="aggregate_daily_sales", layer="gold", depends_on=["transform_sales"])
@schedule(cron="0 8 * * *", enabled=True)  # Daily at 8am
@expect(not_empty(), severity="ERROR")
@expect(column_values_in_range("total_revenue", min_value=0), severity="ERROR")
def aggregate_daily_sales(spark: SparkSession) -> DataFrame:
    """
    Aggregate Silver sales into daily business metrics.

    Metrics:
    - Total revenue per day
    - Transaction count per day
    - Average transaction value
    - Unique customers per day
    - Total items sold
    """
    silver_df = spark.table("silver_layer.sales")

    # Filter to completed transactions only
    completed_df = silver_df.filter(F.col("status") == "COMPLETED")

    # Daily aggregation
    gold_df = (completed_df
        .groupBy(
            F.to_date("transaction_date").alias("sale_date")
        )
        .agg(
            F.sum("total_amount").alias("total_revenue"),
            F.count("*").alias("transaction_count"),
            F.avg("total_amount").alias("avg_transaction_value"),
            F.countDistinct("customer_id").alias("unique_customers"),
            F.sum("quantity").alias("total_items_sold")
        )
        .withColumn("revenue_per_customer",
            F.col("total_revenue") / F.col("unique_customers"))
    )

    # Add Gold metadata
    gold_df = (gold_df
        .withColumn("_aggregated_at", F.current_timestamp())
        .withColumn("_source_silver_table", F.lit("sales"))
        .withColumn("_metric_type", F.lit("daily_sales"))
    )

    return gold_df


class DailySalesGold(GoldTable):
    """Daily sales aggregations and business metrics."""
    sale_date: datetime
    total_revenue: float
    transaction_count: int
    avg_transaction_value: float
    unique_customers: int
    total_items_sold: int
    revenue_per_customer: float

    # Gold metadata
    _aggregated_at: datetime
    _source_silver_table: str
    _metric_type: str

    @classmethod
    def get_table_name(cls) -> str:
        return "daily_sales"

    @classmethod
    def get_primary_key(cls) -> list:
        """Primary key for daily aggregations."""
        return ["sale_date"]

    @classmethod
    def get_partition_by(cls) -> list:
        """Partition by year-month for time-series queries."""
        return ["year(sale_date)", "month(sale_date)"]
