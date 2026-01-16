# Bronze Layer Ingestion - Alur Framework

## Overview

The Bronze layer is the **raw data landing zone** in the medallion architecture. It stores data exactly as received from source systems, with minimal processing and standard metadata for tracking.

## Bronze Layer Philosophy

### What Bronze IS

✅ **Raw data storage** - Data as-is from source systems
✅ **Format conversion** - CSV/JSON → Parquet (for efficiency)
✅ **Metadata addition** - Track when, where, how data arrived
✅ **Append-only** - Immutable audit trail
✅ **Complete history** - Keep everything, never delete

### What Bronze is NOT

❌ **NO transformations** - No business logic
❌ **NO filtering** - Keep bad records for investigation
❌ **NO deduplication** - Keep duplicates (fix in Silver)
❌ **NO data quality fixes** - Preserve source truth
❌ **NO aggregations** - Raw records only

### Why This Matters

**Bronze = Source of Truth for Auditing**

- Reprocess anytime if business logic changes
- Investigate data quality issues at the source
- Regulatory compliance and audit trails
- Disaster recovery and data lineage

---

## Standard Bronze Metadata

Every Bronze table should include these metadata fields:

| Field | Type | Purpose | Example |
|---|---|---|---|
| `_ingested_at` | Timestamp | When data was loaded | `2024-01-15 14:30:00` |
| `_source_system` | String | Where data came from | `sales_db`, `api`, `sftp` |
| `_source_file` | String | Original file name | `orders_20240115.csv` |

Optional custom metadata:
- `_batch_id` - Batch/job identifier
- `_environment` - Environment (dev/prod)
- `_data_owner` - Team/system responsible
- `_retention_days` - Data retention policy

---

## Quick Start

### 1. Basic CSV Ingestion

```python
from alur.core import BronzeTable, StringField, IntegerField, TimestampField
from alur.decorators import pipeline
from alur.ingestion import load_csv_to_bronze
from alur.engine import get_spark_session


class OrdersBronze(BronzeTable):
    """Raw orders from sales system."""

    order_id = StringField(nullable=False)
    customer_id = StringField(nullable=False)
    amount = IntegerField(nullable=True)
    created_at = TimestampField(nullable=True)

    # Metadata fields
    _ingested_at = TimestampField(nullable=True)
    _source_system = StringField(nullable=True)
    _source_file = StringField(nullable=True)

    class Meta:
        partition_by = ["created_at"]
        description = "Raw orders from sales database"


@pipeline(sources={}, target=OrdersBronze)
def ingest_orders():
    """Load orders CSV into Bronze."""
    spark = get_spark_session()

    df = load_csv_to_bronze(
        spark,
        source_path="s3://landing-zone/orders/*.csv",
        source_system="sales_db",
        options={"header": "true", "inferSchema": "true"}
    )

    return df
```

**What happens:**
1. Reads CSV files from S3
2. Adds `_ingested_at` (current timestamp)
3. Adds `_source_system` ("sales_db")
4. Adds `_source_file` (filename)
5. Returns DataFrame ready for Bronze

---

## Ingestion Helpers

### `add_bronze_metadata()`

Add standard metadata to any DataFrame.

```python
from alur.ingestion import add_bronze_metadata

bronze_df = add_bronze_metadata(
    df,
    source_system="sales_db",
    source_file="orders.csv",
    custom_metadata={
        "_batch_id": "batch_001",
        "_environment": "prod"
    }
)
```

**Parameters:**
- `df`: Input DataFrame
- `source_system`: Name of source system
- `source_file`: Source file identifier
- `custom_metadata`: Dict of additional metadata fields

**Returns:** DataFrame with metadata columns

---

### `load_csv_to_bronze()`

Load CSV files with automatic metadata.

```python
from alur.ingestion import load_csv_to_bronze

df = load_csv_to_bronze(
    spark,
    source_path="s3://landing/*.csv",
    source_system="sales_db",
    options={
        "header": "true",
        "inferSchema": "true",
        "mode": "PERMISSIVE"
    },
    add_metadata=True
)
```

**Parameters:**
- `spark`: SparkSession
- `source_path`: S3/local path (supports wildcards)
- `source_system`: Source system name
- `options`: CSV reader options
- `schema`: Optional explicit schema
- `add_metadata`: Add Bronze metadata (default True)

---

### `load_json_to_bronze()`

Load JSON files with automatic metadata.

```python
from alur.ingestion import load_json_to_bronze

df = load_json_to_bronze(
    spark,
    source_path="s3://landing/*.json",
    source_system="event_api",
    multiline=True
)
```

**Parameters:**
- `spark`: SparkSession
- `source_path`: S3/local path
- `source_system`: Source system name
- `multiline`: True for single JSON object per file
- `options`: JSON reader options
- `add_metadata`: Add Bronze metadata

---

### `load_parquet_to_bronze()`

