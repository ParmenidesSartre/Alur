# Silver Layer Implementation Plan

## Executive Summary

The Silver layer is the **cleansing and conformance** layer in the medallion architecture. This plan details implementing production-ready Silver layer capabilities in the Alur framework, focusing on the most critical operations: deduplication, data quality validation, schema enforcement, business logic application, and ACID guarantees via Iceberg MERGE operations.

**Current Status**: Silver layer core capabilities (SilverTable, MERGE, transformation utilities) are ✅ **FULLY IMPLEMENTED**. Critical gaps exist in infrastructure generation (Terraform) and templates.

---

## Part 1: What Silver Layer Does (Core Capabilities)

### 1.1 Deduplication
**Purpose**: Remove duplicate records arriving from Bronze, keeping latest/first/best record per business key.

**Implementation Status**: ✅ Complete
- `deduplicate()` function supports 3 strategies:
  - `latest`: Keep most recent by timestamp (default: `_ingested_at`)
  - `first`: Keep oldest record
  - `distinct`: Arbitrary deduplication (Spark dropDuplicates)
- Window function-based ranking for deterministic results
- Custom order_by column support

**Typical Use Cases**:
```python
# Keep latest order by order_id
df = deduplicate(df, keys=["order_id"], strategy="latest")

# Keep first customer record
df = deduplicate(df, keys=["customer_id"],
                 order_by=F.asc("created_at"),
                 strategy="first")
```

### 1.2 Data Quality Validation
**Purpose**: Enforce business rules, check completeness, validate data integrity.

**Implementation Status**: ✅ Complete (9 built-in checks)
- `@expect` decorator with severity levels (ERROR/WARN)
- Built-in checks:
  - `not_empty()`: Verify records exist
  - `min_row_count()` / `max_row_count()`: Row count boundaries
  - `no_nulls_in_column()`: Required field validation
  - `no_duplicates_in_column()`: Uniqueness constraints
  - `schema_has_columns()`: Schema completeness
  - `column_values_in_range()`: Numeric/date boundaries
  - `column_matches_pattern()`: Regex validation
  - `freshness_check()`: Staleness detection
  - `column_values_in_list()`: Enumeration validation

**Execution Flow**:
- Quality checks run AFTER data written to Silver table
- ERROR severity: Pipeline fails, blocks downstream
- WARN severity: Logs warning, pipeline continues
- Console output: ✓ (pass) / ✗ (fail) / ⚠ (warn)

**Typical Use Cases**:
```python
@pipeline(name="transform_orders", layer="silver")
@expect(not_empty(), severity="ERROR")
@expect(no_nulls_in_column("order_id"), severity="ERROR")
@expect(no_duplicates_in_column("order_id"), severity="ERROR")
@expect(column_values_in_range("total_amount", min_value=0), severity="WARN")
def transform_orders(spark: SparkSession) -> DataFrame:
    # Transformation logic
```

### 1.3 Schema Enforcement & Type Casting
**Purpose**: Convert Bronze string/variant types to strongly-typed Silver schemas.

**Implementation Status**: ✅ Complete
- `cast_types()` function with two modes:
  1. Contract-based: Reads schema from SilverTable class
  2. Manual: Dict mapping column → Spark type string
- Automatic casting from Iceberg schema definition
- Graceful handling of missing columns (only casts existing)

**Typical Use Cases**:
```python
# Using contract
df = cast_types(df, target=OrdersSilver)

# Manual mapping
df = cast_types(df, type_map={
    "amount": "decimal(10,2)",
    "created_at": "timestamp",
    "is_active": "boolean"
})
```

### 1.4 Data Cleansing & Normalization
**Purpose**: Fix data quality issues, normalize values, handle missing data.

**Implementation Status**: ✅ Complete
- `fill_nulls()`: Replace null values with defaults
- Supports complex fill strategies via dict mapping
- Preserves non-null values

**Typical Use Cases**:
```python
df = fill_nulls(df, {
    "status": "pending",
    "notes": "",
    "quantity": 0,
    "discount_pct": 0.0
})
```

### 1.5 Business Logic Application
**Purpose**: Apply derived columns, calculations, enrichments, transformations.

**Implementation Status**: ✅ Complete (via PySpark in pipeline functions)
- User-defined transformations in pipeline functions
- Access to full PySpark API
- Support for UDFs, window functions, joins

**Typical Use Cases**:
```python
df = df.withColumn("total_with_tax", F.col("subtotal") * 1.1)
df = df.withColumn("order_date", F.to_date("order_timestamp"))
df = df.withColumn("customer_segment",
    F.when(F.col("total_amount") > 1000, "VIP")
     .otherwise("Standard"))
```

### 1.6 Metadata Addition
**Purpose**: Track Silver layer lineage, transformation timestamps, source tables.

**Implementation Status**: ✅ Complete
- `add_silver_metadata()`: Adds standard Silver metadata columns
  - `_transformed_at`: Transformation execution timestamp
  - `_source_bronze_table`: Source Bronze table name
  - `_transformation_name`: Pipeline name that created record
- Generic `add_metadata_columns()` for custom metadata
- Exclude parameter for selective metadata

**Typical Use Cases**:
```python
df = add_silver_metadata(
    df,
    source_bronze_table="orders_bronze",
    transformation_name="transform_orders"
)
```

