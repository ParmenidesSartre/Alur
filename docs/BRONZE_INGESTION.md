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

## Production Features

Alur's bronze ingestion includes production-grade features for reliability and cost-effectiveness:

### 1. Schema Validation

Validate incoming data against table contracts before loading:

```python
df = load_to_bronze(
    spark,
    source_path="s3://landing/orders/*.csv",
    source_system="sales_db",
    target=OrdersBronze,  # Validates schema
    strict_mode=True      # Fail on mismatch
)
```

**Benefits:**
- Catch schema changes early (before bad data enters lake)
- Fail-fast prevents expensive downstream errors
- Clear error messages for troubleshooting

### 2. Built-in Logging & Metrics

Automatic logging of ingestion metrics:

```
INFO: Starting bronze ingestion from s3://landing/orders/*.csv
INFO: Source system: sales_db, Target: OrdersBronze
INFO: Detected format: csv
INFO: Bronze ingestion completed successfully
INFO: Rows loaded: 15,000
INFO: Duration: 12.34s
INFO: Throughput: 1,215 rows/sec
INFO: Marked file as processed in state tracker
```

---

## Standard Bronze Metadata

Every Bronze table includes these metadata fields:

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

### 1. Define Bronze Table Contract

```python
from alur.core import BronzeTable, StringField, IntegerField, TimestampField

class OrdersBronze(BronzeTable):
    """Raw orders from sales system."""

    order_id = StringField(nullable=False)
    customer_id = StringField(nullable=False)
    amount = IntegerField(nullable=True)
    created_at = TimestampField(nullable=True)

    # Metadata fields (added automatically by load_to_bronze)
    _ingested_at = TimestampField(nullable=True)
    _source_system = StringField(nullable=True)
    _source_file = StringField(nullable=True)

    class Meta:
        partition_by = ["created_at"]
        description = "Raw orders from sales database"
```

### 2. Create Production Ingestion Pipeline

```python
from alur.decorators import pipeline
from alur.ingestion import load_to_bronze
from alur.engine import get_spark_session

@pipeline(sources={}, target=OrdersBronze)
def ingest_orders():
    """
    Production pattern: Bronze ingestion with schema validation.
    """
    spark = get_spark_session()

    df = load_to_bronze(
        spark,
        source_path="s3://landing-zone/orders/*.csv",
        source_system="sales_db",
        target=OrdersBronze,       # Schema validation
        validate=True,             # Enable validation
        strict_mode=True,          # Fail on schema mismatch
    )

    return df
```

### 3. Deploy and Run

```bash
# Deploy to AWS
alur deploy --env dev

# Trigger manually:
alur run ingest_orders

# View logs
alur logs ingest_orders
```

---

## API Reference

### `load_to_bronze()`

Unified function for loading data into Bronze layer with automatic metadata and safety features.

```python
def load_to_bronze(
    spark: SparkSession,
    source_path: str,
    source_system: str,
    target: Optional[Type] = None,
    format: Optional[str] = None,
    options: Optional[Dict[str, str]] = None,
    schema: Optional[StructType] = None,
    exclude_metadata: Optional[List[str]] = None,
    custom_metadata: Optional[Dict[str, Any]] = None,
    validate: bool = True,
    strict_mode: bool = True,
    check_duplicates: bool = True,
    force_reprocess: bool = False
) -> DataFrame:
```

**Parameters:**

- `spark` - SparkSession instance
- `source_path` - S3 or local path to files (supports wildcards: `*.csv`, `*.json`)
- `source_system` - Name of source system for metadata
- `target` - Table contract class for schema validation (e.g., `OrdersBronze`)
- `format` - File format ('csv', 'json', 'parquet'). Auto-detected if not provided.
- `options` - Format-specific reader options (e.g., `{"header": "true"}`)
- `schema` - Optional Spark schema for reading
- `exclude_metadata` - List of metadata columns to exclude
- `custom_metadata` - Dictionary of custom metadata to add
- `validate` - Enable schema validation against target (default: True)
- `strict_mode` - Fail on extra columns or type mismatches (default: True)
- `check_duplicates` - **NOT IMPLEMENTED** - Reserved for future idempotency feature (must keep default value True)
- `force_reprocess` - **NOT IMPLEMENTED** - Reserved for future feature (must keep default value False)

