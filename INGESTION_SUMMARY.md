# Bronze Ingestion - Implementation Summary

## ✅ What Was Added

### Core Module
- `src/alur/ingestion/__init__.py` - Complete Bronze ingestion framework (~450 lines)

### Integration
- Modified `src/alur/__init__.py` - Export ingestion module

### Examples
- `examples/bronze_ingestion_examples.py` - 8 comprehensive examples

### Documentation
- `BRONZE_INGESTION.md` - Complete user guide
- `INGESTION_SUMMARY.md` - This file

---

## Quick Usage Examples

### 1. Simple CSV Ingestion

```python
from alur.core import BronzeTable, StringField, TimestampField
from alur.decorators import pipeline
from alur.ingestion import load_csv_to_bronze
from alur.engine import get_spark_session


class OrdersBronze(BronzeTable):
    order_id = StringField(nullable=False)
    amount = IntegerField(nullable=True)
    created_at = TimestampField(nullable=True)

    # Metadata fields (added automatically)
    _ingested_at = TimestampField(nullable=True)
    _source_system = StringField(nullable=True)
    _source_file = StringField(nullable=True)


@pipeline(sources={}, target=OrdersBronze)
def ingest_orders():
    spark = get_spark_session()

    df = load_csv_to_bronze(
        spark,
        source_path="s3://landing/orders/*.csv",
        source_system="sales_db",
        options={"header": "true", "inferSchema": "true"}
    )

    return df
```

### 2. Manual Metadata Addition

```python
from alur.ingestion import add_bronze_metadata

bronze_df = add_bronze_metadata(
    raw_df,
    source_system="sales_db",
    source_file="orders.csv",
    custom_metadata={
        "_batch_id": "batch_001",
        "_environment": "prod"
    }
)
```

### 3. JSON Ingestion

```python
from alur.ingestion import load_json_to_bronze

df = load_json_to_bronze(
    spark,
    source_path="s3://landing/events/*.json",
    source_system="event_api",
    multiline=True
)
```

### 4. Bad Records Handling

```python
from alur.ingestion import handle_bad_records

raw_df = spark.read.csv("data.csv", mode="PERMISSIVE")

clean_df = handle_bad_records(
    raw_df,
    bad_records_path="s3://errors/bronze/",
    filter_corrupted=True
)
```

### 5. Incremental Loading

```python
from alur.ingestion import IncrementalLoader

loader = IncrementalLoader(spark)

df = loader.load_new_files(
    source_path="s3://landing/orders/*.csv",
    source_name="orders_daily",
    loader_fn=lambda p: load_csv_to_bronze(spark, p, "sales_db")
)

if df is None:
    print("No new files to process")
```

---

## Built-in Helpers

| Helper Function | Purpose | Example |
|---|---|---|
| `add_bronze_metadata()` | Add standard metadata | `add_bronze_metadata(df, "sales_db", "file.csv")` |
| `load_csv_to_bronze()` | Load CSV with metadata | `load_csv_to_bronze(spark, path, "sales_db")` |
| `load_json_to_bronze()` | Load JSON with metadata | `load_json_to_bronze(spark, path, "api")` |
| `load_parquet_to_bronze()` | Load Parquet with metadata | `load_parquet_to_bronze(spark, path, "export")` |
| `handle_bad_records()` | Save/filter corrupted rows | `handle_bad_records(df, "s3://errors/")` |
| `IncrementalLoader` | Load only new files | `loader.load_new_files(...)` |

---

## Standard Bronze Metadata

Every Bronze table should include:

| Field | Type | Purpose |
|---|---|---|
| `_ingested_at` | Timestamp | When data was loaded |
| `_source_system` | String | Source system name |
| `_source_file` | String | Original filename |

Optional custom metadata:
- `_batch_id` - Job/batch identifier
- `_environment` - Environment (dev/prod)
- `_data_owner` - Owning team/system

---

## Bronze Layer Philosophy

### ✅ DO in Bronze

- ✅ Load raw data as-is
- ✅ Add ingestion metadata
- ✅ Convert format (CSV → Parquet)
- ✅ Keep all records (including bad ones)
- ✅ Append-only writes
- ✅ Partition by date/time

### ❌ DON'T in Bronze

- ❌ NO transformations
- ❌ NO filtering
- ❌ NO deduplication
- ❌ NO business logic
- ❌ NO data quality fixes
- ❌ NO aggregations

**Why?** Bronze is the immutable source of truth for auditing and reprocessing.

---

## Execution Flow

```
Source Files (S3/Local)
    ↓
Load with Helper Function
    ↓
Add Bronze Metadata
    ├─ _ingested_at
    ├─ _source_system
    └─ _source_file
    ↓
Handle Bad Records (optional)
    ├─ Save to errors/
    └─ Filter corrupted
    ↓
Write to Bronze Table
    └─ Append mode, Parquet format
    ↓
Ready for Silver Layer Processing
```

---

## Example Output

### Successful Ingestion

```
[Alur] Executing transformation: ingest_orders
[Alur] Loading CSV from s3://landing/orders/2024_01_15.csv
[Alur] Adding Bronze metadata: source_system=sales_db
[Alur] Writing to target: ordersbronze (mode=append)
[Alur] Loaded 1,234 rows
[Alur] Pipeline 'ingest_orders' completed successfully
```

### With Bad Records

