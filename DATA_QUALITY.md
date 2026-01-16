# Data Quality Checks - Alur Framework

## Overview

Alur provides built-in data quality validation that runs automatically after each pipeline execution. Catch data issues early and ensure data reliability across your entire lakehouse.

## Features

- ✅ **Automatic execution** - Checks run after pipeline completes
- ✅ **Multiple severity levels** - ERROR (fails pipeline) or WARN (logs only)
- ✅ **Built-in checks** - Common validations ready to use
- ✅ **Custom checks** - Write your own validation logic
- ✅ **Zero overhead** - Only runs on result DataFrame
- ✅ **Clear reporting** - Detailed pass/fail messages

---

## Quick Start

### Basic Usage

```python
from alur.decorators import pipeline
from alur.quality import expect, not_empty, no_nulls_in_column

@expect(
    name="data_not_empty",
    check_fn=not_empty,
    description="Ensure we have data"
)
@expect(
    name="no_null_ids",
    check_fn=no_nulls_in_column("order_id"),
    description="All orders must have an ID"
)
@pipeline(
    sources={"orders": OrdersBronze},
    target=OrdersSilver
)
def clean_orders(orders):
    return orders.filter(F.col("status") == "valid")
```

### What Happens

```
[Alur] Executing transformation: clean_orders
[Alur] Writing to target: orderssilver (mode=overwrite)
[Alur] Running 2 quality check(s)...
[Alur]   ✓ data_not_empty: DataFrame has 1234 rows
[Alur]   ✓ no_null_ids: Column 'order_id' has 0 null values
[Alur] Pipeline 'clean_orders' completed successfully
```

---

## Built-in Quality Checks

### 1. Row Count Checks

```python
from alur.quality import not_empty, min_row_count, max_row_count

# Check DataFrame is not empty
@expect(name="has_data", check_fn=not_empty)

# Minimum row count
@expect(name="min_rows", check_fn=min_row_count(1000))

# Maximum row count
@expect(name="max_rows", check_fn=max_row_count(1000000))
```

### 2. Null Checks

```python
from alur.quality import no_nulls_in_column

# No nulls in critical columns
@expect(name="no_null_ids", check_fn=no_nulls_in_column("order_id"))
@expect(name="no_null_amounts", check_fn=no_nulls_in_column("amount"))
```

### 3. Duplicate Checks

```python
from alur.quality import no_duplicates_in_column

# Primary key uniqueness
@expect(name="unique_ids", check_fn=no_duplicates_in_column("order_id"))
```

### 4. Schema Validation

```python
from alur.quality import schema_has_columns

# Required columns present
@expect(
    name="required_columns",
    check_fn=schema_has_columns(["order_id", "customer_id", "amount"])
)
```

### 5. Value Range Checks

```python
from alur.quality import column_values_in_range

# Values within expected range
@expect(
    name="valid_amounts",
    check_fn=column_values_in_range("amount", min_val=0, max_val=100000)
)

@expect(
    name="valid_quantities",
    check_fn=column_values_in_range("quantity", min_val=1, max_val=1000)
)
```

### 6. Freshness Checks

```python
from alur.quality import freshness_check

# Data recency
@expect(
    name="data_is_fresh",
    check_fn=freshness_check("created_at", max_age_hours=24)
)
```

---

## Custom Quality Checks

### Simple Custom Check

```python
def check_no_future_dates(df):
    """Ensure no orders have future dates."""
    from pyspark.sql.functions import col, current_timestamp

    future_count = df.filter(col("created_at") > current_timestamp()).count()

    if future_count == 0:
        return (True, "No future-dated orders")
    else:
        return (False, f"Found {future_count} orders with future dates")

@expect(name="no_future_orders", check_fn=check_no_future_dates)
@pipeline(...)
def my_pipeline(data):
    return data
```

### Lambda Checks

```python
# Quick inline check
@expect(
    name="weekend_orders",
    check_fn=lambda df: (
        df.filter(F.dayofweek("created_at").isin([1, 7])).count() > 0,
        "Has weekend orders"
    )
)
```

### Complex Custom Check

```python
def check_revenue_growth(df):
    """
    Ensure daily revenue is growing.
    Returns (bool, str) tuple.
    """
    from pyspark.sql import Window
    from pyspark.sql.functions import col, lag

    # Calculate day-over-day growth
    window = Window.orderBy("report_date")

    with_previous = df.withColumn(
        "prev_revenue",
        lag("total_revenue").over(window)
    )

    declining_days = with_previous.filter(
        col("total_revenue") < col("prev_revenue")
    ).count()

    passed = declining_days == 0

    if passed:
        return (True, "Revenue growing consistently")
    else:
        return (False, f"Revenue declined on {declining_days} days")

@expect(name="revenue_growth", check_fn=check_revenue_growth)
@pipeline(...)
def sales_analysis(data):
    return data
```

