"""
Bronze Layer Ingestion Examples for Alur Framework.

Demonstrates how to load raw data into Bronze tables with metadata.
Bronze philosophy: Raw data as-is + metadata. NO transformations.
"""

from alur.core import BronzeTable, StringField, IntegerField, TimestampField
from alur.decorators import pipeline
from alur.ingestion import (
    add_bronze_metadata,
    load_csv_to_bronze,
    load_json_to_bronze,
    load_parquet_to_bronze,
    handle_bad_records,
    IncrementalLoader
)
from alur.engine import get_spark_session
from pyspark.sql import functions as F


# ============================================================================
# EXAMPLE 1: Simple CSV Ingestion with Metadata
# ============================================================================

class OrdersBronze(BronzeTable):
    """Raw orders from sales system."""

    order_id = StringField(nullable=False)
    customer_id = StringField(nullable=False)
    product_id = StringField(nullable=True)
    quantity = IntegerField(nullable=True)
    amount = IntegerField(nullable=True)
    status = StringField(nullable=True)
    created_at = TimestampField(nullable=True)

    # Bronze metadata fields (added automatically by helpers)
    _ingested_at = TimestampField(nullable=True)
    _source_system = StringField(nullable=True)
    _source_file = StringField(nullable=True)

    class Meta:
        partition_by = ["created_at"]
        description = "Raw orders from sales database"


@pipeline(sources={}, target=OrdersBronze)
def ingest_orders_csv():
    """
    Load CSV files from landing zone into Bronze.

    Bronze pattern:
    1. Load raw data as-is
    2. Add ingestion metadata (_ingested_at, _source_system, _source_file)
    3. NO transformations, NO filtering
    4. Keep everything for auditability
    """
    spark = get_spark_session()

    # Load CSV with automatic metadata
    df = load_csv_to_bronze(
        spark,
        source_path="s3://landing-zone/orders/*.csv",
        source_system="sales_db",
        options={
            "header": "true",
            "inferSchema": "true",
            "mode": "PERMISSIVE"  # Keep bad records for investigation
        }
    )

    return df


# ============================================================================
# EXAMPLE 2: Manual Metadata Addition
# ============================================================================

@pipeline(sources={}, target=OrdersBronze)
def ingest_orders_manual_metadata():
    """
    Manually add metadata for custom ingestion scenarios.
    """
    spark = get_spark_session()

    # Read raw CSV without helper
    raw_df = spark.read.csv(
        "s3://landing-zone/orders.csv",
        header=True,
        inferSchema=True
    )

    # Add Bronze metadata manually
    bronze_df = add_bronze_metadata(
        raw_df,
        source_system="sales_db",
        source_file="orders_2024_01_15.csv",
        custom_metadata={
            "_batch_id": "batch_20240115_001",
            "_data_owner": "sales_team"
        }
    )

    return bronze_df


# ============================================================================
# EXAMPLE 3: JSON Ingestion
# ============================================================================

class EventsBronze(BronzeTable):
    """Raw events from API."""

    event_id = StringField(nullable=False)
    event_type = StringField(nullable=False)
    user_id = StringField(nullable=True)
    timestamp = TimestampField(nullable=True)
    payload = StringField(nullable=True)  # JSON string

    # Metadata
    _ingested_at = TimestampField(nullable=True)
    _source_system = StringField(nullable=True)
    _source_file = StringField(nullable=True)

    class Meta:
        partition_by = ["timestamp"]
        description = "Raw events from API"


@pipeline(sources={}, target=EventsBronze)
def ingest_events_json():
    """Load JSON events into Bronze."""
    spark = get_spark_session()

    df = load_json_to_bronze(
        spark,
        source_path="s3://landing-zone/events/*.json",
        source_system="event_api",
        multiline=True  # Each file is one JSON object
    )

    return df


# ============================================================================
# EXAMPLE 4: Parquet Ingestion
# ============================================================================

class ExportsBronze(BronzeTable):
    """Raw exports from external system."""

    export_id = StringField(nullable=False)
    data = StringField(nullable=True)
    exported_at = TimestampField(nullable=True)

    # Metadata
    _ingested_at = TimestampField(nullable=True)
    _source_system = StringField(nullable=True)
    _source_file = StringField(nullable=True)

    class Meta:
        description = "Raw exports from external system"


@pipeline(sources={}, target=ExportsBronze)
def ingest_parquet_exports():
    """Load Parquet exports into Bronze."""
    spark = get_spark_session()

    df = load_parquet_to_bronze(
        spark,
        source_path="s3://landing-zone/exports/*.parquet",
        source_system="external_system"
    )

    return df


# ============================================================================
# EXAMPLE 5: Bad Records Handling
# ============================================================================

@pipeline(sources={}, target=OrdersBronze)
def ingest_orders_with_error_handling():
    """
    Handle bad/corrupted records during ingestion.

    Best practice:
    - Save bad records to separate location for investigation
    - Continue processing good records
    - Alert data engineers about bad records
    """
    spark = get_spark_session()

    # Read CSV in PERMISSIVE mode (bad records go to _corrupt_record column)
    raw_df = spark.read.csv(
        "s3://landing-zone/orders/*.csv",
        header=True,
        mode="PERMISSIVE"  # Creates _corrupt_record column
    )

    # Handle bad records
    clean_df = handle_bad_records(
        raw_df,
        bad_records_path="s3://errors/bronze/orders/",
        filter_corrupted=True  # Remove bad records from main flow
    )

    # Add metadata to clean records
    bronze_df = add_bronze_metadata(
        clean_df,
        source_system="sales_db",
        source_file="orders.csv"
    )

    return bronze_df


