# Alur Framework

**A Python framework for building scalable data lake pipelines with Apache Iceberg and Spark.**

[![Version](https://img.shields.io/badge/version-0.3.0-blue.svg)](https://github.com/ParmenidesSartre/Alur/releases)
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
- **Bronze Ingestion Helpers** - Streamlined API for loading raw data with automatic metadata tracking
- **Pipeline Orchestration** - Automatic dependency resolution with DAG-based execution
- **Data Quality Validation** - Built-in quality checks with declarative expectations
- **AWS-Native Deployment** - One-command deployment with auto-generated Terraform infrastructure
- **Multi-Layer Architecture** - Bronze/Silver/Gold pattern with Iceberg table format support
- **EventBridge Scheduling** - Declarative cron-based pipeline scheduling

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
    """Load raw orders from S3 into Bronze layer."""
    spark = get_spark_session()

    # Format auto-detected from file extension
    df = load_to_bronze(
        spark,
        source_path="s3://landing-zone/orders/*.csv",
        source_system="sales_db"
    )

    return df
```

**pipelines/orders.py:**

```python
from alur.decorators import pipeline
from alur.quality import expect, not_empty, no_nulls_in_column
from contracts.bronze import OrdersBronze
from contracts.silver import OrdersSilver
from pyspark.sql import functions as F

@expect(name="has_data", check_fn=not_empty)
@expect(name="valid_ids", check_fn=no_nulls_in_column("order_id"))
@pipeline(sources={"orders": OrdersBronze}, target=OrdersSilver)
def clean_orders(orders):
    """Clean and validate orders."""

    # Filter invalid records
    cleaned = orders.filter(
        (F.col("order_id").isNotNull()) &
        (F.col("amount") > 0)
    )

    # Add processing metadata
    cleaned = cleaned.withColumn("status", F.lit("processed"))
    cleaned = cleaned.withColumn("updated_at", F.current_timestamp())

    # Drop Bronze metadata columns
    cleaned = cleaned.drop("_ingested_at", "_source_system", "_source_file")

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

| Layer | Class | Format | Write Mode | Purpose |
|-------|-------|--------|------------|---------|
| Bronze | `BronzeTable` | Parquet | Append | Raw data with metadata tracking |
| Silver | `SilverTable` | Iceberg | Merge | Cleaned and validated data |
| Gold | `GoldTable` | Iceberg | Overwrite | Business-ready aggregates |

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
from alur import pipeline, expect, schedule

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

# With scheduled execution
@schedule(cron="cron(0 2 * * ? *)", description="Daily at 2am UTC")
@pipeline(sources={"input": InputTable}, target=OutputTable)
def scheduled_transform(input):
    return input.transform(...)
```

### Bronze Ingestion API

```python
from alur.ingestion import load_to_bronze, add_bronze_metadata

# Auto-detection of format from file extension
df = load_to_bronze(
    spark,
    source_path="s3://bucket/data/*.csv",
    source_system="sales_db",
    options={"header": "true"}
)

# Manual metadata addition
bronze_df = add_bronze_metadata(
    df,
    source_system="api",
    exclude=["_source_file"],  # Exclude irrelevant metadata
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

**Current Version:** 0.3.0

### Implemented Features

- Core table contracts (BronzeTable, SilverTable, GoldTable)
- Type-safe field system with 10+ field types
- Pipeline decorator with automatic dependency injection
- Streamlined bronze ingestion API with format auto-detection
- Data quality checks via @expect decorator
- EventBridge scheduling via @schedule decorator
- Comprehensive CLI (init, run, deploy, logs, validate, list, destroy)
- AWSAdapter with AWS Glue integration
- Auto-generated Terraform infrastructure
- One-command deployment workflow
- Pre-deployment validation and error checking

### Roadmap

- Schema evolution support for Iceberg tables
- Additional source connectors (MySQL, PostgreSQL, Kafka, REST APIs)
- Data lineage tracking and visualization
- Web UI for pipeline monitoring
- Cost optimization features
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