---

## Severity Levels

### ERROR (Default)

Pipeline **fails** if check fails.

```python
from alur.quality import Severity

@expect(
    name="critical_check",
    check_fn=min_row_count(100),
    severity=Severity.ERROR  # Pipeline fails
)
```

**Output when fails:**
```
[Alur]   ✗ critical_check: Row count 50 below minimum 100
[Alur] Quality checks: 1 failure(s)
[ERROR] Data quality checks failed for pipeline 'my_pipeline':
  - critical_check: Row count 50 below minimum 100
```

### WARN

Pipeline **continues** but logs warning.

```python
@expect(
    name="preferred_check",
    check_fn=min_row_count(1000),
    severity=Severity.WARN  # Only warns
)
```

**Output when fails:**
```
[Alur]   ⚠  preferred_check: Row count 500 below minimum 1000
[Alur] Quality checks: 1 warning(s)
[Alur] Pipeline 'my_pipeline' completed successfully
```

---

## Real-World Examples

### Example 1: E-commerce Orders

```python
from alur.quality import (
    expect, Severity,
    not_empty, min_row_count,
    no_nulls_in_column, no_duplicates_in_column,
    column_values_in_range, freshness_check
)

@expect(
    name="orders_not_empty",
    check_fn=not_empty,
    description="Must have order data"
)
@expect(
    name="min_daily_orders",
    check_fn=min_row_count(100),
    severity=Severity.ERROR,
    description="Expect at least 100 orders per day"
)
@expect(
    name="unique_order_ids",
    check_fn=no_duplicates_in_column("order_id"),
    description="Order IDs must be unique"
)
@expect(
    name="no_null_customers",
    check_fn=no_nulls_in_column("customer_id"),
    description="All orders need customer IDs"
)
@expect(
    name="valid_amounts",
    check_fn=column_values_in_range("amount", 0, 1000000),
    description="Amounts between $0 and $10,000"
)
@expect(
    name="fresh_data",
    check_fn=freshness_check("created_at", max_age_hours=2),
    description="Data should be <2 hours old"
)
@pipeline(sources={"orders": OrdersBronze}, target=OrdersSilver)
def process_orders(orders):
    return orders.filter(F.col("status") == "completed")
```

### Example 2: Financial Reconciliation

```python
def check_debit_credit_balance(df):
    """Ensure debits equal credits."""
    from pyspark.sql.functions import sum as spark_sum, col

    totals = df.agg(
        spark_sum(col("debit")).alias("total_debit"),
        spark_sum(col("credit")).alias("total_credit")
    ).collect()[0]

    debit = totals["total_debit"]
    credit = totals["total_credit"]

    balanced = abs(debit - credit) < 0.01  # Allow for rounding

    return (
        balanced,
        f"Debits ({debit}) and credits ({credit}) {'balanced' if balanced else 'UNBALANCED'}"
    )

@expect(
    name="books_balanced",
    check_fn=check_debit_credit_balance,
    severity=Severity.ERROR,
    description="Accounting entries must balance"
)
@pipeline(...)
def reconcile_accounts(transactions):
    return transactions
```

### Example 3: Data Warehouse ETL

```python
@expect(
    name="no_duplicates",
    check_fn=no_duplicates_in_column("transaction_id"),
    severity=Severity.ERROR
)
@expect(
    name="all_required_columns",
    check_fn=schema_has_columns([
        "transaction_id", "customer_id", "product_id",
        "amount", "timestamp"
    ]),
    severity=Severity.ERROR
)
@expect(
    name="reasonable_transaction_amounts",
    check_fn=column_values_in_range("amount", -10000, 10000),
    severity=Severity.WARN
)
@expect(
    name="has_weekend_data",
    check_fn=lambda df: (
        df.filter(F.dayofweek("timestamp").isin([1, 7])).count() > 0,
        "Should have weekend transactions"
    ),
    severity=Severity.WARN
)
@pipeline(sources={"txns": TransactionsBronze}, target=TransactionsSilver)
def clean_transactions(txns):
    """Clean transactions with comprehensive quality checks."""
    return txns.filter(F.col("status") == "completed")
```

---

## Check Execution Flow

```
1. Pipeline executes transformation
2. Result DataFrame is written to target
3. Quality checks run on result DataFrame
4. For each check:
   - Run check function
   - Log result (✓ pass, ✗ fail, ⚠ warn)
5. If any ERROR-level checks fail:
   - Raise RuntimeError with details
   - Pipeline fails
6. If only WARN-level checks fail:
   - Log warnings
   - Pipeline succeeds
7. Pipeline completes
```

---

## Disabling Checks

### Temporarily Disable a Check

```python
@expect(
    name="optional_check",
    check_fn=min_row_count(1000),
    enabled=False  # Disabled
)
```

### Environment-Specific Checks

