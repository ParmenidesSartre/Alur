# Bronze Layer Ingestion - Usage Guide

**Version**: v0.9.0 (Simplified Design)
**Last Updated**: 2026-02-05

---

## Quick Start

### Basic Bronze Ingestion

The simplest way to ingest CSV files into the bronze layer:

```python
from alur import pipeline, get_spark_session
from alur.ingestion import load_to_bronze
from contracts.bronze import OrdersBronze

@pipeline(sources={}, target=OrdersBronze)
def ingest_orders():
    spark = get_spark_session()

    return load_to_bronze(
        spark,
        source_path="s3://landing-zone/orders/*.csv",
        source_system="sales_db",
        target=OrdersBronze
    )
```

**What happens automatically:**
- ✅ Files tracked via Glue Job Bookmarks (no duplicates on retry)
- ✅ Schema validation against `OrdersBronze` contract
- ✅ Metadata added (_ingested_at, _source_system, _source_file)
- ✅ Data written as Parquet with partitioning

---

## Common Use Cases

### 1. Multi-Source Ingestion

Ingest from multiple S3 locations in a single pipeline:

```python
@pipeline(sources={}, target=OrdersBronze)
def ingest_orders_all_sources():
    spark = get_spark_session()

    return load_to_bronze(
        spark,
        source_path=[
            "s3://landing-zone/prod/orders/*.csv",
            "s3://landing-zone/staging/orders/*.csv",
            "s3://archive/2024/orders/*.csv"
        ],
        source_system="sales_db",
        target=OrdersBronze
    )
```

**Best for:**
- Consolidating data from multiple regions
- Including historical archive data
- Handling late-arriving files

**Note:** Idempotency is handled by Glue Job Bookmarks automatically.

---

### 2. Lenient Mode (Skip Bad Files)

For unreliable data sources, skip bad files instead of failing:

```python
@pipeline(sources={}, target=OrdersBronze)
def ingest_orders_lenient():
    spark = get_spark_session()

    return load_to_bronze(
        spark,
        source_path="s3://external-vendor/orders/*.csv",
        source_system="vendor_system",
        target=OrdersBronze,
        strict_mode=False  # Skip files with schema errors
    )
```

**Behavior:**
- Files with missing required columns → Skip, log warning
- Files with type mismatches → Skip, log warning
- Good files → Process normally

**Check logs:**
```
WARNING: Skipped 2 files due to schema validation failures:
  - s3://bucket/bad1.csv: Missing required columns: ['customer_id']
  - s3://bucket/bad2.csv: Type mismatch 'amount': expected integer, got string
```

---

### 3. Custom Metadata

Add custom tracking fields to bronze data:

```python
@pipeline(sources={}, target=OrdersBronze)
def ingest_orders_with_metadata():
    spark = get_spark_session()

    return load_to_bronze(
        spark,
        source_path="s3://landing-zone/orders/*.csv",
        source_system="sales_db",
        target=OrdersBronze,
        custom_metadata={
            "_batch_id": "2024-01-15-001",
            "_pipeline_version": "v2.3.0",
            "_data_owner": "sales_team",
            "_compliance_flag": "pii_present"
        }
    )
```

**Result DataFrame:**
```
+----------+------------+----------------+--------------------+---------------------+
| order_id | amount     | _ingested_at   | _batch_id          | _pipeline_version   |
+----------+------------+----------------+--------------------+---------------------+
| ORD001   | 99.99      | 2024-01-15...  | 2024-01-15-001     | v2.3.0              |
+----------+------------+----------------+--------------------+---------------------+
```

---

### 4. Idempotency via Glue Job Bookmarks

Idempotency is handled automatically by **AWS Glue Job Bookmarks**. Enable bookmarks in your Glue job configuration:

```python
# In your Glue job script
from awsglue.context import GlueContext
from awsglue.job import Job

glueContext = GlueContext(SparkContext.getOrCreate())
job = Job(glueContext)
job.init(args['JOB_NAME'], args)

# Your pipeline code here...

job.commit()  # Commits the bookmark
```

