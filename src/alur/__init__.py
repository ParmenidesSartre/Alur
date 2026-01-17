"""
Alur Framework - Cost-effective data lake framework for small and mid-size companies.

Alur is a production-ready framework designed to make modern data lake architectures
accessible to organizations without large data engineering teams. Built on AWS serverless
infrastructure, Alur eliminates idle costs while providing enterprise-grade capabilities.

The framework simplifies the complexity of building data pipelines by providing:
- Declarative table definitions with type safety
- Automated Bronze/Silver/Gold layer architecture
- One-command deployment to AWS with zero infrastructure management
- Built-in data quality validation and monitoring
- Pay-per-use pricing model (zero cost when not running)

Target Audience:
- Small and mid-size companies building their first data lake
- Organizations seeking cost-effective alternatives to expensive data platforms
- Teams without dedicated data infrastructure engineers
- Companies requiring modern data capabilities without operational overhead

This framework was developed as part of academic research exploring accessible
data lake architectures for resource-constrained organizations.
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
    load_to_bronze,
    handle_bad_records,
    IncrementalLoader
)

__version__ = "0.3.0"

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
    "load_to_bronze",
    "handle_bad_records",
    "IncrementalLoader",
    # Engine
    "AWSAdapter",
    "PipelineRunner",
    "get_spark_session",
]
