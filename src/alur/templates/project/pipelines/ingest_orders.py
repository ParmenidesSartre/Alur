"""
Bronze layer ingestion pipeline for orders.

This pipeline loads raw data into Bronze tables using Alur ingestion helpers.
Bronze philosophy: Raw data as-is + metadata. NO transformations.
"""

from alur.decorators import pipeline
from alur.ingestion import load_to_bronze
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

    # Load CSV files from S3 with automatic Bronze metadata
    df = load_to_bronze(
        spark,
        source_path="s3://landing-zone/orders/*.csv",
        source_system="sales_db",
        options={
            "header": "true",
            "inferSchema": "true",
            "mode": "PERMISSIVE"
        }
    )

    # No transformations - just return raw data with metadata
    return df