### 1.7 ACID Guarantees via Iceberg MERGE
**Purpose**: Enable idempotent writes, handle late-arriving updates, ensure exactly-once semantics.

**Implementation Status**: ✅ Complete
- Automatic MERGE INTO SQL generation in `AWSAdapter.write()`
- Smart table existence detection (catches AnalysisException)
- Supports UPDATE when matched, INSERT when not matched
- Primary key-based matching from SilverTable.primary_key
- Partition pruning optimization via SilverTable.partition_by

**MERGE SQL Generation** (src/alur/engine/adapter.py:250-308):
```sql
MERGE INTO catalog.database.table AS target
USING temp_view AS source
ON target.order_id = source.order_id
WHEN MATCHED THEN UPDATE SET *
WHEN NOT MATCHED THEN INSERT *
```

**Typical Use Cases**:
- Reprocessing Bronze data without duplicates
- Late-arriving fact updates (order status changes)
- Dimension updates (customer address changes)
- Idempotent pipeline reruns

---

## Part 2: Current Implementation Status

### 2.1 What's Already Complete ✅

**Core Framework** (src/alur/core/contracts.py):
- `SilverTable` class with Iceberg format
- `primary_key` property for MERGE key extraction
- `get_table_name()`, `get_database()` methods
- Schema definition via `@dataclass` + `to_iceberg_schema()`
- Partition specification support

**Transformation Utilities** (src/alur/transformation/__init__.py):
- ✅ `deduplicate()` - 3 strategies, window-based ranking
- ✅ `fill_nulls()` - dict-based null replacement
- ✅ `cast_types()` - contract or manual type casting
- ✅ `add_silver_metadata()` - standard Silver metadata columns
- ✅ `transform_to_silver()` - High-level helper combining all steps

**Iceberg MERGE** (src/alur/engine/adapter.py:250-308):
- ✅ SQL MERGE INTO generation
- ✅ Primary key extraction from target class
- ✅ Smart table existence check
- ✅ Temp view registration
- ✅ MERGE execution via Spark SQL

**Data Quality** (src/alur/quality/__init__.py):
- ✅ `@expect` decorator with severity levels
- ✅ 9 built-in quality checks
- ✅ QualityRegistry integration
- ✅ Pipeline execution with quality validation

**Templates** (src/alur/templates/project/):
- ✅ `contracts/silver.py` - Complete OrdersSilver example
- ✅ `pipelines/transform_orders.py` - Simple and advanced examples

### 2.2 Critical Gaps ⚠️

**Infrastructure Generation** (src/alur/infra/generator.py):
- ❌ Only generates `bronze_layer` Glue database
- ❌ No `silver_layer` or `gold_layer` database generation
- ❌ No Iceberg table definitions (generates Parquet CREATE TABLE instead)
- ❌ No SILVER_BUCKET or GOLD_BUCKET S3 resources
- ❌ Missing IAM permissions for Silver/Gold bucket access

**Layer Detection Bug** (src/alur/core/contracts.py:74):
```python
def get_layer(cls) -> str:
    if issubclass(cls, BronzeTable):
        return "bronze"
    # BUG: SilverTable/GoldTable not checked!
    return "unknown"  # Always returns "unknown" for Silver/Gold
```

**Configuration** (src/alur/config.py):
- ❌ No SILVER_BUCKET or GOLD_BUCKET environment variables
- ❌ No silver_layer or gold_layer database configuration

**Templates**:
- ❌ No Bronze→Silver→Gold multi-layer example
- ❌ No advanced quality check examples for Silver

---

## Part 3: Implementation Steps

### Step 1: Fix Layer Detection Bug
**File**: src/alur/core/contracts.py:74-77

**Current Code**:
```python
@classmethod
def get_layer(cls) -> str:
    if issubclass(cls, BronzeTable):
        return "bronze"
    return "unknown"
```

**Fixed Code**:
```python
@classmethod
def get_layer(cls) -> str:
    # Check in reverse order of inheritance (most specific first)
    if issubclass(cls, GoldTable):
        return "gold"
    elif issubclass(cls, SilverTable):
        return "silver"
    elif issubclass(cls, BronzeTable):
        return "bronze"
    return "unknown"
```

**Impact**: Enables layer-aware bucket selection, database naming, and Terraform generation.

---

### Step 2: Update Infrastructure Generator for Multi-Layer Support
**File**: src/alur/infra/generator.py

**Changes Required**:

#### 2.1: Add Silver/Gold Database Scanning
**Current** (lines 87-99): Only scans for BronzeTable
```python
def _find_contracts(cls, base_path: Path) -> Dict[str, List[Type]]:
    # Only finds BronzeTable contracts
    if issubclass(contract_class, BronzeTable):
        bronze_tables.append(contract_class)
```

**Updated**: Scan for all table types
```python
def _find_contracts(cls, base_path: Path) -> Dict[str, List[Type]]:
    bronze_tables = []
    silver_tables = []
    gold_tables = []

    # ... scanning logic ...

    if issubclass(contract_class, BronzeTable):
        bronze_tables.append(contract_class)
    elif issubclass(contract_class, SilverTable):
        silver_tables.append(contract_class)
    elif issubclass(contract_class, GoldTable):
        gold_tables.append(contract_class)

    return {
        "bronze": bronze_tables,
        "silver": silver_tables,
        "gold": gold_tables
    }
```

