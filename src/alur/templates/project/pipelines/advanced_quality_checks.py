"""
Advanced quality check patterns for Silver layer.

Demonstrates:
- Multi-column validation
- Cross-table referential integrity
- Time-series freshness checks
- Business rule validation
- Custom quality check functions

Use these patterns to ensure data quality at the Silver layer
before data flows to Gold aggregations.
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

    Args:
        foreign_key_col: Column in current table (e.g., "customer_id")
        reference_table: Fully qualified table name (e.g., "silver_layer.customers")
        reference_col: Column in reference table (e.g., "id")

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

    Useful for validating calculations like: subtotal + tax + shipping = total

    Args:
        sum_columns: List of columns to sum
        total_column: Column containing expected total
        tolerance: Acceptable difference (default 0.01)

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

    Prevents data entry errors or system clock issues.

    Args:
        date_column: Name of date/timestamp column to check

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


def percentage_in_range(
    column: str,
    min_pct: float = 0.0,
    max_pct: float = 100.0
) -> QualityCheck:
    """
    Check that percentage values are within valid range.

    Args:
        column: Column containing percentage values
        min_pct: Minimum valid percentage (default 0.0)
        max_pct: Maximum valid percentage (default 100.0)

    Example:
        @expect(percentage_in_range("discount_percentage", min_pct=0, max_pct=50))
    """
    def check(df: DataFrame) -> tuple[bool, str]:
        out_of_range = df.filter(
            (F.col(column) < min_pct) | (F.col(column) > max_pct)
        )
        invalid_count = out_of_range.count()

        if invalid_count > 0:
            samples = out_of_range.select(column).limit(5).collect()
            sample_values = [row[0] for row in samples]
            return False, (
                f"Found {invalid_count} values in '{column}' outside range [{min_pct}, {max_pct}]. "
                f"Samples: {sample_values}"
            )

        return True, f"All values in '{column}' within range [{min_pct}, {max_pct}]"

    return check


def min_distinct_count(
    column: str,
    min_count: int
) -> QualityCheck:
    """
    Check that column has at least min_count distinct values.

    Useful for detecting data quality issues like all records having same value.

    Args:
        column: Column to check
        min_count: Minimum number of distinct values expected

    Example:
        @expect(min_distinct_count("product_id", min_count=10))
    """
    def check(df: DataFrame) -> tuple[bool, str]:
        distinct_count = df.select(column).distinct().count()

        if distinct_count < min_count:
            return False, (
                f"Column '{column}' has only {distinct_count} distinct values, "
                f"expected at least {min_count}"
            )

        return True, f"Column '{column}' has {distinct_count} distinct values (>= {min_count})"

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
@expect(sum_equals_total(["subtotal", "tax", "shipping"], "total_amount"), severity="WARN")
@expect(percentage_in_range("discount_percentage", min_pct=0, max_pct=50), severity="WARN")
@expect(min_distinct_count("product_id", min_count=5), severity="WARN")
def transform_orders_advanced(spark: SparkSession) -> DataFrame:
    """
    Orders transformation with comprehensive quality validation.

    Quality checks enforce:
    1. Required fields (order_id, customer_id, order_date)
    2. Freshness (data not older than 48 hours)
    3. No future dates (prevents data entry errors)
    4. Reasonable value ranges (total_amount between 0 and 1M)
    5. Mathematical consistency (subtotal + tax + shipping = total)
    6. Percentage validation (discount between 0-50%)
    7. Data variety (at least 5 distinct products)
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
            "discount": 0.0,
            "discount_percentage": 0.0
        },
        filters=[
            F.col("total_amount").cast("decimal(10,2)") >= 0
        ],
        validate=True,
        source_bronze_table="orders"
    )

    # Add calculated fields
    silver_df = (silver_df
        .withColumn("order_year", F.year("order_date"))
        .withColumn("order_month", F.month("order_date"))
    )

    return silver_df


class OrdersSilver(SilverTable):
    """Silver orders with advanced validation."""
    order_id: str
    customer_id: str
    product_id: str
    order_date: datetime
    subtotal: float
    tax: float
    shipping: float
    discount: float
    discount_percentage: float
    total_amount: float
    status: str
    notes: str
    order_year: int
    order_month: int

    @classmethod
    def get_table_name(cls) -> str:
        return "orders"

    @classmethod
    def get_primary_key(cls) -> list:
        return ["order_id"]

    @classmethod
    def get_partition_by(cls) -> list:
        return ["order_year", "order_month"]


# ============================================================================
# Another Example: Customer Dimension with Referential Integrity
# ============================================================================

@pipeline(name="transform_customer_orders", layer="silver")
@expect(not_empty(), severity="ERROR")
@expect(no_nulls_in_column("order_id"), severity="ERROR")
@expect(no_nulls_in_column("customer_id"), severity="ERROR")
# Note: Referential integrity check requires silver_layer.customers to exist
# @expect(referential_integrity("customer_id", "silver_layer.customers", "customer_id"), severity="ERROR")
@expect(column_values_in_range("order_total", min_value=0), severity="ERROR")
def transform_customer_orders(spark: SparkSession) -> DataFrame:
    """
    Example showing referential integrity checks.

    This pipeline validates that all customer_id values in orders
    exist in the customers dimension table.

    Note: Uncomment the referential_integrity check above once
    silver_layer.customers table is populated.
    """
    bronze_df = spark.table("bronze_layer.customer_orders")

    silver_df = transform_to_silver(
        df=bronze_df,
        target=CustomerOrdersSilver,
        dedup_by=["order_id"],
        dedup_strategy="latest",
        fill_nulls_map={
            "shipping_address": "",
            "notes": ""
        },
        validate=True,
        source_bronze_table="customer_orders"
    )

    return silver_df


class CustomerOrdersSilver(SilverTable):
    """Customer orders with referential integrity to customers table."""
    order_id: str
    customer_id: str  # Foreign key to silver_layer.customers
    order_date: datetime
    order_total: float
    shipping_address: str
    notes: str

    @classmethod
    def get_table_name(cls) -> str:
        return "customer_orders"

    @classmethod
    def get_primary_key(cls) -> list:
        return ["order_id"]

    @classmethod
    def get_partition_by(cls) -> list:
        return ["year(order_date)"]
