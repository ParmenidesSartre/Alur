"""
Data Quality Checks for Alur Framework.
Validate data quality at every stage of the pipeline.
"""

from typing import Callable, Optional, Dict, Any, List
from dataclasses import dataclass, field
from enum import Enum


class Severity(Enum):
    """Severity level for quality check failures."""
    WARN = "warn"      # Log warning but continue
    ERROR = "error"    # Fail the pipeline


@dataclass
class QualityCheck:
    """Represents a single data quality check."""

    name: str
    check_fn: Callable
    description: Optional[str] = None
    severity: Severity = Severity.ERROR
    enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class QualityResult:
    """Result of a quality check execution."""

    check_name: str
    passed: bool
    message: str
    severity: Severity
    metrics: Dict[str, Any] = field(default_factory=dict)


class QualityRegistry:
    """Global registry for data quality checks."""

    _checks: Dict[str, List[QualityCheck]] = {}

    @classmethod
    def register(cls, pipeline_name: str, check: QualityCheck) -> None:
        """Register a quality check for a pipeline."""
        if pipeline_name not in cls._checks:
            cls._checks[pipeline_name] = []

        cls._checks[pipeline_name].append(check)

    @classmethod
    def get_checks(cls, pipeline_name: str) -> List[QualityCheck]:
        """Get all checks for a pipeline."""
        return cls._checks.get(pipeline_name, [])

    @classmethod
    def get_all(cls) -> Dict[str, List[QualityCheck]]:
        """Get all registered checks."""
        return cls._checks.copy()

    @classmethod
    def clear(cls) -> None:
        """Clear all checks (useful for testing)."""
        cls._checks.clear()


def expect(
    name: str,
    check_fn: Callable,
    description: Optional[str] = None,
    severity: Severity = Severity.ERROR,
    enabled: bool = True,
    **metadata
):
    """
    Decorator to add data quality expectations to a pipeline.

    Checks run automatically after pipeline execution.
    Failed checks can warn or fail the pipeline based on severity.

    Args:
        name: Name of the quality check
        check_fn: Function that takes DataFrame and returns (bool, message)
        description: Human-readable description
        severity: WARN or ERROR (ERROR fails pipeline)
        enabled: Whether this check is active
        **metadata: Additional metadata for reporting

    Example:
        @expect(
            name="orders_not_empty",
            check_fn=lambda df: (df.count() > 0, "Orders table is empty"),
            description="Ensure orders table has data"
        )
        @pipeline(sources={"orders": OrdersBronze}, target=OrdersSilver)
        def clean_orders(orders):
            return orders.filter(...)

    Common Patterns:
        # Row count check
        check_fn=lambda df: (df.count() > 1000, f"Expected >1000 rows, got {df.count()}")

        # Null check
        check_fn=lambda df: (df.filter(col("id").isNull()).count() == 0, "Found null IDs")

        # Schema check
        check_fn=lambda df: ("amount" in df.columns, "Missing 'amount' column")
    """

    def decorator(func):
        # Get the pipeline name
        pipeline_name = func.__name__

        # Create quality check
        quality_check = QualityCheck(
            name=name,
            check_fn=check_fn,
            description=description or name,
            severity=severity,
            enabled=enabled,
            metadata=metadata
        )

        # Register the check
        QualityRegistry.register(pipeline_name, quality_check)

        # Attach metadata to function
        if not hasattr(func, '_alur_quality_checks'):
            func._alur_quality_checks = []

        func._alur_quality_checks.append(quality_check)

        return func

    return decorator


# Built-in quality check functions

def not_empty(df) -> tuple[bool, str]:
    """Check that DataFrame is not empty."""
    count = df.count()
    return (count > 0, f"DataFrame has {count} rows" if count > 0 else "DataFrame is empty")


def min_row_count(min_count: int):
    """Check that DataFrame has at least min_count rows."""
    def check(df) -> tuple[bool, str]:
        count = df.count()
        passed = count >= min_count
        msg = f"Row count {count} {'meets' if passed else 'below'} minimum {min_count}"
        return (passed, msg)
    return check


def max_row_count(max_count: int):
    """Check that DataFrame has at most max_count rows."""
    def check(df) -> tuple[bool, str]:
        count = df.count()
        passed = count <= max_count
        msg = f"Row count {count} {'within' if passed else 'exceeds'} maximum {max_count}"
        return (passed, msg)
    return check


