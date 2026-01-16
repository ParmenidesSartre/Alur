# Data Quality Checks - Implementation Summary

## ✅ What Was Added

### Core Module
- `src/alur/quality/__init__.py` - Complete data quality framework (~350 lines)

### Integration
- Modified `src/alur/engine/runner.py` - Auto-run quality checks after pipeline execution
- Modified `src/alur/__init__.py` - Export quality module

### Examples
- `pipelines/with_quality_checks.py` - 6 comprehensive examples

### Documentation
- `DATA_QUALITY.md` - Complete user guide

---

## Quick Usage Examples

### 1. Built-in Checks

```python
from alur.quality import expect, not_empty, no_nulls_in_column, min_row_count

@expect(name="has_data", check_fn=not_empty)
@expect(name="min_rows", check_fn=min_row_count(1000))
@expect(name="no_null_ids", check_fn=no_nulls_in_column("order_id"))
@pipeline(sources={"orders": OrdersBronze}, target=OrdersSilver)
def clean_orders(orders):
    return orders.filter(F.col("status") == "valid")
```

### 2. Custom Checks

```python
def check_no_future_dates(df):
    future_count = df.filter(F.col("created_at") > F.current_timestamp()).count()
    return (future_count == 0, f"Found {future_count} future dates")

@expect(name="valid_dates", check_fn=check_no_future_dates)
@pipeline(...)
def process_data(data):
    return data
```

### 3. Severity Levels

```python
from alur.quality import Severity

# ERROR - Fails pipeline
@expect(name="critical", check_fn=not_empty, severity=Severity.ERROR)

# WARN - Logs warning only
@expect(name="preferred", check_fn=min_row_count(1000), severity=Severity.WARN)
```

---

## Built-in Quality Checks

| Check Function | Purpose | Example |
|---|---|---|
| `not_empty` | DataFrame has data | `check_fn=not_empty` |
| `min_row_count(n)` | Minimum row count | `check_fn=min_row_count(1000)` |
| `max_row_count(n)` | Maximum row count | `check_fn=max_row_count(1000000)` |
| `no_nulls_in_column(col)` | No null values | `check_fn=no_nulls_in_column("id")` |
| `no_duplicates_in_column(col)` | Unique values | `check_fn=no_duplicates_in_column("id")` |
| `schema_has_columns(cols)` | Required columns | `check_fn=schema_has_columns(["id", "name"])` |
| `column_values_in_range(col, min, max)` | Value bounds | `check_fn=column_values_in_range("amount", 0, 10000)` |
| `freshness_check(col, hours)` | Data recency | `check_fn=freshness_check("created_at", 24)` |

---

## Execution Flow

```
Pipeline Execution
    ↓
Transform Data
    ↓
Write to Target
    ↓
Run Quality Checks  ← NEW!
    ├─ Check 1: ✓ Pass
    ├─ Check 2: ✓ Pass
    ├─ Check 3: ✗ Fail (ERROR) → Pipeline fails
    └─ Check 4: ⚠ Fail (WARN) → Pipeline continues
    ↓
Complete
```

---

## Example Output

### All Checks Pass
```
[Alur] Executing transformation: clean_orders
[Alur] Writing to target: orderssilver (mode=overwrite)
[Alur] Running 3 quality check(s)...
[Alur]   ✓ orders_not_empty: DataFrame has 1234 rows
[Alur]   ✓ min_1000_orders: Row count 1234 meets minimum 1000
[Alur]   ✓ no_null_order_ids: Column 'order_id' has 0 null values
[Alur] Pipeline 'clean_orders' completed successfully
```

### Check Fails (ERROR)
```
[Alur] Running 2 quality check(s)...
[Alur]   ✗ orders_not_empty: DataFrame is empty
[Alur]   ✗ min_1000_orders: Row count 0 below minimum 1000
[Alur] Quality checks: 2 failure(s)
[ERROR] Data quality checks failed for pipeline 'clean_orders':
  - orders_not_empty: DataFrame is empty
  - min_1000_orders: Row count 0 below minimum 1000
```

### Check Warns (WARN)
```
[Alur] Running 2 quality check(s)...
[Alur]   ✓ critical_min_rows: Row count 500 meets minimum 100
[Alur]   ⚠  preferred_min_rows: Row count 500 below minimum 1000
[Alur] Quality checks: 1 warning(s)
[Alur] Pipeline 'clean_orders' completed successfully
```

---

## Real-World Example