**Returns:** DataFrame with bronze metadata ready for loading

**Raises:** `SchemaValidationError` if validation fails in strict mode

**Supported Formats:**
- CSV (auto-detects from `.csv` extension)
- JSON (auto-detects from `.json` extension)
- Parquet (auto-detects from `.parquet` extension)

---

### `add_bronze_metadata()`

Manually add bronze metadata to any DataFrame.

```python
def add_bronze_metadata(
    df: DataFrame,
    source_system: Optional[str] = None,
    source_file: Optional[str] = None,
    exclude: Optional[List[str]] = None,
    custom_metadata: Optional[Dict[str, Any]] = None
) -> DataFrame:
```

**Parameters:**

- `df` - Input DataFrame
- `source_system` - Name of source system
- `source_file` - Source file identifier
- `exclude` - List of metadata columns to exclude (e.g., `["_source_file"]` for API data)
- `custom_metadata` - Dictionary of additional metadata fields

**Returns:** DataFrame with metadata columns added

---

### `validate_schema()`

Validate DataFrame schema against a table contract.

```python
def validate_schema(
    df: DataFrame,
    target: Type,
    strict_mode: bool = True,
    exclude_metadata: bool = False
) -> None:
```

**Parameters:**

- `df` - DataFrame to validate
- `target` - Table contract class (e.g., `OrdersBronze`)
- `strict_mode` - If True, fail on extra columns or type mismatches. If False, warn only.
- `exclude_metadata` - If True, ignore bronze metadata columns in validation

**Raises:** `SchemaValidationError` if validation fails in strict mode

---

## Common Patterns

### Pattern 1: CSV File Ingestion (RECOMMENDED)

```python
@pipeline(sources={}, target=OrdersBronze)
def ingest_orders():
    spark = get_spark_session()

    df = load_to_bronze(
        spark,
        source_path="s3://landing/orders/*.csv",
        source_system="sales_db",
        target=OrdersBronze,
        validate=True,
        strict_mode=True
    )

    return df
```

**Use when:** Ingesting CSV files from S3 with schema validation

### Pattern 2: API Data Ingestion

```python
@pipeline(sources={}, target=EventsBronze)
def ingest_api_events():
    spark = get_spark_session()

    # Read from API response files
    api_df = spark.read.json("s3://api-responses/events/*.json")

    # Exclude _source_file since this isn't from a file
    bronze_df = add_bronze_metadata(
        api_df,
        source_system="events_api",
        exclude=["_source_file"],
        custom_metadata={
            "_api_version": "v2",
            "_request_id": "req_12345"
        }
    )

    return bronze_df
```

**Use when:** Ingesting data from APIs, message queues, or non-file sources

### Pattern 3: Manual Control (Advanced)

```python
@pipeline(sources={}, target=OrdersBronze)
def ingest_orders_manual():
    spark = get_spark_session()

    # Custom read logic with specific options
    raw_df = spark.read.csv(
        "s3://landing/orders/*.csv",
        header=True,
        inferSchema=False,
        schema=custom_schema,
        mode="FAILFAST"
    )

    # Manual metadata addition
    bronze_df = add_bronze_metadata(
        raw_df,
        source_system="sales_db",
        source_file="orders_daily.csv",
        custom_metadata={"_batch_id": "batch_001"}
    )

    return bronze_df
```

**Use when:** Need fine-grained control over Spark reader options

---

## Cost Optimization for SMEs

### Understanding Bronze Ingestion Costs

Bronze ingestion costs come from:

1. **AWS Glue DPU-hours** - Compute for running Spark jobs
2. **S3 storage** - Storing Parquet files
3. **S3 requests** - Reading source files, writing results

### Cost-Saving Features

**1. Parquet format reduces storage costs:**

```
CSV: 1GB of data = $0.023/month
Parquet: Same data compressed to 200MB = $0.005/month (78% savings)
```

### Example: Monthly Cost for 1M Rows/Day

