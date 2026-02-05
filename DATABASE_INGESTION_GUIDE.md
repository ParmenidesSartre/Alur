# Database Ingestion for Bronze Layer

**Version**: v1.0.0
**Last Updated**: 2026-02-05

---

## Overview

Alur supports **database ingestion** for the bronze layer, allowing you to load data from relational databases (MySQL, PostgreSQL, SQL Server, Oracle) into your data lake with:

- **Incremental loading** via Glue Job Bookmarks (no custom state management)
- **Full table loads** for initial data or refresh
- **Secure credential management** via AWS Secrets Manager
- **Parallel reads** for large tables
- **Glue-native** — no DynamoDB, no S3 watermarks

---

## Quick Start

### 1. Define a Database Source

```python
from alur.ingestion.database import DatabaseSource, create_mysql_source

# Option A: Using convenience function
source = create_mysql_source(
    name="sales_db",
    host="mydb.cluster-xxx.us-east-1.rds.amazonaws.com",
    port=3306,
    database="salesdb",
    secret_name="prod/salesdb/credentials"  # AWS Secrets Manager
)

# Option B: Using DatabaseSource directly
source = DatabaseSource(
    name="sales_db",
    jdbc_url="jdbc:mysql://myhost:3306/salesdb",
    secret_name="prod/salesdb/credentials"
)
```

### 2. Load Data with Incremental Tracking

```python
from alur import pipeline
from alur.ingestion.database import load_from_database
from contracts.bronze import OrdersBronze
from awsglue.context import GlueContext

@pipeline(sources={}, target=OrdersBronze)
def ingest_orders_from_db(glue_context: GlueContext):
    return load_from_database(
        glue_context,
        source=source,
        table="orders",
        target=OrdersBronze,
        bookmark_keys=["updated_at"]
    )
```

### 3. That's It!

- First run: Loads all data, Glue stores bookmark at `MAX(updated_at)`
- Subsequent runs: Glue only reads rows beyond the bookmarked value
- Bookmark auto-commits with `job.commit()`

---

## Database Sources

### Supported Databases

| Database | Driver | Convenience Function |
|----------|--------|---------------------|
| MySQL | `com.mysql.cj.jdbc.Driver` | `create_mysql_source()` |
| PostgreSQL | `org.postgresql.Driver` | `create_postgresql_source()` |
| SQL Server | `com.microsoft.sqlserver.jdbc.SQLServerDriver` | `create_sqlserver_source()` |
| Oracle | `oracle.jdbc.OracleDriver` | Manual `DatabaseSource()` |
| Others | Any JDBC driver | Manual `DatabaseSource()` |

### Creating Sources

#### MySQL

```python
from alur.ingestion.database import create_mysql_source

source = create_mysql_source(
    name="sales_db",
    host="mydb.xxx.us-east-1.rds.amazonaws.com",
    port=3306,
    database="salesdb",
    secret_name="prod/salesdb/credentials"
)
```

#### PostgreSQL

```python
from alur.ingestion.database import create_postgresql_source

source = create_postgresql_source(
    name="analytics_db",
    host="analytics.xxx.us-east-1.rds.amazonaws.com",
    port=5432,
    database="analytics",
    secret_name="prod/analytics/credentials"
)
```

#### SQL Server

```python
from alur.ingestion.database import create_sqlserver_source

source = create_sqlserver_source(
    name="erp_db",
    host="erp-server.company.com",
    port=1433,
    database="ERPData",
    secret_name="prod/erp/credentials"
)
```

#### Generic JDBC

```python
from alur.ingestion.database import DatabaseSource

# Oracle example
source = DatabaseSource(
    name="oracle_db",
    jdbc_url="jdbc:oracle:thin:@//myhost:1521/ORCL",
    secret_name="prod/oracle/credentials",
    driver="oracle.jdbc.OracleDriver"
)
```

---

## Credential Management

### AWS Secrets Manager (Recommended)

Store credentials securely in AWS Secrets Manager:

```json
{
    "username": "readonly_user",
    "password": "your_secure_password"
}
```

Then reference by secret name:

```python
source = DatabaseSource(
    name="my_db",
    jdbc_url="jdbc:mysql://host:3306/db",
    secret_name="prod/mydb/credentials"  # Secret name in Secrets Manager
)
```

### Direct Credentials (Development Only)

For local development/testing only:

```python
source = DatabaseSource(
    name="my_db",
    jdbc_url="jdbc:mysql://localhost:3306/testdb",
    username="test_user",
    password="test_password"
)
```

**Warning**: Never use direct credentials in production!

---

## Incremental Loading

### How It Works

Incremental loading uses **Glue Job Bookmarks** with `jobBookmarkKeys`:

1. **First run**: Reads all rows, Glue stores `MAX(bookmark_key)` internally
2. **Next run**: Glue filters to only rows beyond the stored bookmark value
3. **On commit**: `job.commit()` persists the new bookmark

No custom watermark storage, no S3 files, no DynamoDB.

### Timestamp-Based Incremental

Best for tables with `created_at` or `updated_at` columns:

```python
df = load_from_database(
    glue_context,
    source=source,
    table="orders",
    target=OrdersBronze,
    bookmark_keys=["updated_at"]
)
```

### Integer-Based Incremental

Best for tables with auto-increment IDs:

```python
df = load_from_database(
    glue_context,
    source=source,
    table="events",
    target=EventsBronze,
    bookmark_keys=["event_id"]
)
```

### Date-Based Incremental

For tables with date columns:

```python
df = load_from_database(
    glue_context,
    source=source,
    table="daily_reports",
    target=ReportsBronze,
    bookmark_keys=["report_date"]
)
```

### Full Table Load

Omit `bookmark_keys` for full loads:

```python
df = load_from_database(
    glue_context,
    source=source,
    table="products",
    target=ProductsBronze
    # No bookmark_keys = full load every time
)
```

### Resetting Bookmarks

To re-process all data, reset the Glue Job Bookmark:

```bash
aws glue reset-job-bookmark --job-name "your-glue-job-name"
```

---

## Performance Optimization

### Parallel Reads

For large tables, use partitioned reads:

```python
df = load_from_database(
    glue_context,
    source=source,
    table="large_table",
    target=LargeTableBronze,
    partition_column="id",
    num_partitions=8,
    lower_bound=1,
    upper_bound=10000000
)
```

### Fetch Size

Tune JDBC fetch size for memory/performance tradeoff:

```python
df = load_from_database(
    glue_context,
    source=source,
    table="orders",
    target=OrdersBronze,
    fetch_size=50000  # Larger = faster but more memory (default: 10000)
)
```

### Column Selection

Only load needed columns:

```python
df = load_from_database(
    glue_context,
    source=source,
    table="orders",
    target=OrdersBronze,
    columns=["order_id", "customer_id", "amount", "created_at"],
    bookmark_keys=["created_at"]
)
```

---

## Complete Examples

### Example 1: Daily Incremental Sales Orders

```python
from alur import pipeline
from alur.ingestion.database import load_from_database, create_mysql_source
from contracts.bronze import OrdersBronze

# Define source
sales_db = create_mysql_source(
    name="sales_db",
    host="sales.xxx.rds.amazonaws.com",
    port=3306,
    database="sales",
    secret_name="prod/sales/credentials"
)

@pipeline(sources={}, target=OrdersBronze)
def ingest_sales_orders(glue_context):
    """
    Incremental ingestion of sales orders.
    Runs daily, only loads new/updated records via Job Bookmarks.
    """
    return load_from_database(
        glue_context,
        source=sales_db,
        table="orders",
        target=OrdersBronze,
        bookmark_keys=["updated_at"],
        custom_metadata={
            "_pipeline": "ingest_sales_orders",
            "_schedule": "daily"
        }
    )
```

### Example 2: Full Product Catalog Refresh

```python
from alur import pipeline
from alur.ingestion.database import load_from_database
from contracts.bronze import ProductsBronze

@pipeline(sources={}, target=ProductsBronze)
def refresh_product_catalog(glue_context):
    """
    Full refresh of product catalog.
    Products table is small, so full load is acceptable.
    """
    return load_from_database(
        glue_context,
        source=sales_db,
        table="products",
        target=ProductsBronze
        # No bookmark_keys = full load
    )
```

### Example 3: Large Table with Parallel Reads

```python
from alur import pipeline
from alur.ingestion.database import load_from_database
from contracts.bronze import EventsBronze

@pipeline(sources={}, target=EventsBronze)
def ingest_events(glue_context):
    """
    High-volume event ingestion with parallel reads.
    Uses 8 partitions for parallel database connections.
    """
    return load_from_database(
        glue_context,
        source=analytics_db,
        table="events",
        target=EventsBronze,
        bookmark_keys=["event_id"],
        partition_column="event_id",
        num_partitions=8,
        lower_bound=1,
        upper_bound=100000000,
        fetch_size=50000
    )
```

