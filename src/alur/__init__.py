"""
Alur Framework - A Python framework for building data lake pipelines.

This package provides tools for building scalable data lake pipelines
with Apache Iceberg and Spark, deployable on AWS infrastructure.
"""

from .core import (
    BaseTable,
    BronzeTable,
    SilverTable,
    GoldTable,
    StringField,
    IntegerField,
    LongField,
    DoubleField,
    BooleanField,
    TimestampField,
    DateField,
    DecimalField,
    ArrayField,
    StructField,
)

from .decorators import pipeline, PipelineRegistry

from .engine import (
    LocalAdapter,
    AWSAdapter,
    PipelineRunner,
    get_spark_session,
)

from .scheduling import schedule, ScheduleRegistry

from .quality import (
    expect,
    QualityRegistry,
    Severity,
    not_empty,
    min_row_count,
    max_row_count,
    no_nulls_in_column,
    no_duplicates_in_column,
    schema_has_columns,
    column_values_in_range,
    freshness_check
)

from .ingestion import (
    add_bronze_metadata,
    load_csv_to_bronze,
    load_json_to_bronze,
    load_parquet_to_bronze,
    handle_bad_records,
    IncrementalLoader
)

__version__ = "0.1.0"

__all__ = [
    # Table classes
    "BaseTable",
    "BronzeTable",
    "SilverTable",
    "GoldTable",
    # Field types
    "StringField",
    "IntegerField",
    "LongField",
    "DoubleField",
    "BooleanField",
    "TimestampField",
    "DateField",
    "DecimalField",
    "ArrayField",
    "StructField",
    # Decorators
    "pipeline",
    "PipelineRegistry",
    # Scheduling
    "schedule",
    "ScheduleRegistry",
    # Quality
    "expect",
    "QualityRegistry",
    "Severity",
    "not_empty",
    "min_row_count",
    "max_row_count",
    "no_nulls_in_column",
    "no_duplicates_in_column",
    "schema_has_columns",
    "column_values_in_range",
    "freshness_check",
    # Ingestion
    "add_bronze_metadata",
    "load_csv_to_bronze",
    "load_json_to_bronze",
    "load_parquet_to_bronze",
    "handle_bad_records",
    "IncrementalLoader",
    # Engine
    "LocalAdapter",
    "AWSAdapter",
    "PipelineRunner",
    "get_spark_session",
]