#### 2.2: Generate Silver/Gold Glue Databases
**Current** (lines 153-165): Only generates bronze_layer database
```python
resource "aws_glue_catalog_database" "bronze_layer" {
  name = "${var.project_name}_bronze_layer"
}
```

**Updated**: Generate all layer databases
```python
resource "aws_glue_catalog_database" "bronze_layer" {
  name        = "${var.project_name}_bronze_layer"
  description = "Bronze layer - raw ingested data (Parquet)"
}

resource "aws_glue_catalog_database" "silver_layer" {
  name        = "${var.project_name}_silver_layer"
  description = "Silver layer - cleaned and deduplicated data (Iceberg)"
}

resource "aws_glue_catalog_database" "gold_layer" {
  name        = "${var.project_name}_gold_layer"
  description = "Gold layer - aggregated business metrics (Iceberg)"
}
```

#### 2.3: Generate Iceberg Table Definitions
**Current**: Generates Parquet CREATE TABLE statements (not needed - Glue Catalog auto-populated)

**Updated**: Generate Iceberg table definitions for Silver/Gold
```python
def _generate_iceberg_table_tf(self, table: Type, layer: str) -> str:
    """Generate Terraform for Iceberg table (Silver/Gold only)."""
    table_name = table.get_table_name()
    database = f"{layer}_layer"

    # Get schema from contract
    schema = table.to_iceberg_schema()
    columns = []
    for field in schema.fields:
        columns.append(f'''    {{
      name = "{field.name}"
      type = "{field.dataType.simpleString()}"
    }}''')

    # Get partition columns
    partition_cols = []
    if hasattr(table, 'partition_by') and table.partition_by:
        for col in table.partition_by:
            partition_cols.append(f'    "{col}"')

    # Get primary key (for Iceberg)
    primary_key = []
    if hasattr(table, 'primary_key') and table.primary_key:
        for col in table.primary_key:
            primary_key.append(f'    "{col}"')

    return f'''
resource "aws_glue_catalog_table" "{table_name}" {{
  name          = "{table_name}"
  database_name = aws_glue_catalog_database.{database}.name

  table_type = "EXTERNAL_TABLE"

  parameters = {{
    "table_type"           = "ICEBERG"
    "format"              = "parquet"
    "write.format.default" = "parquet"
    "write.metadata.compression-codec" = "gzip"
  }}

  storage_descriptor {{
    location      = "s3://${{var.{layer}_bucket}}/{table_name}/"
    input_format  = "org.apache.iceberg.mr.hive.HiveIcebergInputFormat"
    output_format = "org.apache.iceberg.mr.hive.HiveIcebergOutputFormat"

    ser_de_info {{
      serialization_library = "org.apache.iceberg.mr.hive.HiveIcebergSerDe"
    }}

    columns = [
{chr(10).join(columns)}
    ]
  }}

{f"  partition_keys = [{chr(10)}{chr(10).join(partition_cols)}{chr(10)}  ]" if partition_cols else ""}
}}
'''
```

#### 2.4: Generate Silver/Gold S3 Buckets
**Current** (lines 119-136): Only generates bronze_bucket
```python
resource "aws_s3_bucket" "bronze_bucket" {
  bucket = "${var.project_name}-bronze-${data.aws_caller_identity.current.account_id}"

  tags = {
    Layer = "Bronze"
  }
}
```

**Updated**: Generate all layer buckets
```python
resource "aws_s3_bucket" "bronze_bucket" {
  bucket = "${var.project_name}-bronze-${data.aws_caller_identity.current.account_id}"

  tags = {
    Layer       = "Bronze"
    Description = "Raw ingested data (Parquet)"
  }
}

resource "aws_s3_bucket" "silver_bucket" {
  bucket = "${var.project_name}-silver-${data.aws_caller_identity.current.account_id}"

  tags = {
    Layer       = "Silver"
    Description = "Cleaned and deduplicated data (Iceberg)"
  }
}

resource "aws_s3_bucket" "gold_bucket" {
  bucket = "${var.project_name}-gold-${data.aws_caller_identity.current.account_id}"

  tags = {
    Layer       = "Gold"
    Description = "Aggregated business metrics (Iceberg)"
  }
}

# Bucket outputs for easy reference
output "bronze_bucket" {
  value = aws_s3_bucket.bronze_bucket.id
}

output "silver_bucket" {
  value = aws_s3_bucket.silver_bucket.id
}

output "gold_bucket" {
  value = aws_s3_bucket.gold_bucket.id
}
```

#### 2.5: Update IAM Permissions
**Current** (lines 220-232): Only grants access to bronze_bucket

**Updated**: Grant access to all layer buckets
```python
statement {
  sid    = "S3DataAccess"
  effect = "Allow"

  actions = [
    "s3:GetObject",
    "s3:PutObject",
    "s3:DeleteObject",
    "s3:ListBucket"
  ]

  resources = [
    aws_s3_bucket.bronze_bucket.arn,
    "${aws_s3_bucket.bronze_bucket.arn}/*",
    aws_s3_bucket.silver_bucket.arn,
    "${aws_s3_bucket.silver_bucket.arn}/*",
    aws_s3_bucket.gold_bucket.arn,
    "${aws_s3_bucket.gold_bucket.arn}/*"
  ]
}
```