| Component | Without Parquet | With Parquet | Savings |
|-----------|-----------------|--------------|---------|
| Storage (CSV) | $7 | $1.50 (compression) | $5.50 |
| **Monthly Total** | **$7** | **$1.50** | **$5.50 (79% savings)** |

**Note:** Additional cost savings can be achieved by implementing your own idempotency logic to prevent duplicate processing.

---

## Troubleshooting

### Schema Validation Failed

**Error:**
```
SchemaValidationError: Missing required column 'customer_id'
```

**Solution:**
1. Check if source file format changed
2. Verify column names match exactly (case-sensitive)
3. For development, use `strict_mode=False` to see warnings instead of errors

### No Data Loaded

**Issue:** DataFrame is empty after `load_to_bronze()`

**Solutions:**
1. Verify S3 path is correct
2. Check if wildcard pattern matches files
3. Ensure AWS credentials have S3 read permissions
4. Check CloudWatch logs for errors

---

## Best Practices

### 1. Enable Schema Validation in Production

```python
# Production (strict)
df = load_to_bronze(..., target=OrdersBronze, strict_mode=True)

# Development (relaxed)
df = load_to_bronze(..., target=OrdersBronze, strict_mode=False)
```

### 2. Use Descriptive Source System Names

```python
# Good
source_system="salesforce_crm"
source_system="stripe_payments"
source_system="internal_hr_db"

# Bad
source_system="db1"
source_system="api"
source_system="data"
```

---

## Current Limitations

The following features are **not yet implemented** in the Spark-based `load_to_bronze()` function:

### 1. Idempotency / Duplicate Detection

**Status:** Not implemented

**Impact:** Files will be reprocessed every time the pipeline runs, potentially causing:
- Duplicate records in bronze tables
- Increased storage costs
- Wasted compute resources

**Workarounds:**
- Use the batch ingestion module (`alur.batch_ingestion.ingest_csv_sources_to_bronze()`) which has better support for batch processing
- Implement your own deduplication logic (e.g., check DynamoDB before processing)
- Use unique file paths and manual file management
- Add deduplication in Silver layer transformations

**Example of manual deduplication:**
```python
import boto3
from datetime import datetime

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('alur-ingestion-state')

def should_process_file(file_path: str) -> bool:
    """Check if file was already processed."""
    try:
        response = table.get_item(Key={'file_path': file_path})
        return 'Item' not in response
    except:
        return True

def mark_processed(file_path: str):
    """Mark file as processed."""
    table.put_item(Item={
        'file_path': file_path,
        'processed_at': datetime.utcnow().isoformat()
    })
```

### 2. Scheduled Execution

**Status:** Removed (was broken)

**Impact:** No automatic pipeline triggering via EventBridge

**Workarounds:**
- Use AWS EventBridge directly to trigger Glue jobs
- Use external schedulers (Airflow, Step Functions, cron)
- Manual triggering via `alur run <pipeline>`
- Use AWS Glue workflow triggers

### 3. Sample-Based Validation Only

**Status:** By design (in batch ingestion)

**Limitation:** CSV validation only checks first 50 rows by default

**Impact:** Schema errors in rows beyond the sample may go undetected

**Workarounds:**
- Increase `sample_rows` parameter (e.g., `sample_rows=1000`)
- Set `sample_rows=None` for full file validation (slower, more expensive)
- Rely on Spark schema enforcement to catch issues during read
- Add data quality checks in Silver layer

### 4. CSV-Only Support (for Spark-based ingestion)

**Status:** By design (AWS-only, batch-focused framework)

**Limitation:** Only CSV files from S3 are supported

**Workarounds:**
- Use Spark directly for other formats
- Convert files to CSV before ingestion
- Use batch ingestion for CSV, custom code for other formats

---

## Next Steps

After loading data into Bronze:

1. **Create Silver pipelines** - Transform and clean data
2. **Add data quality checks** - Use `@expect` decorator
3. **Set up monitoring** - Check CloudWatch logs
4. **Review costs** - Monitor AWS Glue DPU usage

See [Data Quality](DATA_QUALITY.md) for validation patterns.