```python
import os

@expect(
    name="prod_only_check",
    check_fn=min_row_count(10000),
    enabled=(os.getenv("ENV") == "prod")  # Only in production
)
```

---

## Viewing Quality Checks

### List All Checks

```bash
$ alur list --verbose

⚙️  PIPELINES (1 total)

  • clean_orders: [orders] → orderssilver
      Sources: orders
      Target: orderssilver
      Profile: medium
      Quality Checks: 3
        - data_not_empty (ERROR)
        - min_1000_orders (ERROR)
        - no_null_ids (ERROR)
```

### Programmatic Access

```python
from alur.quality import QualityRegistry

# Get checks for a pipeline
checks = QualityRegistry.get_checks("clean_orders")

for check in checks:
    print(f"Check: {check.name}")
    print(f"  Severity: {check.severity.value}")
    print(f"  Enabled: {check.enabled}")
    print(f"  Description: {check.description}")
```

---

## Best Practices

### 1. Start with Critical Checks

```python
# Start with must-have validations
@expect(name="not_empty", check_fn=not_empty, severity=Severity.ERROR)
@expect(name="no_null_pks", check_fn=no_nulls_in_column("id"), severity=Severity.ERROR)
```

### 2. Add Warnings for Nice-to-Haves

```python
# Add softer checks as warnings
@expect(name="preferred_volume", check_fn=min_row_count(1000), severity=Severity.WARN)
```

### 3. Keep Checks Fast

```python
# Good: Uses count() - fast
check_fn=min_row_count(100)

# Bad: Collects all data - slow
check_fn=lambda df: (len(df.collect()) > 100, "...")
```

### 4. Use Descriptive Names

```python
# Good
@expect(name="no_future_order_dates", ...)

# Bad
@expect(name="check1", ...)
```

### 5. Layer Your Validations

```python
# Bronze: Basic structure
@expect(name="has_data", check_fn=not_empty)
@expect(name="has_required_columns", check_fn=schema_has_columns([...]))

# Silver: Business rules
@expect(name="no_null_ids", check_fn=no_nulls_in_column("id"))
@expect(name="valid_amounts", check_fn=column_values_in_range("amount", 0, 100000))

# Gold: Analytics quality
@expect(name="reasonable_aggregates", check_fn=...)
@expect(name="no_negative_totals", check_fn=...)
```

---

## Advanced Patterns

### Check with External State

```python
def check_against_previous_run(df):
    """Compare to previous run metrics."""
    current_count = df.count()

    # TODO: Load previous count from DynamoDB/S3
    # previous_count = load_from_state_store()

    # For now, return pass
    return (True, f"Current count: {current_count}")
```

### Multi-Column Checks

```python
def check_referential_integrity(df):
    """Ensure customer_id exists in customers table."""
    # This would require access to other tables
    # Could be implemented by joining with customer dimension
    return (True, "Referential integrity maintained")
```

### Statistical Checks

```python
def check_distribution(df):
    """Ensure data distribution is reasonable."""
    from pyspark.sql.functions import stddev, mean

    stats = df.agg(
        mean("amount").alias("mean"),
        stddev("amount").alias("stddev")
    ).collect()[0]

    # Check if stddev is too high (possible data quality issue)
    coefficient_of_variation = stats["stddev"] / stats["mean"]

    passed = coefficient_of_variation < 2.0

    return (
        passed,
        f"CV: {coefficient_of_variation:.2f} ({'normal' if passed else 'high variance'})"
    )
```

---

## Integration with Contract Validation

Quality checks work seamlessly with contract field constraints:

```python
from alur.core import SilverTable, StringField, IntegerField

class OrdersSilver(SilverTable):
    """Contract defines schema constraints."""

    order_id = StringField(nullable=False)  # Schema-level constraint
    amount = IntegerField(nullable=False)   # Schema-level constraint

# Quality checks add runtime validation
@expect(
    name="no_null_order_ids",  # Runtime validation
    check_fn=no_nulls_in_column("order_id")
)
@expect(
    name="positive_amounts",   # Business rule validation
    check_fn=column_values_in_range("amount", 0, 1000000)
)
@pipeline(sources={...}, target=OrdersSilver)
def process_orders(data):
    return data
```

**Layer your validations:**
- **Schema (Contracts)**: Field types, nullability
- **Quality Checks**: Business rules, data ranges, freshness
- **Custom Logic**: Complex validations in pipeline code

---

## Summary

Data quality checks in Alur provide:

✅ **Automatic validation** after every pipeline run
✅ **Built-in checks** for common scenarios
✅ **Custom checks** for business-specific rules
✅ **Flexible severity** (ERROR vs WARN)
✅ **Clear reporting** with detailed messages
✅ **Zero config** - just add decorators

Start with basic checks, add custom validations as needed, and ensure data quality across your entire lakehouse!