def no_nulls_in_column(column_name: str):
    """Check that a column has no null values."""
    def check(df) -> tuple[bool, str]:
        from pyspark.sql.functions import col
        null_count = df.filter(col(column_name).isNull()).count()
        passed = null_count == 0
        msg = f"Column '{column_name}' has {null_count} null values"
        return (passed, msg)
    return check


def no_duplicates_in_column(column_name: str):
    """Check that a column has no duplicate values."""
    def check(df) -> tuple[bool, str]:
        total_count = df.count()
        distinct_count = df.select(column_name).distinct().count()
        passed = total_count == distinct_count
        duplicates = total_count - distinct_count
        msg = f"Column '{column_name}' has {duplicates} duplicate values"
        return (passed, msg)
    return check


def schema_has_columns(required_columns: List[str]):
    """Check that DataFrame has all required columns."""
    def check(df) -> tuple[bool, str]:
        actual_columns = set(df.columns)
        required_set = set(required_columns)
        missing = required_set - actual_columns
        passed = len(missing) == 0

        if passed:
            msg = f"All required columns present: {required_columns}"
        else:
            msg = f"Missing columns: {list(missing)}"

        return (passed, msg)
    return check


def column_values_in_range(column_name: str, min_val: float, max_val: float):
    """Check that column values are within a range."""
    def check(df) -> tuple[bool, str]:
        from pyspark.sql.functions import col, min as spark_min, max as spark_max

        stats = df.agg(
            spark_min(col(column_name)).alias("min"),
            spark_max(col(column_name)).alias("max")
        ).collect()[0]

        actual_min = stats["min"]
        actual_max = stats["max"]

        passed = (actual_min >= min_val and actual_max <= max_val)

        msg = (f"Column '{column_name}' range [{actual_min}, {actual_max}] "
               f"{'within' if passed else 'outside'} expected [{min_val}, {max_val}]")

        return (passed, msg)
    return check


def column_matches_pattern(column_name: str, pattern: str):
    """Check that column values match a regex pattern."""
    def check(df) -> tuple[bool, str]:
        from pyspark.sql.functions import col

        # Count rows that don't match pattern
        invalid_count = df.filter(~col(column_name).rlike(pattern)).count()
        passed = invalid_count == 0

        msg = (f"Column '{column_name}' has {invalid_count} values "
               f"not matching pattern '{pattern}'")

        return (passed, msg)
    return check


def row_count_increased_since_last_run(min_increase: int = 0):
    """
    Check that row count increased since last run.
    Requires state tracking (TODO: implement with DynamoDB).
    """
    def check(df) -> tuple[bool, str]:
        current_count = df.count()
        # TODO: Get previous count from state store
        # For now, always pass
        return (True, f"Current row count: {current_count} (state tracking not yet implemented)")
    return check


def freshness_check(timestamp_column: str, max_age_hours: int):
    """Check that data is fresh (most recent record within max_age_hours)."""
    def check(df) -> tuple[bool, str]:
        from pyspark.sql.functions import col, max as spark_max, current_timestamp, unix_timestamp
        from datetime import datetime, timedelta

        latest_ts = df.agg(spark_max(col(timestamp_column))).collect()[0][0]

        if latest_ts is None:
            return (False, f"No data in timestamp column '{timestamp_column}'")

        # Convert to datetime if needed
        if isinstance(latest_ts, str):
            latest_ts = datetime.fromisoformat(latest_ts.replace('Z', '+00:00'))

        age_hours = (datetime.now() - latest_ts).total_seconds() / 3600
        passed = age_hours <= max_age_hours

        msg = (f"Latest record is {age_hours:.1f} hours old "
               f"({'fresh' if passed else 'stale'}, max age {max_age_hours}h)")

        return (passed, msg)
    return check


__all__ = [
    # Core classes
    "QualityCheck",
    "QualityResult",
    "QualityRegistry",
    "Severity",
    # Decorator
    "expect",
    # Built-in checks
    "not_empty",
    "min_row_count",
    "max_row_count",
    "no_nulls_in_column",
    "no_duplicates_in_column",
    "schema_has_columns",
    "column_values_in_range",
    "column_matches_pattern",
    "row_count_increased_since_last_run",
    "freshness_check",
]
