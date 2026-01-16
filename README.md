# Alur Framework

**A Python framework for building scalable data lake pipelines with Apache Iceberg and Spark.**

[![Version](https://img.shields.io/badge/version-0.1.0--alpha-blue.svg)](https://pypi.org/project/alur-framework/)
[![Python](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

Alur is a Python package that simplifies building and deploying data lake pipelines. It provides:

- **Declarative table definitions** using Python classes (similar to Django ORM)
- **Type-safe schema management** with field validators
- **Pipeline orchestration** with automatic dependency resolution
- **Bronze ingestion helpers** for loading raw data with metadata tracking
- **Data quality checks** with automatic validation after pipeline execution
- **EventBridge scheduling** for automated pipeline runs
- **Local development mode** for testing without cloud resources
- **AWS deployment** with auto-generated Terraform infrastructure
- **Multi-layer architecture** (Bronze/Silver/Gold) built-in

## Table of Contents

- [Installation](#installation)
- [Quick Start](#quick-start)
- [Core Concepts](#core-concepts)
- [Usage Examples](#usage-examples)
- [CLI Commands](#cli-commands)
- [Deployment](#deployment)
- [Architecture](#architecture)
- [Contributing](#contributing)

## Installation

```bash
pip install alur-framework
```

**Requirements:**
- Python 3.8+
- PySpark 3.3+
- Java 8 or 11 (for Spark)

## Quick Start

### 1. Initialize a New Project

```bash
alur init my_datalake
cd my_datalake
```

This creates a project structure:

```
my_datalake/
├── config/
│   └── settings.py      # AWS and environment config
├── contracts/
│   ├── bronze.py        # Raw data table definitions
│   └── silver.py        # Cleaned data table definitions
├── pipelines/
│   └── orders.py        # Data transformation pipelines
└── main.py              # Entry point
```

### 2. Define Your Tables

**contracts/bronze.py:**

```python
from alur.core import BronzeTable, StringField, IntegerField, TimestampField

class OrdersBronze(BronzeTable):
    """Raw orders from the source system."""

    order_id = StringField(nullable=False)
    customer_id = StringField(nullable=False)
    amount = IntegerField(nullable=False)
    created_at = TimestampField(nullable=False)

    class Meta:
        partition_by = ["created_at"]
```

**contracts/silver.py:**

```python
from alur.core import SilverTable, StringField, IntegerField, TimestampField

class OrdersSilver(SilverTable):
    """Cleaned and deduplicated orders."""

    order_id = StringField(nullable=False)
    customer_id = StringField(nullable=False)
    amount = IntegerField(nullable=False)
    status = StringField(nullable=False)
    created_at = TimestampField(nullable=False)
    updated_at = TimestampField(nullable=False)

    class Meta:
        primary_key = ["order_id"]
        partition_by = ["created_at"]
```

### 3. Create a Pipeline

**pipelines/orders.py:**

```python
from alur.decorators import pipeline
from contracts.bronze import OrdersBronze
from contracts.silver import OrdersSilver
from pyspark.sql import functions as F

@pipeline(
    sources={"orders": OrdersBronze},
    target=OrdersSilver
)
def clean_orders(orders):
    """Clean and validate orders."""

    # Filter invalid records
    cleaned = orders.filter(
        (F.col("order_id").isNotNull()) &
        (F.col("amount") > 0)
    )

    # Add status and updated_at
    cleaned = cleaned.withColumn("status", F.lit("processed"))
    cleaned = cleaned.withColumn("updated_at", F.current_timestamp())

    return cleaned
```

### 4. Run Locally

```bash
python main.py
```

Or use the CLI:

```bash
alur run clean_orders --local
```

Data will be stored in `/tmp/alur/`.

### 5. Deploy to AWS

Deploy with a single command:

```bash
alur deploy --env dev
```

This automatically:
- Builds your Python wheel package
- Generates Terraform infrastructure
- Provisions AWS resources (S3, Glue, DynamoDB)
- Uploads your code to S3

See [DEPLOY.md](DEPLOY.md) for detailed deployment options.

## Core Concepts

### Table Layers

Alur implements a multi-layer architecture:

- **Bronze Layer** (`BronzeTable`): Raw, immutable data from sources
  - Format: Parquet
  - Write mode: Append-only

- **Silver Layer** (`SilverTable`): Cleaned, deduplicated data
  - Format: Iceberg
  - Write mode: Merge (ACID upserts)
  - Requires: `primary_key` definition

- **Gold Layer** (`GoldTable`): Business-level aggregates
  - Format: Iceberg
  - Write mode: Configurable (overwrite/merge)

### Field Types

```python
from alur.core import (
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
```

### Pipeline Decorator

The `@pipeline` decorator registers transformation functions:

```python
@pipeline(
    sources={"input1": Table1, "input2": Table2},
    target=OutputTable,
    resource_profile="large"  # Optional: for AWS resource sizing
)
def my_pipeline(input1, input2):
    # input1 and input2 are Spark DataFrames
    return transformed_data
```

### Dependency Resolution

Alur automatically builds a DAG from your pipelines and executes them in the correct order:

```bash
alur validate  # Check for circular dependencies
```

## CLI Commands

### Project Management

```bash
# Initialize new project
alur init <project_name>

# Validate pipeline DAG
alur validate

# Build distributable wheel
alur build
```

### Running Pipelines

```bash
# Run a specific pipeline locally
alur run clean_orders --local

# Run all pipelines
alur run --all

# Run in AWS mode
alur run clean_orders
```

### Infrastructure

```bash
# One-command deployment to AWS
alur deploy --env dev
alur deploy --env prod --auto-approve

# Deploy options
alur deploy --skip-terraform     # Just upload code
alur deploy --skip-build         # Use existing wheel

# Generate Terraform files only
alur infra generate
alur infra generate --output ./infrastructure
```

## Usage Examples

### Example 1: Bronze to Silver with Deduplication

```python
from alur.decorators import pipeline
from pyspark.sql import Window, functions as F

@pipeline(
    sources={"raw_users": UsersBronze},
    target=UsersSilver
)
def deduplicate_users(raw_users):
    """Keep only the latest record per user."""

    window = Window.partitionBy("user_id").orderBy(F.desc("updated_at"))

    return raw_users.withColumn("row_num", F.row_number().over(window)) \
                    .filter(F.col("row_num") == 1) \
                    .drop("row_num")
```

### Example 2: Multiple Sources

```python
@pipeline(
    sources={
        "orders": OrdersSilver,
        "customers": CustomersSilver
    },
    target=OrdersEnrichedGold
)
def enrich_orders(orders, customers):
    """Join orders with customer data."""

    return orders.join(customers, "customer_id", "left")
```

### Example 3: Incremental Processing

```python
@pipeline(
    sources={"events": EventsBronze},
    target=EventsSilver
)
def process_events(events):
    """Process only new events using watermark."""

    from alur.engine import LocalAdapter

    adapter = LocalAdapter()
    last_processed = adapter.get_state("events_watermark") or "1970-01-01"

    new_events = events.filter(F.col("event_time") > last_processed)

    # Update watermark
    max_time = new_events.agg(F.max("event_time")).collect()[0][0]
    if max_time:
        adapter.set_state("events_watermark", str(max_time))

    return new_events
```

## Deployment

### One-Command AWS Deployment

Deploy your entire data lake to AWS with a single command:

```bash
# Full deployment (infrastructure + code)
alur deploy --env dev

# Production deployment
alur deploy --env prod --auto-approve

# Just upload code changes
alur deploy --skip-terraform
```

The `alur deploy` command:
1. Builds your Python wheel package
2. Generates Terraform infrastructure files
3. Provisions AWS resources (S3, Glue, DynamoDB)
4. Uploads your code to S3
5. Provides next steps for running jobs

**See [DEPLOY.md](DEPLOY.md) for complete deployment documentation.**

### Local Development

```python
from alur.engine import LocalAdapter, PipelineRunner

adapter = LocalAdapter(base_path="/tmp/alur")
runner = PipelineRunner(adapter)
runner.run_all()
```

### Manual AWS Deployment

```python
from alur.engine import AWSAdapter, PipelineRunner

adapter = AWSAdapter(region="us-east-1")
runner = PipelineRunner(adapter)
runner.run_all()
```

### AWS Glue Job

Create a driver script for Glue:

```python
# driver.py
import sys
from awsglue.utils import getResolvedOptions
from alur.engine import AWSAdapter, PipelineRunner

# Import your pipelines
import pipelines

# Get arguments
args = getResolvedOptions(sys.argv, ['pipeline_name'])

# Run pipeline
adapter = AWSAdapter()
runner = PipelineRunner(adapter)
runner.run_pipeline(args['pipeline_name'])
```

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                  User Project                       │
│                                                     │
│  ┌──────────┐  ┌───────────┐  ┌──────────────┐   │
│  │contracts/│  │ pipelines/ │  │   config/    │   │
│  └──────────┘  └───────────┘  └──────────────┘   │
└─────────────────────────────────────────────────────┘
                       │
                       │ uses
                       ▼
┌─────────────────────────────────────────────────────┐
│               Alur Framework                        │
│                                                     │
│  ┌──────────┐  ┌───────────┐  ┌──────────────┐   │
│  │   Core   │  │ Decorators│  │    Engine    │   │
│  │(Tables)  │  │(Pipeline) │  │(Adapters)    │   │
│  └──────────┘  └───────────┘  └──────────────┘   │
└─────────────────────────────────────────────────────┘
                       │
                       │
        ┌──────────────┴──────────────┐
        │                             │
        ▼                             ▼
┌──────────────┐            ┌──────────────────┐
│    Local     │            │       AWS        │
│ /tmp/alur/   │            │  S3 + Glue +     │
│   SQLite     │            │    DynamoDB      │
└──────────────┘            └──────────────────┘
```

## Project Status

**Current Version:** 0.1.0-alpha

**Phase 1 (Completed):**
- ✅ Core table contracts (BaseTable, BronzeTable, SilverTable, GoldTable)
- ✅ Field type system
- ✅ Pipeline decorator and registry
- ✅ LocalAdapter for development
- ✅ SparkSession factory
- ✅ CLI with `init`, `run`, `validate`, `infra generate` commands
- ✅ Project templates

**Phase 2 (Upcoming):**
- Iceberg MERGE implementation for Silver tables
- PostgreSQL source connector
- Watermark/state management
- DAG visualization

**Phase 3 (Planned):**
- AWSAdapter with full Glue integration
- Advanced Terraform templates
- EMR Serverless support
- `alur deploy` command

**Phase 4 (Future):**
- More source connectors (MySQL, REST APIs, Kafka)
- Data quality validations
- Lineage tracking
- Web UI for monitoring

## Contributing

Contributions are welcome! Please open an issue or submit a pull request.

### Development Setup

```bash
git clone https://github.com/alur-framework/alur-framework
cd alur-framework
pip install -e ".[dev]"
pytest
```

## License

MIT License - see LICENSE file for details.

## Support

- Documentation: [GitHub Wiki](https://github.com/alur-framework/alur-framework/wiki)
- Issues: [GitHub Issues](https://github.com/alur-framework/alur-framework/issues)
- Discussions: [GitHub Discussions](https://github.com/alur-framework/alur-framework/discussions)
