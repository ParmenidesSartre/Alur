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
    #
    # Multi-source support: Pass a list of S3 paths to ingest from multiple locations
    # source_path=[
    #     "s3://landing-zone/orders/*.csv",
    #     "s3://landing-zone/archive/orders/*.csv",
    #     "s3://landing-zone/backfill/orders/*.csv"
    # ]
    #
    # Idempotency: Enabled by default (enable_idempotency=True)
    # - Files are tracked in DynamoDB to prevent duplicate ingestion
    # - Re-running the pipeline will skip already-processed files
    # - Set enable_idempotency=False to reprocess all files
    df = load_to_bronze(
        spark,
        source_path="s3://landing-zone/orders/*.csv",
        source_system="sales_db",
        target=OrdersBronze,  # Required for schema validation and idempotency
        validate=True,  # Validate CSV headers match contract schema
        strict_mode=False,  # False: skip bad files, True: fail on bad files
        enable_idempotency=True,  # Track files to prevent duplicate ingestion
        options={
            "header": "true",
            "inferSchema": "true",
            "mode": "PERMISSIVE"
        }
    )

    # No transformations - just return raw data with metadata
    return df