#### 2.6: Update Terraform Variables
**Add** (in variables section):
```python
variable "silver_bucket" {
  description = "S3 bucket for Silver layer (optional override)"
  type        = string
  default     = ""
}

variable "gold_bucket" {
  description = "S3 bucket for Gold layer (optional override)"
  type        = string
  default     = ""
}
```

---

### Step 3: Update Configuration for Silver/Gold Buckets
**File**: src/alur/config.py

**Add** (after BRONZE_BUCKET):
```python
SILVER_BUCKET: str = os.getenv("SILVER_BUCKET", "")
GOLD_BUCKET: str = os.getenv("GOLD_BUCKET", "")
```

**Update _init_from_terraform()** to parse Silver/Gold bucket outputs:
```python
def _init_from_terraform(cls):
    # ... existing bronze_bucket parsing ...

    # Silver bucket
    if "silver_bucket" in outputs:
        cls.SILVER_BUCKET = outputs["silver_bucket"]["value"]
        os.environ["SILVER_BUCKET"] = cls.SILVER_BUCKET

    # Gold bucket
    if "gold_bucket" in outputs:
        cls.GOLD_BUCKET = outputs["gold_bucket"]["value"]
        os.environ["GOLD_BUCKET"] = cls.GOLD_BUCKET
```

---

### Step 4: Update RuntimeAdapter Bucket Selection
**File**: src/alur/engine/adapter.py:218-230

**Current**: Only handles Bronze layer
```python
def _get_s3_path(self, target: Type) -> str:
    layer = target.get_layer()
    if layer == "bronze":
        bucket = self.config.BRONZE_BUCKET
    else:
        raise ValueError(f"Unsupported layer: {layer}")
```

**Updated**: Handle all layers
```python
def _get_s3_path(self, target: Type) -> str:
    layer = target.get_layer()

    if layer == "bronze":
        bucket = self.config.BRONZE_BUCKET
    elif layer == "silver":
        bucket = self.config.SILVER_BUCKET
    elif layer == "gold":
        bucket = self.config.GOLD_BUCKET
    else:
        raise ValueError(f"Unknown layer '{layer}'. Expected: bronze, silver, gold")

    if not bucket:
        raise ValueError(f"{layer.upper()}_BUCKET not configured. Run 'alur deploy' or set environment variable.")

    table_name = target.get_table_name()
    return f"s3://{bucket}/{table_name}/"
```

---

### Step 5: Create Complete Bronze→Silver→Gold Example
**File**: src/alur/templates/project/pipelines/end_to_end_example.py (NEW)

This example demonstrates the full medallion architecture workflow:

```python
"""
Complete Bronze → Silver → Gold pipeline example.

Demonstrates:
1. Bronze: Ingest raw CSV from S3
2. Silver: Deduplicate, validate, cleanse, MERGE
3. Gold: Aggregate business metrics
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
    - Idempotency via Glue Job Bookmarks
    - Schema validation against BronzeTable contract
    - Metadata addition (_ingested_at, _source_system, _source_file)
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
    def partition_by(cls) -> list[str]:
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
            F.col("quantity") * F.col("unit_price") - F.col("discount_amount"))
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
    def primary_key(cls) -> list[str]:
        """Primary key for MERGE/upsert operations."""
        return ["transaction_id"]

    @classmethod
    def partition_by(cls) -> list[str]:
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
    - Top product by revenue
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
    def primary_key(cls) -> list[str]:
        """Primary key for daily aggregations."""
        return ["sale_date"]

    @classmethod
    def partition_by(cls) -> list[str]:
        """Partition by year-month for time-series queries."""
        return ["year(sale_date)", "month(sale_date)"]
```

**Usage**:
```bash
# 1. Deploy infrastructure (creates all 3 layers)
alur deploy

# 2. Run full pipeline
alur run end_to_end_example

# 3. Query in AWS Athena
SELECT * FROM gold_layer.daily_sales
WHERE sale_date >= current_date - interval '7' day
ORDER BY sale_date DESC;
```

---

### Step 6: Create Advanced Quality Check Examples
**File**: src/alur/templates/project/pipelines/advanced_quality_checks.py (NEW)