**How it works:**
- Glue tracks which files have been processed
- Re-running the job only processes new files
- No custom state management needed

---

### 5. Custom CSV Options

Handle non-standard CSV formats:

```python
@pipeline(sources={}, target=OrdersBronze)
def ingest_legacy_csv():
    spark = get_spark_session()

    return load_to_bronze(
        spark,
        source_path="s3://legacy-system/data/*.csv",
        source_system="legacy_erp",
        target=OrdersBronze,
        options={
            "delimiter": "|",              # Pipe-delimited
            "quote": '"',                  # Quote character
            "escape": "\\",                # Escape character
            "encoding": "ISO-8859-1",      # Latin-1 encoding
            "mode": "DROPMALFORMED",       # Drop bad rows
            "dateFormat": "dd-MM-yyyy",    # Custom date format
            "ignoreLeadingWhiteSpace": "true",
            "ignoreTrailingWhiteSpace": "true"
        }
    )
```

---

## Advanced Patterns

### Pattern 1: Incremental Processing with Date Ranges

```python
from datetime import datetime, timedelta

@pipeline(sources={}, target=OrdersBronze)
def ingest_orders_incremental():
    spark = get_spark_session()

    # Generate path for today's files
    today = datetime.now().strftime("%Y-%m-%d")
    source_path = f"s3://landing-zone/orders/{today}/*.csv"

    return load_to_bronze(
        spark,
        source_path=source_path,
        source_system="sales_db",
        target=OrdersBronze
    )
```

### Pattern 2: Error Notification

```python
import logging

@pipeline(sources={}, target=OrdersBronze)
def ingest_orders_with_alerts():
    spark = get_spark_session()
    logger = logging.getLogger(__name__)

    try:
        df = load_to_bronze(
            spark,
            source_path="s3://landing-zone/orders/*.csv",
            source_system="sales_db",
            target=OrdersBronze,
            strict_mode=True  # Fail on errors
        )
        return df

    except Exception as e:
        logger.error(f"Bronze ingestion failed: {str(e)}")
        # Send alert (SNS, email, Slack, etc.)
        send_alert(f"Orders ingestion failed: {str(e)}")
        raise  # Re-raise for Glue job failure
```

### Pattern 3: Conditional Processing

```python
@pipeline(sources={}, target=OrdersBronze)
def ingest_orders_conditional():
    spark = get_spark_session()

    # Check if new files exist
    from alur.utils.aws_helpers import AWSClientFactory
    s3_client = AWSClientFactory.get_s3_client()

    response = s3_client.list_objects_v2(
        Bucket='landing-zone',
        Prefix='orders/',
        MaxKeys=1
    )

    if 'Contents' not in response:
        logger.info("No files to process, skipping")
        return create_empty_dataframe(spark, target=OrdersBronze)

    # Files exist, proceed with ingestion
    return load_to_bronze(
        spark,
        source_path="s3://landing-zone/orders/*.csv",
        source_system="sales_db",
        target=OrdersBronze
    )
```

---

## Monitoring & Troubleshooting

### Check Ingestion State

Glue Job Bookmarks are managed automatically. To check processed files, query the bronze layer:

```sql
-- Query Athena to see processed files
SELECT
    _source_file,
    MIN(_ingested_at) as first_ingested,
    COUNT(*) as row_count
FROM bronze_layer.orders
GROUP BY _source_file
ORDER BY first_ingested DESC;
```

### Check Glue Job Bookmark Status

Use AWS CLI or console to check bookmark state:

```bash
# Get job bookmark
aws glue get-job-bookmark --job-name "your-glue-job-name"

# Reset bookmark (to reprocess all files)
aws glue reset-job-bookmark --job-name "your-glue-job-name"
```

### Check Row Counts

Verify row counts in Athena:

```sql
-- Query Athena for bronze data
SELECT
    _source_file,
    COUNT(*) as row_count
FROM bronze_layer.orders
GROUP BY _source_file
ORDER BY row_count DESC;
```

### Debug Schema Validation Failures

