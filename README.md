# Alur Framework

**A Python framework for building scalable data lake pipelines with Apache Iceberg and Spark.**

[![Version](https://img.shields.io/badge/version-0.1.0-blue.svg)](https://github.com/ParmenidesSartre/Alur/releases)
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
- [Testing Your Installation](#testing-your-installation)
- [Core Concepts](#core-concepts)
- [Usage Examples](#usage-examples)
- [CLI Commands](#cli-commands)
- [Deployment](#deployment)
- [Documentation](#documentation)
- [Contributing](#contributing)

## Installation

### From Source (Recommended)

```bash
# Clone the repository
git clone https://github.com/ParmenidesSartre/Alur.git
cd Alur

# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in development mode
pip install -e .

# Or install with all dependencies
pip install -e ".[all]"
```

### Requirements

- **Python 3.8+**
- **Java 8 or 11** (required for PySpark)
- **PySpark 3.3+** (installed automatically with `[all]` option)

### Verify Installation

```bash
# Check version
python -c "import alur; print(alur.__version__)"

# Verify CLI is available
alur --help
```

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
│   ├── ingest_orders.py # Bronze ingestion pipeline
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

    # Bronze metadata (added automatically by ingestion helpers)
    _ingested_at = TimestampField(nullable=True)
    _source_system = StringField(nullable=True)
    _source_file = StringField(nullable=True)

    class Meta:
        partition_by = ["created_at"]
```

### 3. Create a Pipeline

**pipelines/orders.py:**

```python
from alur.decorators import pipeline
from alur.quality import expect, not_empty, no_nulls_in_column
from contracts.bronze import OrdersBronze
from contracts.silver import OrdersSilver
from pyspark.sql import functions as F

@expect(name="has_data", check_fn=not_empty)
@expect(name="valid_ids", check_fn=no_nulls_in_column("order_id"))
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

    # Drop Bronze metadata
    cleaned = cleaned.drop("_ingested_at", "_source_system", "_source_file")

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

```bash
alur deploy --env dev
```

## Testing Your Installation

### Quick Test

```bash
# Create a test project
alur init test_project
cd test_project

# Run the example pipeline locally (requires Java for Spark)
python main.py
```

### Test Without Spark (Verify Import)

```python
# test_import.py
from alur import (
    BronzeTable, SilverTable, GoldTable,
    StringField, IntegerField, TimestampField,
    pipeline, expect, schedule,
    add_bronze_metadata
)

print("All imports successful!")

# Define a simple table
class TestTable(BronzeTable):
    id = StringField(nullable=False)
    name = StringField(nullable=True)

    class Meta:
        description = "Test table"

print(f"Table name: {TestTable.get_table_name()}")
print(f"Fields: {list(TestTable._fields.keys())}")
```

Run it:

```bash
python test_import.py
```

### Full Integration Test (Requires Java)

```python
# test_full.py
from alur import (
    BronzeTable, StringField, IntegerField, TimestampField,
    pipeline, add_bronze_metadata, get_spark_session
)
from pyspark.sql import functions as F

# 1. Define Bronze table
class TestOrdersBronze(BronzeTable):
    order_id = StringField(nullable=False)
    amount = IntegerField(nullable=True)
    _ingested_at = TimestampField(nullable=True)
    _source_system = StringField(nullable=True)

# 2. Create Spark session
spark = get_spark_session()

# 3. Create test data
test_data = [
    {"order_id": "ORD-001", "amount": 100},
    {"order_id": "ORD-002", "amount": 200},
    {"order_id": "ORD-003", "amount": 150},
]

df = spark.createDataFrame(test_data)

# 4. Add Bronze metadata
bronze_df = add_bronze_metadata(
    df,
    source_system="test_system",
    source_file="test_data.json"
)

# 5. Show results
print("Bronze data with metadata:")
bronze_df.show(truncate=False)

print("\nSchema:")
bronze_df.printSchema()

print("\n✅ Integration test passed!")
```

Run it:

```bash
python test_full.py
```

### Run Unit Tests

```bash
# From the Alur directory
pip install pytest
pytest tests/ -v
```

## Core Concepts

### Table Layers

| Layer | Class | Format | Write Mode | Purpose |
|-------|-------|--------|------------|---------|
| Bronze | `BronzeTable` | Parquet | Append | Raw data + metadata |
| Silver | `SilverTable` | Iceberg | Merge | Cleaned, validated |
| Gold | `GoldTable` | Iceberg | Overwrite | Business aggregates |

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

### Decorators

```python
from alur import pipeline, expect, schedule

# Pipeline decorator
@pipeline(sources={"input": InputTable}, target=OutputTable)
def transform(input):
    return input.filter(...)

# Data quality checks
@expect(name="not_empty", check_fn=not_empty)
@pipeline(...)
def validated_transform(input):
    return input

# Scheduled execution (AWS EventBridge)
@schedule(cron="cron(0 2 * * ? *)", description="Daily at 2am")
@pipeline(...)
def scheduled_transform(input):
    return input
```

## CLI Commands

```bash
# Project Management
alur init <project_name>    # Initialize new project
alur validate               # Validate pipeline DAG
alur list                   # List all pipelines

# Running Pipelines
alur run <pipeline> --local # Run locally
alur run <pipeline>         # Run on AWS Glue
alur logs <pipeline>        # View CloudWatch logs

# Deployment
alur deploy --env dev       # Deploy to AWS
alur infra generate         # Generate Terraform only
alur destroy --env dev      # Destroy infrastructure
```

## Documentation

| Document | Description |
|----------|-------------|
| [docs/DEPLOY.md](docs/DEPLOY.md) | AWS deployment guide |
| [docs/BRONZE_INGESTION.md](docs/BRONZE_INGESTION.md) | Bronze layer best practices |
| [docs/DATA_QUALITY.md](docs/DATA_QUALITY.md) | Data quality checks |
| [docs/LOCAL_TESTING.md](docs/LOCAL_TESTING.md) | Local development |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Development workflow |
| [CHANGELOG.md](CHANGELOG.md) | Version history |

## Project Status

**Current Version:** 0.1.0

### Implemented Features

- ✅ Core table contracts (BronzeTable, SilverTable, GoldTable)
- ✅ Type-safe field system (10+ field types)
- ✅ Pipeline decorator with dependency injection
- ✅ Bronze ingestion helpers with metadata
- ✅ Data quality checks (@expect decorator)
- ✅ EventBridge scheduling (@schedule decorator)
- ✅ CLI commands (init, run, deploy, logs, validate, list, destroy)
- ✅ LocalAdapter for development
- ✅ AWSAdapter with Glue integration
- ✅ Auto-generated Terraform infrastructure
- ✅ One-command deployment (`alur deploy`)

### Planned Features

- Schema evolution support
- More source connectors (MySQL, Kafka, REST APIs)
- Data lineage tracking
- Web UI for monitoring

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development workflow and guidelines.

```bash
# Development setup
git clone https://github.com/ParmenidesSartre/Alur.git
cd Alur
pip install -e ".[dev]"
pytest
```

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Links

- **Repository**: https://github.com/ParmenidesSartre/Alur
- **Issues**: https://github.com/ParmenidesSartre/Alur/issues
- **Releases**: https://github.com/ParmenidesSartre/Alur/releases