```python
"""
Advanced quality check patterns for Silver layer.

Demonstrates:
- Multi-column validation
- Cross-table referential integrity
- Time-series freshness checks
- Business rule validation
- Custom quality check functions
"""

from pyspark.sql import SparkSession, DataFrame
from pyspark.sql import functions as F
from datetime import datetime, timedelta

from alur import (
    pipeline, SilverTable,
    expect, not_empty, no_nulls_in_column,
    freshness_check, column_values_in_range,
    transform_to_silver
)
from alur.quality import QualityCheck


# ============================================================================
# Custom Quality Checks
# ============================================================================

def referential_integrity(
    foreign_key_col: str,
    reference_table: str,
    reference_col: str
) -> QualityCheck:
    """
    Check that all foreign key values exist in reference table.

    Example:
        @expect(referential_integrity("customer_id", "silver_layer.customers", "id"))
    """
    def check(df: DataFrame) -> tuple[bool, str]:
        spark = df.sparkSession

        # Get distinct foreign keys from current table
        fk_values = df.select(foreign_key_col).distinct()

        # Get reference values
        ref_df = spark.table(reference_table)
        ref_values = ref_df.select(F.col(reference_col).alias(foreign_key_col))

        # Find orphaned records (FKs not in reference table)
        orphaned = fk_values.join(ref_values, on=foreign_key_col, how="left_anti")
        orphan_count = orphaned.count()

        if orphan_count > 0:
            orphan_samples = [row[0] for row in orphaned.limit(5).collect()]
            return False, (
                f"Found {orphan_count} orphaned foreign keys in '{foreign_key_col}'. "
                f"Sample values: {orphan_samples}"
            )

        return True, f"All {foreign_key_col} values exist in {reference_table}.{reference_col}"

    return check


def sum_equals_total(
    sum_columns: list[str],
    total_column: str,
    tolerance: float = 0.01
) -> QualityCheck:
    """
    Check that sum of component columns equals total column (within tolerance).

    Example:
        @expect(sum_equals_total(["subtotal", "tax", "shipping"], "total_amount"))
    """
    def check(df: DataFrame) -> tuple[bool, str]:
        # Calculate sum of components
        sum_expr = sum(F.col(col) for col in sum_columns)

        # Find mismatches
        mismatches = df.filter(
            F.abs(sum_expr - F.col(total_column)) > tolerance
        )

        mismatch_count = mismatches.count()

        if mismatch_count > 0:
            sample = mismatches.select(*sum_columns, total_column).limit(3)
            sample_data = [row.asDict() for row in sample.collect()]

            return False, (
                f"Found {mismatch_count} rows where sum({sum_columns}) != {total_column}. "
                f"Samples: {sample_data}"
            )

        return True, f"All rows: sum({sum_columns}) == {total_column} (within {tolerance})"

    return check


def no_future_dates(date_column: str) -> QualityCheck:
    """
    Check that date column contains no future dates.

    Example:
        @expect(no_future_dates("order_date"))
    """
    def check(df: DataFrame) -> tuple[bool, str]:
        future_records = df.filter(F.col(date_column) > F.current_timestamp())
        future_count = future_records.count()

        if future_count > 0:
            max_future = future_records.agg(F.max(date_column)).collect()[0][0]
            return False, (
                f"Found {future_count} records with future dates in '{date_column}'. "
                f"Latest future date: {max_future}"
            )

        return True, f"No future dates in '{date_column}'"

    return check


# ============================================================================
# Silver Pipeline with Advanced Quality Checks
# ============================================================================

@pipeline(name="transform_orders_advanced", layer="silver")
@expect(not_empty(), severity="ERROR")
@expect(no_nulls_in_column("order_id"), severity="ERROR")
@expect(no_nulls_in_column("customer_id"), severity="ERROR")
@expect(no_nulls_in_column("order_date"), severity="ERROR")
@expect(freshness_check("order_date", max_age_hours=48), severity="WARN")
@expect(no_future_dates("order_date"), severity="ERROR")
@expect(column_values_in_range("total_amount", min_value=0, max_value=1000000), severity="WARN")
@expect(referential_integrity("customer_id", "silver_layer.customers", "customer_id"), severity="ERROR")
@expect(sum_equals_total(["subtotal", "tax", "shipping"], "total_amount"), severity="WARN")
def transform_orders_advanced(spark: SparkSession) -> DataFrame:
    """
    Orders transformation with comprehensive quality validation.

    Quality checks enforce:
    1. Required fields (order_id, customer_id, order_date)
    2. Freshness (data not older than 48 hours)
    3. No future dates
    4. Reasonable value ranges
    5. Referential integrity (customer_id exists)
    6. Mathematical consistency (subtotal + tax + shipping = total)
    """
    bronze_df = spark.table("bronze_layer.orders")

    silver_df = transform_to_silver(
        df=bronze_df,
        target=OrdersSilver,
        dedup_by=["order_id"],
        dedup_strategy="latest",
        fill_nulls_map={
            "notes": "",
            "shipping": 0.0,
            "discount": 0.0
        },
        filters=[
            F.col("total_amount").cast("decimal(10,2)") >= 0
        ],
        validate=True,
        source_bronze_table="orders"
    )

    return silver_df


class OrdersSilver(SilverTable):
    """Silver orders with advanced validation."""
    order_id: str
    customer_id: str
    order_date: datetime
    subtotal: float
    tax: float
    shipping: float
    discount: float
    total_amount: float
    status: str
    notes: str

    @classmethod
    def get_table_name(cls) -> str:
        return "orders"

    @classmethod
    def primary_key(cls) -> list[str]:
        return ["order_id"]

    @classmethod
    def partition_by(cls) -> list[str]:
        return ["year(order_date)", "month(order_date)"]
```

---

## Part 4: Testing & Verification Strategy

### 4.1 Local Development Testing

**Pre-Deployment Validation**:
```bash
# 1. Validate contracts (Python import checks)
python -c "from contracts.silver import OrdersSilver; print(OrdersSilver.to_iceberg_schema())"

# 2. Validate pipeline registration
python -c "from pipelines.transform_orders import transform_orders; print(transform_orders)"

# 3. Generate Terraform (check for errors)
alur generate

# 4. Review generated Terraform
cat terraform/main.tf | grep -A 20 "silver_layer"
```