# ============================================================================
# EXAMPLE 6: Incremental Loading
# ============================================================================

@pipeline(sources={}, target=OrdersBronze)
def ingest_orders_incremental():
    """
    Incrementally load only new files.

    Use case: Daily file drops where you only want to process new files.
    Watermark tracking prevents reprocessing the same files.
    """
    spark = get_spark_session()

    # Initialize incremental loader
    loader = IncrementalLoader(
        spark,
        watermark_table="bronze_watermarks",
        watermark_path="s3://alur-datalake/watermarks/"
    )

    # Define loader function
    def load_orders_file(file_path: str):
        return load_csv_to_bronze(
            spark,
            source_path=file_path,
            source_system="sales_db",
            options={"header": "true", "inferSchema": "true"}
        )

    # Load only new files since last run
    df = loader.load_new_files(
        source_path="s3://landing-zone/orders/*.csv",
        source_name="orders_daily",
        loader_fn=load_orders_file,
        watermark_pattern="filename"
    )

    if df is None:
        # No new files to process
        spark = get_spark_session()
        return spark.createDataFrame([], OrdersBronze.to_iceberg_schema())

    return df


# ============================================================================
# EXAMPLE 7: Multiple Source Systems
# ============================================================================

@pipeline(sources={}, target=OrdersBronze)
def ingest_orders_multi_source():
    """
    Combine data from multiple source systems into one Bronze table.

    Track source system in metadata to distinguish origins.
    """
    spark = get_spark_session()

    # Load from sales database
    sales_df = load_csv_to_bronze(
        spark,
        source_path="s3://landing-zone/sales/*.csv",
        source_system="sales_db"
    )

    # Load from POS system
    pos_df = load_csv_to_bronze(
        spark,
        source_path="s3://landing-zone/pos/*.csv",
        source_system="pos_system"
    )

    # Load from mobile app
    mobile_df = load_json_to_bronze(
        spark,
        source_path="s3://landing-zone/mobile/*.json",
        source_system="mobile_app",
        multiline=True
    )

    # Combine all sources (Bronze accepts all raw data)
    combined_df = sales_df.union(pos_df).union(mobile_df)

    return combined_df


# ============================================================================
# EXAMPLE 8: Custom Metadata Fields
# ============================================================================

@pipeline(sources={}, target=OrdersBronze)
def ingest_orders_custom_metadata():
    """
    Add custom metadata fields for advanced tracking.
    """
    spark = get_spark_session()

    import os
    from datetime import datetime

    # Read raw data
    raw_df = spark.read.csv(
        "s3://landing-zone/orders.csv",
        header=True,
        inferSchema=True
    )

    # Add custom metadata
    bronze_df = add_bronze_metadata(
        raw_df,
        source_system="sales_db",
        source_file="orders.csv",
        custom_metadata={
            "_environment": os.getenv("ENV", "dev"),
            "_ingestion_job_id": os.getenv("AWS_BATCH_JOB_ID", "local"),
            "_data_classification": "pii",
            "_retention_days": 2555,  # 7 years
            "_processed_by": "alur_framework",
            "_ingestion_version": "1.0"
        }
    )

    return bronze_df


# ============================================================================
# Usage Notes
# ============================================================================

"""
BRONZE LAYER BEST PRACTICES:

1. RAW DATA ONLY
   - No transformations
   - No filtering
   - No business logic
   - Keep everything as-is

2. ADD METADATA
   - _ingested_at: When data arrived
   - _source_system: Where it came from
   - _source_file: Original file name
   - Custom fields: Batch ID, environment, etc.

3. FORMAT CONVERSION
   - CSV/JSON → Parquet (OK, just format change)
   - Keep same data values

4. APPEND ONLY
   - Never delete from Bronze
   - Immutable audit trail
   - Can reprocess anytime

5. BAD RECORDS
   - Save to separate location
   - Don't discard silently
   - Investigate and fix source

6. PARTITIONING
   - Partition by date/time for efficiency
   - Helps with incremental processing
   - Makes queries faster

SILVER LAYER is where you:
- Clean the data
- Filter out bad records
- Apply business rules
- Deduplicate
- Standardize formats

BRONZE → SILVER pipeline example:

@pipeline(sources={"orders": OrdersBronze}, target=OrdersSilver)
def clean_orders(orders):
    # Now we can transform!
    cleaned = orders.filter(
        (F.col("order_id").isNotNull()) &
        (F.col("amount") > 0) &
        (F.col("_corrupt_record").isNull())
    )

    # Drop Bronze metadata (not needed in Silver)
    cleaned = cleaned.drop("_ingested_at", "_source_system", "_source_file")

    # Apply business logic
    return cleaned.withColumn(
        "amount_usd",
        F.col("amount") / 100.0
    )
"""