Load Parquet files with automatic metadata.

```python
from alur.ingestion import load_parquet_to_bronze

df = load_parquet_to_bronze(
    spark,
    source_path="s3://landing/*.parquet",
    source_system="data_export"
)
```

---

### `handle_bad_records()`

Handle corrupted/malformed records.

```python
from alur.ingestion import handle_bad_records

# Read in PERMISSIVE mode (bad records → _corrupt_record column)
raw_df = spark.read.csv("data.csv", mode="PERMISSIVE")

# Save bad records and filter them out
clean_df = handle_bad_records(
    raw_df,
    bad_records_path="s3://errors/bad_records/",
    filter_corrupted=True
)
```

**Best Practice:**
- Always use `mode="PERMISSIVE"` when reading
- Save bad records for investigation
- Don't silently discard bad data

---

### `IncrementalLoader`

Load only new files since last run.

```python
from alur.ingestion import IncrementalLoader

loader = IncrementalLoader(
    spark,
    watermark_table="bronze_watermarks",
    watermark_path="s3://alur-datalake/watermarks/"
)

# Define how to load a single file
def load_file(path):
    return load_csv_to_bronze(spark, path, "sales_db")

# Load only new files
df = loader.load_new_files(
    source_path="s3://landing/orders/*.csv",
    source_name="orders_daily",
    loader_fn=load_file,
    watermark_pattern="filename"
)

if df is None:
    print("No new files to process")
```

**Watermarking:**
- Tracks last processed file/timestamp
- Prevents reprocessing same data
- Useful for daily/hourly file drops

---

## Common Patterns

### Pattern 1: Daily File Drops

Load daily CSV files from SFTP/S3.

```python
@pipeline(sources={}, target=OrdersBronze)
def ingest_daily_orders():
    """Load today's orders file."""
    spark = get_spark_session()

    from datetime import date
    today = date.today().strftime("%Y%m%d")

    df = load_csv_to_bronze(
        spark,
        source_path=f"s3://landing/orders_{today}.csv",
        source_system="sales_db"
    )

    return df
```

### Pattern 2: Multiple Source Systems

Combine data from different sources.

```python
@pipeline(sources={}, target=OrdersBronze)
def ingest_all_orders():
    """Load orders from all sources."""
    spark = get_spark_session()

    # Sales database
    sales_df = load_csv_to_bronze(
        spark, "s3://landing/sales/*.csv", "sales_db"
    )

    # POS system
    pos_df = load_csv_to_bronze(
        spark, "s3://landing/pos/*.csv", "pos_system"
    )

    # Combine (Bronze accepts all raw data)
    return sales_df.union(pos_df)
```

### Pattern 3: API Data Ingestion

Load JSON from REST API responses.

```python
@pipeline(sources={}, target=EventsBronze)
def ingest_api_events():
    """Load events from API dumps."""
    spark = get_spark_session()

    df = load_json_to_bronze(
        spark,
        source_path="s3://landing/api_events/*.json",
        source_system="event_api",
        multiline=True  # Each file is one JSON object
    )

    return df
```

### Pattern 4: Error Handling

Handle bad records gracefully.

```python
@pipeline(sources={}, target=OrdersBronze)
def ingest_orders_safe():
    """Load orders with error handling."""
    spark = get_spark_session()

    # Read with PERMISSIVE mode
    raw_df = spark.read.csv(
        "s3://landing/orders.csv",
        header=True,
        mode="PERMISSIVE"
    )

    # Save and filter bad records
    clean_df = handle_bad_records(
        raw_df,
        bad_records_path="s3://errors/orders/",
        filter_corrupted=True
    )

    # Add metadata
    bronze_df = add_bronze_metadata(
        clean_df,
        source_system="sales_db",
        source_file="orders.csv"
    )

    return bronze_df
```

### Pattern 5: Incremental Loading

Only process new files.

```python
@pipeline(sources={}, target=OrdersBronze)
def ingest_orders_incremental():
    """Load only new order files."""
    spark = get_spark_session()

    loader = IncrementalLoader(spark)

    df = loader.load_new_files(
        source_path="s3://landing/orders/*.csv",
        source_name="orders",
        loader_fn=lambda p: load_csv_to_bronze(spark, p, "sales_db")
    )

    if df is None:
        # No new files - return empty DataFrame
        return spark.createDataFrame([], OrdersBronze.to_iceberg_schema())

    return df
```

---

## Best Practices

### 1. ✅ Keep It Raw

```python
# GOOD: Raw data with metadata
@pipeline(sources={}, target=OrdersBronze)
def ingest_orders(orders):
    spark = get_spark_session()
    df = load_csv_to_bronze(spark, "s3://landing/orders.csv", "sales_db")
    return df  # Just metadata, no transformations

# BAD: Transformations in Bronze
@pipeline(sources={}, target=OrdersBronze)
def ingest_orders_bad(orders):
    spark = get_spark_session()
    df = load_csv_to_bronze(spark, "s3://landing/orders.csv", "sales_db")
    return df.filter(F.col("amount") > 0)  # ❌ Filtering belongs in Silver!
```