```python
from alur.decorators import pipeline
from alur.quality import (
    expect, Severity,
    not_empty, min_row_count,
    no_nulls_in_column, column_values_in_range,
    freshness_check
)
from contracts.bronze import OrdersBronze
from contracts.silver import OrdersSilver
from pyspark.sql import functions as F

# Critical checks (ERROR severity - pipeline fails)
@expect(
    name="orders_not_empty",
    check_fn=not_empty,
    severity=Severity.ERROR,
    description="Must have order data"
)
@expect(
    name="no_null_order_ids",
    check_fn=no_nulls_in_column("order_id"),
    severity=Severity.ERROR,
    description="All orders need IDs"
)
@expect(
    name="valid_amounts",
    check_fn=column_values_in_range("amount", 0, 1000000),
    severity=Severity.ERROR,
    description="Amounts must be reasonable"
)

# Soft checks (WARN severity - logs warning only)
@expect(
    name="preferred_volume",
    check_fn=min_row_count(1000),
    severity=Severity.WARN,
    description="Ideally >1000 orders per run"
)
@expect(
    name="data_is_fresh",
    check_fn=freshness_check("created_at", max_age_hours=2),
    severity=Severity.WARN,
    description="Data should be recent"
)

# Custom check
def check_no_future_dates(df):
    future_count = df.filter(F.col("created_at") > F.current_timestamp()).count()
    return (future_count == 0, f"Found {future_count} future-dated orders")

@expect(
    name="no_future_orders",
    check_fn=check_no_future_dates,
    severity=Severity.ERROR,
    description="Orders can't be in the future"
)

@pipeline(
    sources={"orders": OrdersBronze},
    target=OrdersSilver,
    resource_profile="medium"
)
def clean_orders_with_quality(orders):
    """
    Clean orders with comprehensive quality validation.
    Checks run automatically after transformation.
    """
    cleaned = orders.filter(
        (F.col("order_id").isNotNull()) &
        (F.col("quantity") > 0) &
        (F.col("amount") > 0)
    )

    return cleaned.withColumn(
        "status",
        F.coalesce(F.col("status"), F.lit("unknown"))
    )
```

---

## Features

### ✅ Automatic Execution
- Checks run after every pipeline execution
- No manual trigger needed
- Integrated into PipelineRunner

### ✅ Severity Levels
- `Severity.ERROR` - Fails pipeline
- `Severity.WARN` - Logs warning only

### ✅ Built-in Checks
- Row counts (min/max)
- Null checks
- Duplicate detection
- Schema validation
- Value ranges
- Data freshness

### ✅ Custom Checks
- Write your own validation logic
- Simple function signature: `(DataFrame) -> (bool, str)`
- Full access to PySpark DataFrame API

### ✅ Clear Reporting
- ✓ Pass
- ✗ Fail (ERROR)
- ⚠ Fail (WARN)
- Detailed messages

### ✅ Zero Configuration
- Just add `@expect` decorators
- Checks registered automatically
- Runs without extra setup

---

## Architecture

```
┌─────────────────────────────────────┐
│ @expect decorators                  │
│ (User defines checks in code)       │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│ QualityRegistry                     │
│ (Stores all checks globally)        │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│ PipelineRunner                      │
│ (Executes checks after pipeline)    │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│ Quality Check Execution              │
│ - Run each check function            │
│ - Collect results                    │
│ - Fail pipeline if ERROR checks fail │
└──────────────────────────────────────┘
```

---

## Files Created

```
src/alur/quality/
  └── __init__.py              (350 lines - complete quality module)

src/alur/engine/
  └── runner.py                (modified - added quality check integration)

src/alur/
  └── __init__.py              (modified - export quality module)

examples/
  └── pipelines/with_quality_checks.py   (comprehensive examples)

docs/
  ├── DATA_QUALITY.md          (complete user guide)
  └── QUALITY_SUMMARY.md       (this file)
```

---

## Next Steps

Users can now:

1. **Add quality checks** to any pipeline with `@expect` decorator
2. **Use built-in checks** for common validations
3. **Write custom checks** for business-specific rules
4. **Control severity** (ERROR vs WARN) per check
5. **See clear feedback** when checks pass/fail

Quality checks integrate seamlessly with:
- Contract field constraints (schema)
- Pipeline transformations (business logic)
- EventBridge scheduling (automated runs)
- All deployment environments (dev/prod)

---

## Benefits

### For Data Engineers
- Catch data issues immediately
- Validate business rules automatically
- No manual data inspection needed
- Clear error messages for debugging

### For Data Analysts
- Trust the data quality
- Fewer surprises in reports
- Known data constraints
- Documented expectations

### For DevOps
- Infrastructure as code
- Version-controlled checks
- Automated validation
- CI/CD integration ready

---

## Complete!

Data Quality Checks are now fully integrated into the Alur framework! 🎉

See [DATA_QUALITY.md](./DATA_QUALITY.md) for complete documentation.