Enable detailed logging:

```python
import logging
logging.getLogger('alur.ingestion').setLevel(logging.DEBUG)

df = load_to_bronze(
    spark,
    source_path="s3://bucket/*.csv",
    source_system="sales",
    target=OrdersBronze,
    strict_mode=False,  # See all errors without failing
    validate=True
)

# Check logs for detailed validation errors:
# "Schema validation failed for s3://bucket/file.csv: Missing required columns: ['customer_id']"
```

---

## Best Practices

### ✅ DO

1. **Enable Glue Job Bookmarks for production**
   - Configure bookmarks in your Glue job settings
   - Always call `job.commit()` at the end of successful runs

2. **Set strict_mode=True for critical data**
   ```python
   strict_mode=True  # Fail fast on errors
   ```

3. **Add custom metadata for governance**
   ```python
   custom_metadata={"_data_owner": "team_name"}
   ```

4. **Monitor Glue job runs via CloudWatch**

5. **Use contract-based schema validation**
   ```python
   target=OrdersBronze,
   validate=True
   ```

### ❌ DON'T

1. **Don't forget to call job.commit()**
   ```python
   # ❌ Bad: Bookmark won't be saved
   # Missing job.commit()
   ```

2. **Don't skip schema validation in production**
   ```python
   validate=False  # ❌ May allow bad data
   ```

3. **Don't use batch_ingestion.py (deprecated)**
   ```python
   from alur.batch_ingestion import ingest_csv_sources_to_bronze  # ❌ Deprecated
   ```

---

## Performance Tuning

### For Large Files (>1GB)

```python
df = load_to_bronze(
    spark,
    source_path="s3://bucket/large_files/*.csv",
    source_system="sales",
    target=OrdersBronze,
    options={
        "maxPartitionBytes": "134217728",  # 128MB partitions
        "maxRecordsPerFile": "1000000"      # Limit records per output file
    }
)
```

### For Many Small Files (>1000)

```python
# Use broader wildcard patterns to let Spark optimize
df = load_to_bronze(
    spark,
    source_path="s3://bucket/orders/*/*.csv",  # Broader pattern
    source_system="sales",
    target=OrdersBronze
)
```

### For Wide Tables (>100 columns)

```python
df = load_to_bronze(
    spark,
    source_path="s3://bucket/*.csv",
    source_system="sales",
    target=OrdersBronze,
    options={
        "columnNameOfCorruptRecord": "_corrupt_record",  # Capture bad rows
        "mode": "PERMISSIVE"                              # Don't fail on corrupt rows
    }
)
```

---

## FAQ

**Q: What happens if a file is updated (same path, different content)?**
A: Glue Job Bookmarks track by file path and modification time. Updated files are automatically re-processed.

**Q: How do I force re-ingestion of all files?**
A: Reset the Glue Job Bookmark: `aws glue reset-job-bookmark --job-name "job-name"`

**Q: Can I use load_to_bronze without Spark?**
A: No, Spark is required for data processing.

**Q: Does idempotency work across different Glue jobs?**
A: Job Bookmarks are per-job. Each job tracks its own state.

**Q: What if my job fails mid-run?**
A: The bookmark is only committed on `job.commit()`. Failed jobs can be safely re-run.

---

## Migration from batch_ingestion.py

**Quick Reference:**

```python
# OLD (deprecated)
from alur.batch_ingestion import S3CsvSource, ingest_csv_sources_to_bronze
sources = [S3CsvSource("s3://bucket/*.csv", source_system="sales")]
report = ingest_csv_sources_to_bronze(sources, contract=OrdersBronze, bronze_bucket="alur-bronze")

# NEW (recommended)
from alur.ingestion import load_to_bronze
df = load_to_bronze(spark, "s3://bucket/*.csv", "sales", OrdersBronze)
```

---

## Next Steps

1. **Try the Quick Start example** above
2. **Enable Glue Job Bookmarks** in your job configuration
3. **Consider migrating from batch_ingestion.py** if used
4. **Set up CloudWatch monitoring** for your Glue jobs