### 4.2 AWS Deployment Testing

**Step 1: Deploy Infrastructure**
```bash
alur deploy
```

**Expected Outputs**:
- ✅ bronze_bucket created
- ✅ silver_bucket created
- ✅ gold_bucket created
- ✅ bronze_layer database created
- ✅ silver_layer database created
- ✅ gold_layer database created
- ✅ IAM roles with multi-layer bucket access
- ✅ Glue jobs for each pipeline

**Step 2: Run Bronze Ingestion**
```bash
alur run ingest_orders
```

**Verification**:
```sql
-- In AWS Athena
SELECT COUNT(*), MIN(_ingested_at), MAX(_ingested_at)
FROM bronze_layer.orders;
```

**Step 3: Run Silver Transformation**
```bash
alur run transform_orders
```

**Verification**:
```sql
-- Check Silver data
SELECT COUNT(*),
       COUNT(DISTINCT order_id) as unique_orders,
       MIN(_transformed_at),
       MAX(_transformed_at)
FROM silver_layer.orders;

-- Verify no duplicates
SELECT order_id, COUNT(*) as cnt
FROM silver_layer.orders
GROUP BY order_id
HAVING COUNT(*) > 1;  -- Should return 0 rows

-- Check MERGE metadata
DESCRIBE HISTORY silver_layer.orders;  -- Iceberg history
```

**Step 4: Test Idempotency (Rerun Silver)**
```bash
# Run twice - should produce same result
alur run transform_orders
alur run transform_orders
```

**Verification**:
```sql
-- Row count should be stable (MERGE updates, not appends)
SELECT COUNT(*) FROM silver_layer.orders;  -- Same count both times
```

**Step 5: Test Quality Checks**
```bash
# Introduce bad data in Bronze, rerun Silver
# Should fail with descriptive error messages
alur run transform_orders
```

**Expected Output**:
```
Running quality checks for transform_orders...
✓ not_empty: PASSED
✓ no_nulls_in_column(order_id): PASSED
✗ no_duplicates_in_column(order_id): FAILED - Found 5 duplicate order_ids
Pipeline failed due to ERROR severity quality check failures
```

### 4.3 Performance Testing

**Large Dataset Test**:
```python
# Generate 10M test records in Bronze
bronze_df = spark.range(0, 10_000_000).select(
    F.col("id").cast("string").alias("order_id"),
    F.lit("customer_123").alias("customer_id"),
    F.current_timestamp().alias("order_date"),
    (F.rand() * 1000).alias("total_amount")
)

# Run Silver transformation - monitor:
# - Execution time
# - Shuffle partitions
# - Memory usage
# - Iceberg MERGE performance
```

**Expected Performance**:
- Bronze ingestion: ~500 MB/s (S3 read bandwidth limited)
- Deduplication: Depends on partition count and shuffle
- MERGE operation: ~100K rows/second for typical schemas

---

## Part 5: Architecture Patterns & Best Practices

### 5.1 When to Use Each Idempotency Strategy

**Glue Job Bookmarks** (default for all ingestion):
- ✅ Best for: CSV file ingestion, database JDBC reads
- ✅ Use when: Source supports incremental reads
- ✅ Benefits: AWS-native, no additional infrastructure, zero cost, no custom state
- ✅ Covers both file-level (S3 CSV) and column-level (JDBC) incremental reads

**No Tracking** (omit bookmark configuration):
- ✅ Best for: Full refreshes, non-production pipelines, testing
- ✅ Use when: Source data is always complete snapshot
- ✅ Benefits: Simple, fast
- ❌ Limitations: Will reprocess all data every run

### 5.2 Silver Layer Design Patterns

**Pattern 1: Type 1 SCD (Overwrite)**
- Use MERGE with UPDATE when matched
- No historical tracking
- Best for: Dimensions that don't need history (customer address, product price)

```python
class CustomersSilver(SilverTable):
    customer_id: str  # Primary key
    name: str
    email: str
    address: str  # Latest value overwrites

    @classmethod
    def primary_key(cls) -> list[str]:
        return ["customer_id"]
```

**Pattern 2: Type 2 SCD (Historical Tracking)**
- Add effective_date, end_date, is_current columns
- MERGE with conditional UPDATE
- Best for: Dimensions needing full history (customer segments, product categories)

```python
class CustomerSegmentsSilver(SilverTable):
    customer_id: str
    segment: str
    effective_date: datetime
    end_date: datetime  # Null for current record
    is_current: bool

    @classmethod
    def primary_key(cls) -> list[str]:
        return ["customer_id", "effective_date"]
```

**Pattern 3: Append-Only Facts**
- No MERGE needed
- Deduplication at read time if needed
- Best for: Immutable facts (transactions, events, logs)

```python
class TransactionsSilver(SilverTable):
    transaction_id: str
    timestamp: datetime
    amount: float

    # No primary_key = append-only mode (if supported)
```

### 5.3 Partitioning Strategy

**Time-Based Partitioning** (Most Common):
```python
@classmethod
def partition_by(cls) -> list[str]:
    return ["year(order_date)", "month(order_date)"]
```
- ✅ Best for: Time-series data with date range queries
- ✅ Benefits: Partition pruning for fast queries
- ❌ Limitations: Can create many small partitions

