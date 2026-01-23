# Alur Framework

**A production-ready Python framework for building cost-effective data lake pipelines with Apache Spark on AWS.**

[![Version](https://img.shields.io/badge/version-0.7.2-blue.svg)](https://github.com/ParmenidesSartre/Alur/releases)
[![Python](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

Alur is a production-ready framework for building modern data lake architectures on AWS. Designed with developer experience and operational simplicity in mind, Alur enables data teams to build robust, scalable data pipelines without infrastructure complexity.

## About This Project

Alur was developed as part of master's thesis research exploring accessible data lake architectures for small and mid-size organizations. Traditional data lake platforms often require significant capital investment, dedicated infrastructure teams, and complex operational overhead that place them out of reach for many organizations.

**Target Audience:**
- Small and mid-size companies building their first data lake
- Organizations seeking cost-effective alternatives to expensive enterprise platforms
- Teams without dedicated data infrastructure engineers
- Companies requiring modern data capabilities without operational complexity

**Core Philosophy:**
- **Zero Idle Costs** - Built on AWS serverless infrastructure (Glue, S3, Lambda), you only pay when pipelines run
- **Accessible Technology** - Enterprise-grade capabilities without enterprise complexity
- **Developer-First** - Python-based declarative API that feels familiar to application developers
- **Production-Ready** - Built-in best practices for data quality, lineage, and reliability

This framework demonstrates that modern data lake architectures can be both powerful and accessible to organizations of any size.

## Key Features

- **Declarative Table Definitions** - Define tables using Python classes with type-safe schema management
- **Production-Grade Bronze Ingestion** - Schema validation, automatic idempotency, multi-source support, and Parquet output
- **File-Level Idempotency** - DynamoDB-based state tracking prevents duplicate ingestion and saves costs
- **Multi-Source CSV Ingestion** - Ingest from multiple S3 locations in a single pipeline with independent tracking
- **Pipeline Orchestration** - Automatic dependency resolution with DAG-based execution
- **Automated Scheduling** - Cron-based pipeline scheduling via @schedule decorator with AWS EventBridge
- **Data Quality Validation** - Built-in quality checks with declarative expectations
- **AWS-Native Deployment** - One-command deployment with auto-generated Terraform infrastructure
- **Automatic Partition Registration** - Data immediately queryable in Athena after writes
- **Cost Optimization** - Serverless architecture with zero idle costs, pay only when pipelines run

## Table of Contents

- [Installation](#installation)
- [Quick Start](#quick-start)
- [Core Concepts](#core-concepts)
- [CLI Reference](#cli-reference)
- [Documentation](#documentation)
- [Development](#development)
- [Contributing](#contributing)
- [License](#license)

## Installation

### Requirements

- Python 3.8 or higher
- Java 8 or 11 (required for PySpark)
- AWS CLI configured (for deployment)

### From Source

```bash
# Clone the repository
git clone https://github.com/ParmenidesSartre/Alur.git
cd Alur

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install with all dependencies
pip install -e ".[all]"
```

### Install Options

```bash
# Core framework only
pip install -e .

# With all dependencies
pip install -e ".[all]"

# Development dependencies (includes testing tools)
pip install -e ".[dev]"
```

### Verify Installation

```bash
# Check version
alur --version

# View available commands
alur --help
```

## Quick Start

### Initialize a New Project

```bash
alur init my_datalake
cd my_datalake
```

This creates a structured project layout:

```
my_datalake/
├── config/
│   └── settings.py      # AWS and environment configuration
├── contracts/
│   ├── bronze.py        # Raw data table definitions
│   └── silver.py        # Cleaned data table definitions
└── pipelines/
    ├── ingest_orders.py # Bronze ingestion pipeline
    └── orders.py        # Data transformation pipelines
```

### Define Tables

**contracts/bronze.py:**

```python
from alur.core import BronzeTable, StringField, IntegerField, TimestampField

class OrdersBronze(BronzeTable):
    """Raw orders from the source system."""

    order_id = StringField(nullable=False)
    customer_id = StringField(nullable=False)
    amount = IntegerField(nullable=False)
    created_at = TimestampField(nullable=False)

    # Bronze metadata columns (added automatically by ingestion helpers)
    _ingested_at = TimestampField(nullable=True)
    _source_system = StringField(nullable=True)
    _source_file = StringField(nullable=True)

    class Meta:
        partition_by = ["created_at"]
```

### Create Pipelines

**pipelines/ingest_orders.py:**

```python
from alur.decorators import pipeline
from alur.ingestion import load_to_bronze
from alur.engine import get_spark_session
from contracts.bronze import OrdersBronze

@pipeline(sources={}, target=OrdersBronze)
def ingest_orders():
    """
    Production pattern: Bronze ingestion with safety features.

    - Schema validation prevents bad data
    - Idempotency prevents duplicate processing (saves costs)
    - Multi-source support for ingesting from multiple S3 locations
    - Automatic logging and metrics
    """
    spark = get_spark_session()

    # Multi-source ingestion example
    df = load_to_bronze(
        spark,
        source_path=[
            "s3://landing-zone/orders/*.csv",
            "s3://landing-zone/archive/*.csv"
        ],
        source_system="sales_db",
        target=OrdersBronze,           # Schema validation
        enable_idempotency=True,       # Skip already-processed files (default)
        validate=True,                 # Validate CSV headers
        strict_mode=False              # Log and skip bad files
    )

    return df
```

**pipelines/process_orders.py:**

```python
from alur.decorators import pipeline
from alur.quality import expect, not_empty, no_nulls_in_column
from contracts.bronze import OrdersBronze
from pyspark.sql import functions as F

@expect(name="has_data", check_fn=not_empty)
@expect(name="valid_ids", check_fn=no_nulls_in_column("order_id"))
@pipeline(sources={"orders": OrdersBronze}, target=OrdersBronze)
def process_orders(orders):
    """
    Clean and enrich orders data.

    Note: This example processes Bronze → Bronze for demonstration.
    Silver/Gold layers are on the roadmap.
    """

    # Filter invalid records
    cleaned = orders.filter(
        (F.col("order_id").isNotNull()) &
        (F.col("amount") > 0)
    )

    # Add processing metadata
    cleaned = cleaned.withColumn("processing_status", F.lit("validated"))
    cleaned = cleaned.withColumn("validated_at", F.current_timestamp())

    return cleaned
```

### Deploy to AWS

```bash
# Configure AWS settings in config/settings.py
# Then deploy with one command
alur deploy --env dev
```

This will:
1. Build Python wheel packages
2. Generate Terraform infrastructure code
3. Deploy AWS resources (S3, Glue, DynamoDB, IAM)
4. Upload code artifacts to S3
5. Create/update Glue jobs

## Core Concepts

### Table Layers

**Currently Implemented:**

| Layer | Class | Format | Write Mode | Purpose |
|-------|-------|--------|------------|---------|
| Bronze | `BronzeTable` | Parquet | Append | Raw data with automatic metadata and idempotency tracking |

**Note:** Silver and Gold layers with Apache Iceberg support are on the roadmap. Current focus is on production-ready Bronze ingestion with idempotency and multi-source support.

### Field Types

```python
from alur.core import (
    StringField,      # VARCHAR/STRING
    IntegerField,     # INT
    LongField,        # BIGINT
    DoubleField,      # DOUBLE
    BooleanField,     # BOOLEAN
    TimestampField,   # TIMESTAMP
    DateField,        # DATE
    DecimalField,     # DECIMAL(precision, scale)
    ArrayField,       # ARRAY<element_type>
    StructField,      # STRUCT<fields>
)
```

All fields support `nullable` parameter and optional `description` metadata.

### Pipeline Decorators

```python
from alur import pipeline, expect
from alur.quality import not_empty, no_nulls_in_column

# Basic pipeline
@pipeline(sources={"input": InputTable}, target=OutputTable)
def transform(input):
    return input.filter(...)

# With data quality checks
@expect(name="not_empty", check_fn=not_empty)
@expect(name="valid_ids", check_fn=no_nulls_in_column("order_id"))
@pipeline(sources={"input": InputTable}, target=OutputTable)
def validated_transform(input):
    return input.transform(...)
```

### Bronze Ingestion API

```python
from alur.ingestion import load_to_bronze, add_bronze_metadata
from contracts.bronze import OrdersBronze

# Single source with idempotency
df = load_to_bronze(
    spark,
    source_path="s3://bucket/orders/*.csv",
    source_system="sales_db",
    target=OrdersBronze,           # Required for schema validation
    enable_idempotency=True,       # Default: prevents duplicate ingestion
    validate=True,                 # Validate CSV headers
    strict_mode=False,             # Log and skip bad files
    options={"header": "true"}
)

# Multi-source ingestion
df = load_to_bronze(
    spark,
    source_path=[
        "s3://bucket/orders/*.csv",
        "s3://bucket/archive/*.csv"
    ],
    source_system="sales_db",
    target=OrdersBronze,
    enable_idempotency=True
)

# Manual metadata addition (for non-CSV sources)
bronze_df = add_bronze_metadata(
    df,
    source_system="api",
    exclude_metadata=["_source_file"],  # Exclude irrelevant metadata
    custom_metadata={"_api_version": "v2"}
)
```

## CLI Reference

### Project Management

```bash
alur init <project_name>    # Initialize new project
alur validate               # Validate pipeline DAG and dependencies
alur list                   # List all pipelines in project
```

### Pipeline Execution

```bash
alur run <pipeline>         # Run pipeline on AWS Glue
alur logs <pipeline>        # View CloudWatch logs for pipeline
```

### Deployment

```bash
alur build                  # Build Python wheel package
alur infra generate         # Generate Terraform files
alur deploy --env dev       # Full deployment (build + infra + upload)
alur deploy --auto-approve  # Deploy without confirmation prompts
alur destroy --env dev      # Destroy AWS infrastructure
```

### Options

```bash
# Deploy with specific flags
alur deploy --skip-build         # Skip wheel building
alur deploy --skip-terraform     # Skip Terraform apply
alur deploy --auto-approve       # Auto-approve Terraform changes
```

## Documentation

Comprehensive documentation is available in the `docs/` directory:

| Document | Description |
|----------|-------------|
| [docs/DEPLOY.md](docs/DEPLOY.md) | AWS deployment guide and best practices |
| [docs/BRONZE_INGESTION.md](docs/BRONZE_INGESTION.md) | Bronze layer ingestion patterns |
| [docs/DATA_QUALITY.md](docs/DATA_QUALITY.md) | Data quality validation framework |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Development workflow and guidelines |
| [CHANGELOG.md](CHANGELOG.md) | Version history and release notes |

## Development

### Setting Up Development Environment

```bash
# Clone and install with development dependencies
git clone https://github.com/ParmenidesSartre/Alur.git
cd Alur
pip install -e ".[dev]"
```

### Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=alur --cov-report=html
```

### Code Quality

```bash
# Format code
black src/alur

# Sort imports
isort src/alur

# Type checking
mypy src/alur
```

## Project Status

**Current Version:** 0.7.5 (Released 2026-01-23)

### Implemented Features

✅ **Bronze Layer (Production-Ready)**
- BronzeTable with Parquet format and Hive partitioning
- Type-safe field system with 10+ field types
- Pipeline decorator with automatic dependency injection
- Production-grade CSV ingestion:
  - File-level idempotency using DynamoDB state tracking
  - Multi-source CSV ingestion from multiple S3 locations
  - Schema validation against table contracts
  - CSV header validation with strict/non-strict modes
  - Automatic metadata columns (_ingested_at, _source_system, _source_file)
  - Built-in logging and metrics
- Data quality checks via @expect decorator
- Automated scheduling via @schedule decorator:
  - AWS EventBridge cron-based scheduling
  - Auto-generated EventBridge rules and IAM roles
  - Support for all pipeline layers (Bronze, Silver, Gold)
  - CLI command to list schedules
- Automatic partition registration in Glue Catalog
- Comprehensive CLI (init, run, deploy, logs, validate, list, destroy, schedules)
- AWSAdapter with AWS Glue integration
- Auto-generated Terraform infrastructure (S3, Glue, DynamoDB, IAM, EventBridge)
- One-command deployment workflow
- Pre-deployment validation and error checking

### Roadmap

🔜 **Near-Term**
- Silver/Gold layers with Apache Iceberg support
- Batch DynamoDB operations for better idempotency performance
- File version detection using S3 ETag comparison

📋 **Future**
- Schema evolution support for Iceberg tables
- Additional source connectors (MySQL, PostgreSQL, Kafka, REST APIs)
- Data lineage tracking and visualization
- Web UI for pipeline monitoring
- Enhanced observability and logging

## Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for development workflow, coding standards, and pull request guidelines.

### Quick Contribution Guide

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/your-feature`)
3. Make your changes with tests
4. Run tests and code quality checks
5. Submit a pull request

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## Links

- **GitHub Repository**: https://github.com/ParmenidesSartre/Alur
- **Issue Tracker**: https://github.com/ParmenidesSartre/Alur/issues
- **Releases**: https://github.com/ParmenidesSartre/Alur/releases
- **Changelog**: https://github.com/ParmenidesSartre/Alur/blob/main/CHANGELOG.md

## Support

For questions, bug reports, or feature requests, please open an issue on GitHub.

---

Built with Apache Spark, Apache Iceberg, and AWS Glue.