### Example 4: Multi-Database Consolidation

```python
from alur import pipeline
from alur.ingestion.database import load_from_database, create_mysql_source

# Define multiple sources
us_sales = create_mysql_source(name="us_sales", ...)
eu_sales = create_mysql_source(name="eu_sales", ...)
apac_sales = create_mysql_source(name="apac_sales", ...)

@pipeline(sources={}, target=GlobalOrdersBronze)
def consolidate_global_orders(glue_context):
    """
    Consolidate orders from multiple regional databases.
    Each source has independent bookmark tracking via transformation_ctx.
    """
    us_df = load_from_database(
        glue_context,
        source=us_sales,
        table="orders",
        target=GlobalOrdersBronze,
        bookmark_keys=["updated_at"],
        custom_metadata={"_region": "us"},
        transformation_ctx="db_us_orders"
    )

    eu_df = load_from_database(
        glue_context,
        source=eu_sales,
        table="orders",
        target=GlobalOrdersBronze,
        bookmark_keys=["updated_at"],
        custom_metadata={"_region": "eu"},
        transformation_ctx="db_eu_orders"
    )

    apac_df = load_from_database(
        glue_context,
        source=apac_sales,
        table="orders",
        target=GlobalOrdersBronze,
        bookmark_keys=["updated_at"],
        custom_metadata={"_region": "apac"},
        transformation_ctx="db_apac_orders"
    )

    # Union all regions
    return us_df.unionByName(eu_df).unionByName(apac_df)
```

---

## Metadata Columns

Database ingestion adds these metadata columns:

| Column | Type | Description |
|--------|------|-------------|
| `_ingested_at` | timestamp | Ingestion timestamp |
| `_source_system` | string | Database source name |
| `_source_table` | string | Source table name |
| `_source_file` | string | `jdbc://{source}/{table}` |
| `_ingestion_type` | string | `"incremental"` or `"full"` |

---

## Comparison: CSV vs Database Ingestion

| Feature | `load_to_bronze()` (CSV) | `load_from_database()` |
|---------|--------------------------|------------------------|
| Source | S3 CSV files | JDBC databases |
| Idempotency | Glue Job Bookmarks | Glue Job Bookmarks |
| Incremental | File-level tracking | `jobBookmarkKeys` column tracking |
| Parallel | Spark file reads | JDBC partition reads |
| Schema | Contract validation | Contract validation |
| Credentials | N/A | Secrets Manager |
| State storage | None (Glue internal) | None (Glue internal) |

---

## Troubleshooting

### Common Issues

**1. JDBC Driver Not Found**

```
java.lang.ClassNotFoundException: com.mysql.cj.jdbc.Driver
```

**Solution**: Add JDBC driver to Glue job's `--extra-jars` parameter:
```
--extra-jars s3://bucket/jars/mysql-connector-java-8.0.28.jar
```

**2. Connection Timeout**

```
Communications link failure
```

**Solution**: Check:
- Security group allows inbound from Glue VPC
- Database is in same VPC or accessible via VPC peering
- Add `connectTimeout` to connection properties

**3. Secret Not Found**

```
ResourceNotFoundException: Secrets Manager can't find the specified secret
```

**Solution**: Verify:
- Secret name is correct
- IAM role has `secretsmanager:GetSecretValue` permission
- Secret is in same region as Glue job

**4. Bookmark Not Advancing**

Ensure:
- `job.commit()` is called at the end of your Glue job script
- `bookmark_keys` column values are monotonically increasing
- Job bookmarks are enabled in the Glue job configuration

Reset bookmark to reprocess: `aws glue reset-job-bookmark --job-name "job-name"`

---

## IAM Permissions Required

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "secretsmanager:GetSecretValue"
            ],
            "Resource": "arn:aws:secretsmanager:*:*:secret:prod/*"
        }
    ]
}
```

No additional permissions needed for bookmark tracking — Glue manages this internally.

---

## Next Steps

- See [BRONZE_INGESTION_USAGE_GUIDE.md](BRONZE_INGESTION_USAGE_GUIDE.md) for CSV ingestion