**Categorical Partitioning**:
```python
@classmethod
def partition_by(cls) -> list[str]:
    return ["region", "product_category"]
```
- ✅ Best for: Data with natural categorical splits
- ✅ Benefits: Isolates queries to specific segments
- ❌ Limitations: Skewed data can create uneven partitions

**No Partitioning**:
```python
@classmethod
def partition_by(cls) -> list[str]:
    return []  # Single partition
```
- ✅ Best for: Small tables (<100GB), frequently updated dimensions
- ✅ Benefits: Simple, no partition management
- ❌ Limitations: Slower queries on large tables

### 5.4 Quality Check Severity Guidelines

**ERROR Severity** (Pipeline fails):
- Required field nulls: `no_nulls_in_column("order_id")`
- Duplicate primary keys: `no_duplicates_in_column("order_id")`
- Empty results: `not_empty()`
- Referential integrity violations
- Data corruption indicators

**WARN Severity** (Log but continue):
- Unexpected value ranges: `column_values_in_range("amount", min_value=0)`
- Stale data: `freshness_check("updated_at", max_age_hours=48)`
- Statistical anomalies (sudden volume changes)
- Optional field validation

---

## Part 6: Rollout Plan

### Phase 1: Infrastructure Foundation (Week 1)
**Deliverables**:
1. Fix layer detection bug in BaseTable.get_layer()
2. Update infrastructure generator for Silver/Gold databases
3. Generate Silver/Gold S3 buckets in Terraform
4. Update IAM permissions for multi-layer access
5. Update config.py with SILVER_BUCKET and GOLD_BUCKET

**Validation**:
- Run `alur generate` - check for Silver/Gold resources
- Deploy to dev AWS account
- Verify all 3 databases created in Glue Catalog
- Verify all 3 buckets created in S3

### Phase 2: Core Silver Capabilities (Week 2)
**Deliverables**:
1. Update RuntimeAdapter._get_s3_path() for Silver/Gold layers
2. Test Iceberg MERGE with sample Silver table
3. Test all transformation utilities (deduplicate, fill_nulls, etc.)
4. Verify quality checks execute in Silver pipeline

**Validation**:
- Create test OrdersSilver table
- Run transform_orders pipeline end-to-end
- Query Silver table in Athena
- Verify MERGE idempotency (run twice, check row counts)

### Phase 3: Templates & Documentation (Week 3)
**Deliverables**:
1. Create end_to_end_example.py (Bronze→Silver→Gold)
2. Create advanced_quality_checks.py examples
3. Update README with Silver layer usage
4. Document idempotency strategy selection guide
5. Create troubleshooting guide

**Validation**:
- New user can run `alur init`, deploy, and execute example pipeline
- Documentation covers all common Silver patterns

### Phase 4: Production Hardening (Week 4)
**Deliverables**:
1. Performance testing with 10M+ row datasets
2. Error handling improvements
3. Monitoring and alerting setup guide
4. Cost optimization recommendations
5. Production checklist

**Validation**:
- Load test passes with acceptable performance
- Error messages are actionable
- Cost per GB processed is acceptable

---

## Part 7: Success Criteria

### Functional Requirements
- ✅ Silver tables can be defined with `@dataclass` contracts
- ✅ Iceberg MERGE operations work correctly (no duplicates after reruns)
- ✅ Transformation utilities (deduplicate, fill_nulls, etc.) work as documented
- ✅ Quality checks fail pipelines on ERROR, warn on WARN
- ✅ Multi-layer pipelines (Bronze→Silver→Gold) execute in dependency order
- ✅ Infrastructure generates correctly for all 3 layers
- ✅ Tables queryable in AWS Athena

### Non-Functional Requirements
- ✅ Performance: Process 1M rows in <5 minutes
- ✅ Cost: <$0.10 per GB processed (Glue + S3)
- ✅ Reliability: Pipeline failures are recoverable (idempotent)
- ✅ Observability: Logs show clear progress and errors
- ✅ Documentation: New user can deploy Silver pipeline in <30 minutes

### Quality Metrics
- ✅ Zero data loss (all Bronze records accounted for in Silver)
- ✅ Zero duplicates in Silver after deduplication
- ✅ 100% schema compliance (all columns match contract)
- ✅ Quality check coverage: >80% of critical business rules

---

## Part 8: Open Questions & Decisions Needed

### Question 1: Iceberg Table Generation Strategy
**Options**:
A) Generate Iceberg tables in Terraform (declarative, version controlled)
B) Auto-create on first write (runtime, simpler)
C) Hybrid: Terraform registers table, Glue auto-creates schema

**Recommendation**: Option C - Terraform creates placeholder, first MERGE populates schema
**Rationale**: Balance between infrastructure-as-code and flexibility

### Question 2: Silver Partitioning Defaults
**Options**:
A) Require explicit partition_by (no defaults)
B) Default to year/month if date column exists
C) No partitioning by default (single partition)

**Recommendation**: Option A - Explicit is better than implicit
**Rationale**: Partitioning strategy depends on query patterns