```
[Alur] Executing transformation: ingest_orders
[Alur] Loading CSV from s3://landing/orders.csv
[Alur] Found 15 corrupted records
[Alur] Saving bad records to s3://errors/bronze/orders/
[Alur] Filtering corrupted records from main flow
[Alur] Writing 1,219 good records to Bronze
[Alur] Pipeline 'ingest_orders' completed successfully
[WARN] 15 bad records saved for investigation
```

### Incremental Load

```
[Alur] Executing transformation: ingest_orders_incremental
[Alur] Last watermark: orders_2024_01_14.csv
[Alur] Found 1 new file: orders_2024_01_15.csv
[Alur] Loading new file...
[Alur] Updating watermark to orders_2024_01_15.csv
[Alur] Pipeline completed successfully
```

---

## Real-World Example

```python
from alur.core import BronzeTable, StringField, IntegerField, TimestampField
from alur.decorators import pipeline
from alur.ingestion import (
    load_csv_to_bronze,
    handle_bad_records,
    IncrementalLoader
)
from alur.engine import get_spark_session


class OrdersBronze(BronzeTable):
    """Raw orders from sales database."""

    order_id = StringField(nullable=False)
    customer_id = StringField(nullable=False)
    product_id = StringField(nullable=True)
    quantity = IntegerField(nullable=True)
    amount = IntegerField(nullable=True)
    status = StringField(nullable=True)
    created_at = TimestampField(nullable=True)

    # Bronze metadata
    _ingested_at = TimestampField(nullable=True)
    _source_system = StringField(nullable=True)
    _source_file = StringField(nullable=True)

    class Meta:
        partition_by = ["created_at"]
        description = "Raw orders from sales database"


@pipeline(sources={}, target=OrdersBronze)
def ingest_daily_orders():
    """
    Load daily orders with:
    - Automatic metadata
    - Bad record handling
    - Incremental loading
    """
    spark = get_spark_session()

    # Setup incremental loader
    loader = IncrementalLoader(
        spark,
        watermark_path="s3://alur-datalake/watermarks/"
    )

    # Define loader function
    def load_orders_file(file_path: str):
        # Read CSV in PERMISSIVE mode
        raw_df = spark.read.csv(
            file_path,
            header=True,
            inferSchema=True,
            mode="PERMISSIVE"
        )

        # Handle bad records
        clean_df = handle_bad_records(
            raw_df,
            bad_records_path="s3://errors/bronze/orders/",
            filter_corrupted=True
        )

        # Add metadata
        from alur.ingestion import add_bronze_metadata
        bronze_df = add_bronze_metadata(
            clean_df,
            source_system="sales_db",
            source_file=file_path.split('/')[-1]
        )

        return bronze_df

    # Load only new files
    df = loader.load_new_files(
        source_path="s3://landing/orders/*.csv",
        source_name="orders_daily",
        loader_fn=load_orders_file,
        watermark_pattern="filename"
    )

    if df is None:
        # No new files - return empty DataFrame
        return spark.createDataFrame([], OrdersBronze.to_iceberg_schema())

    return df
```

---

## Features

### ✅ Standard Metadata
- Automatic tracking of ingestion time, source system, and file name
- Custom metadata support for advanced tracking

### ✅ Multiple Formats
- CSV ingestion with flexible options
- JSON ingestion (single-line and multiline)
- Parquet ingestion

### ✅ Error Handling
- Bad record detection with PERMISSIVE mode
- Separate storage for corrupted records
- Transparent error reporting

### ✅ Incremental Loading
- Watermark-based tracking
- Process only new files
- Efficient for daily/hourly drops

### ✅ Easy Integration
- Works seamlessly with `@pipeline` decorator
- Compatible with all Bronze tables
- Zero configuration needed

---

## Files Created

```
src/alur/ingestion/
  └── __init__.py              (~450 lines - complete ingestion module)

src/alur/
  └── __init__.py              (modified - export ingestion module)

examples/
  └── bronze_ingestion_examples.py   (8 comprehensive examples)

docs/
  ├── BRONZE_INGESTION.md      (complete user guide)
  └── INGESTION_SUMMARY.md     (this file)
```

---

## Next Steps

Users can now:

1. **Load CSV files** with automatic metadata using `load_csv_to_bronze()`
2. **Load JSON files** with automatic metadata using `load_json_to_bronze()`
3. **Add metadata manually** with `add_bronze_metadata()`
4. **Handle bad records** with `handle_bad_records()`
5. **Incremental loading** with `IncrementalLoader`
6. **Follow Bronze best practices** - raw data + metadata, no transformations

Bronze ingestion integrates seamlessly with:
- Contract definitions (BronzeTable schema)
- Pipeline transformations (Bronze → Silver)
- Quality checks (@expect decorator)
- EventBridge scheduling (@schedule decorator)
- All deployment environments (local/AWS)

---

## Benefits

### For Data Engineers
- Standard patterns for raw data ingestion
- Automatic metadata tracking
- Error handling built-in
- Incremental loading support

### For Data Analysts
- Reliable source of truth
- Complete data lineage
- Can reprocess from raw anytime
- Clear audit trail

### For DevOps
- Infrastructure as code
- Standardized ingestion patterns
- Error monitoring built-in
- Easy to schedule and automate

---

## Complete!

Bronze Ingestion helpers are now fully integrated into the Alur framework! 🎉

See [BRONZE_INGESTION.md](./BRONZE_INGESTION.md) for complete documentation.
