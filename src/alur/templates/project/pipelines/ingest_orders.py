"""
Bronze layer ingestion pipeline for orders.

This pipeline loads raw data into Bronze tables using Alur ingestion helpers.
Bronze philosophy: Raw data as-is + metadata. NO transformations.
"""

from alur.decorators import pipeline
from alur.ingestion import load_csv_to_bronze
from alur.engine import get_spark_session
from contracts.bronze import OrdersBronze


@pipeline(sources={}, target=OrdersBronze)
def ingest_orders():
    """
    Load raw orders from landing zone into Bronze layer.

    Bronze ingestion:
    - Load raw data as-is (no transformations)
    - Add metadata (_ingested_at, _source_system, _source_file)
    - Keep all records (including bad ones for investigation)
    - Append-only mode

    Returns:
        DataFrame with raw orders + Bronze metadata
    """
    spark = get_spark_session()

    # Load CSV files with automatic Bronze metadata
    df = load_csv_to_bronze(
        spark,
        source_path="s3://landing-zone/orders/*.csv",
        source_system="sales_db",
        options={
            "header": "true",
            "inferSchema": "true",
            "mode": "PERMISSIVE"  # Keep bad records in _corrupt_record column
        }
    )

    # No transformations - just return raw data with metadata
    return df


# Alternative: Manual metadata addition for custom scenarios
@pipeline(sources={}, target=OrdersBronze)
def ingest_orders_manual():
    """
    Load orders with manual metadata control.
    """
    from alur.ingestion import add_bronze_metadata

    spark = get_spark_session()

    # Read CSV without helper
    raw_df = spark.read.csv(
        "s3://landing-zone/orders.csv",
        header=True,
        inferSchema=True
    )

    # Manually add Bronze metadata
    bronze_df = add_bronze_metadata(
        raw_df,
        source_system="sales_db",
        source_file="orders_daily.csv",
        custom_metadata={
            "_batch_id": "batch_001",
            "_environment": "production"
        }
    )

    return bronze_df