### Question 3: MERGE vs Overwrite for Silver
**Current**: MERGE is always used if primary_key exists
**Alternatives**:
A) Add `write_mode` parameter to SilverTable (MERGE vs OVERWRITE)
B) Keep current behavior (MERGE if primary_key, else append)
C) Make MERGE optional via decorator parameter

**Recommendation**: Option B - Current behavior is correct
**Rationale**: Primary key semantically implies upsert logic

### Question 4: Quality Check Execution Timing
**Current**: Checks run AFTER data written (can't prevent bad writes)
**Alternatives**:
A) Add pre-write checks (validate before MERGE)
B) Keep post-write checks only
C) Support both pre and post hooks

**Recommendation**: Option A - Add pre-write checks with @expect_before decorator
**Rationale**: Prevents writing invalid data, faster failure detection

---

## Part 9: Risk Analysis

### Risk 1: Iceberg MERGE Performance on Large Tables
**Likelihood**: Medium
**Impact**: High
**Mitigation**:
- Use partition pruning (match on partition columns)
- Limit MERGE to recent partitions only
- Consider bucketing for very large tables (>100M rows)
- Monitor Glue job metrics (shuffle size, execution time)

### Risk 2: Quality Check Performance Overhead
**Likelihood**: Low
**Impact**: Low
**Mitigation**:
- Quality checks run on final DataFrame (post-transformations)
- Use sampling for statistical checks on large datasets
- Cache DataFrame before checks if multiple checks reference same data

### Risk 4: Schema Evolution Breaking Pipelines
**Likelihood**: Medium
**Impact**: High
**Mitigation**:
- Iceberg supports schema evolution (add columns without rewrite)
- Use optional types (Optional[str]) for nullable columns
- Version contracts (OrdersSilverV2 for breaking changes)
- Test schema changes in dev environment first

---

## Appendix A: Full File Change Summary

### Files to Create (2 new files)
1. `src/alur/templates/project/pipelines/end_to_end_example.py` (Bronze→Silver→Gold example)
2. `src/alur/templates/project/pipelines/advanced_quality_checks.py` (Custom quality checks)

### Files to Modify (4 files)
1. `src/alur/core/contracts.py` - Fix get_layer() method (4 lines)
2. `src/alur/infra/generator.py` - Add Silver/Gold support (~200 lines)
3. `src/alur/config.py` - Add SILVER_BUCKET and GOLD_BUCKET (~10 lines)
4. `src/alur/engine/adapter.py` - Update _get_s3_path() (~10 lines)

### No Changes Required (Already Complete)
- ✅ `src/alur/core/contracts.py` - SilverTable and GoldTable classes
- ✅ `src/alur/transformation/__init__.py` - All transformation utilities
- ✅ `src/alur/engine/adapter.py` - Iceberg MERGE implementation
- ✅ `src/alur/quality/__init__.py` - Quality check framework
- ✅ `src/alur/templates/project/contracts/silver.py` - OrdersSilver example

### Estimated LOC Changes
- New code: ~800 lines (2 new template files)
- Modified code: ~50 lines (bug fixes + config)
- Total: ~850 lines

---

## Appendix B: Example Athena Queries

### Query Silver Data
```sql
-- Basic query with partition pruning
SELECT *
FROM silver_layer.orders
WHERE year(order_date) = 2024
  AND month(order_date) = 1
LIMIT 100;

-- Aggregation query
SELECT
    date_trunc('day', order_date) as order_day,
    COUNT(*) as order_count,
    SUM(total_amount) as daily_revenue
FROM silver_layer.orders
WHERE year(order_date) = 2024
GROUP BY date_trunc('day', order_date)
ORDER BY order_day DESC;

-- Check for duplicates (should return 0 rows)
SELECT order_id, COUNT(*) as cnt
FROM silver_layer.orders
GROUP BY order_id
HAVING COUNT(*) > 1;

-- Verify MERGE history (Iceberg time travel)
SELECT *
FROM silver_layer.orders
FOR SYSTEM_TIME AS OF TIMESTAMP '2024-01-15 10:00:00';
```

### Monitor Data Quality
```sql
-- Check metadata columns
SELECT
    _source_bronze_table,
    _transformation_name,
    MIN(_transformed_at) as first_transform,
    MAX(_transformed_at) as last_transform,
    COUNT(*) as record_count
FROM silver_layer.orders
GROUP BY _source_bronze_table, _transformation_name;

-- Find recent transformations
SELECT *
FROM silver_layer.orders
WHERE _transformed_at > current_timestamp - interval '1' hour
ORDER BY _transformed_at DESC
LIMIT 100;
```

---

## Summary

This plan provides a comprehensive roadmap for implementing production-ready Silver layer capabilities in the Alur framework. The core transformation utilities and Iceberg MERGE functionality are already complete. The primary work required is fixing infrastructure generation gaps and creating detailed template examples.

**Key Takeaways**:
1. **Silver layer core logic is complete** - Focus on infrastructure and templates
2. **Iceberg MERGE enables true idempotency** - Critical for data quality
3. **Quality checks are first-class citizens** - Not an afterthought
4. **Multi-layer architecture is simple** - Bronze→Silver→Gold just works
5. **AWS-native deployment** - No local adapter, cloud-first design

**Next Steps**:
1. Approve this plan
2. Implement Phase 1 (infrastructure foundation)
3. Test end-to-end with example pipeline
4. Iterate based on production feedback