### 2. ✅ Always Add Metadata

```python
# GOOD: Standard metadata
bronze_df = add_bronze_metadata(
    raw_df,
    source_system="sales_db",
    source_file="orders.csv"
)

# BETTER: Custom metadata for tracking
bronze_df = add_bronze_metadata(
    raw_df,
    source_system="sales_db",
    source_file="orders.csv",
    custom_metadata={
        "_batch_id": batch_id,
        "_environment": env,
        "_data_owner": "sales_team"
    }
)
```

### 3. ✅ Handle Bad Records

```python
# GOOD: Save bad records for investigation
raw_df = spark.read.csv("data.csv", mode="PERMISSIVE")
clean_df = handle_bad_records(
    raw_df,
    bad_records_path="s3://errors/bronze/",
    filter_corrupted=True
)

# BAD: Silent failures
raw_df = spark.read.csv("data.csv", mode="DROPMALFORMED")  # ❌ Lost data!
```

### 4. ✅ Use Partitioning

```python
class OrdersBronze(BronzeTable):
    order_id = StringField(nullable=False)
    created_at = TimestampField(nullable=True)

    class Meta:
        partition_by = ["created_at"]  # ✅ Efficient queries
```

### 5. ✅ Incremental Processing

```python
# GOOD: Only process new files
loader = IncrementalLoader(spark)
df = loader.load_new_files(...)

# BAD: Reprocess everything every time
df = spark.read.csv("s3://landing/all_files/*.csv")  # ❌ Inefficient
```

---

## Bronze → Silver Pipeline

After loading to Bronze, create a Silver pipeline for cleaning:

```python
from alur.decorators import pipeline
from alur.quality import expect, not_empty, no_nulls_in_column

@expect(name="has_data", check_fn=not_empty)
@expect(name="no_null_ids", check_fn=no_nulls_in_column("order_id"))
@pipeline(sources={"orders": OrdersBronze}, target=OrdersSilver)
def clean_orders(orders):
    """
    Silver layer: Clean and validate Bronze data.

    Now we can:
    - Filter out bad records
    - Apply business rules
    - Deduplicate
    - Standardize formats
    """
    from pyspark.sql import functions as F

    # Filter valid records
    cleaned = orders.filter(
        (F.col("order_id").isNotNull()) &
        (F.col("amount") > 0) &
        (F.col("created_at").isNotNull())
    )

    # Drop Bronze metadata (not needed in Silver)
    cleaned = cleaned.drop("_ingested_at", "_source_system", "_source_file")

    # Apply business logic
    cleaned = cleaned.withColumn(
        "amount_usd",
        F.col("amount") / 100.0  # Convert cents to dollars
    )

    # Deduplicate by order_id (keep latest)
    from pyspark.sql.window import Window
    window = Window.partitionBy("order_id").orderBy(F.desc("created_at"))

    deduplicated = cleaned.withColumn(
        "rn", F.row_number().over(window)
    ).filter(F.col("rn") == 1).drop("rn")

    return deduplicated
```

---

## Architecture Overview

```
┌─────────────────────────────────────────────┐
│         Source Systems                      │
│  (Sales DB, APIs, SFTP, Files)             │
└──────────────┬──────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────┐
│         Landing Zone (S3)                   │
│  Raw files: CSV, JSON, Parquet              │
└──────────────┬──────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────┐
│  Ingestion Helpers (This Module)            │
│  - load_csv_to_bronze()                     │
│  - add_bronze_metadata()                    │
│  - handle_bad_records()                     │
└──────────────┬──────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────┐
│         BRONZE LAYER                        │
│  Raw data + metadata (Parquet)              │
│  - _ingested_at                             │
│  - _source_system                           │
│  - _source_file                             │
│  Append-only, immutable                     │
└──────────────┬──────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────┐
│         SILVER LAYER                        │
│  Cleaned, validated, deduplicated           │
│  Business rules applied                     │
└──────────────┬──────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────┐
│         GOLD LAYER                          │
│  Business-ready aggregates                  │
└─────────────────────────────────────────────┘
```

---

## Summary

Bronze layer ingestion helpers provide:

✅ **Standard metadata** - Track data lineage automatically
✅ **Easy file loading** - CSV, JSON, Parquet support
✅ **Error handling** - Save bad records for investigation
✅ **Incremental loading** - Process only new files
✅ **Best practices** - Built-in Bronze layer patterns

**Remember:** Bronze is raw data + metadata. All transformations happen in Silver and Gold layers!

See [`examples/bronze_ingestion_examples.py`](examples/bronze_ingestion_examples.py) for complete working examples.
