# Alur Framework

**A production-ready Python framework for building cost-effective data lake pipelines with Apache Spark on AWS.**

[![Version](https://img.shields.io/badge/version-0.7.4-blue.svg)](https://github.com/ParmenidesSartre/Alur/releases)
[![Python](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](https://github.com/ParmenidesSartre/Alur/blob/main/LICENSE)
[![PyPI](https://img.shields.io/pypi/v/alur-framework.svg)](https://pypi.org/project/alur-framework/)

## Overview

Alur is a production-ready framework for building modern data lake architectures on AWS. Designed with developer experience and operational simplicity in mind, Alur enables data teams to build robust, scalable data pipelines without infrastructure complexity.

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

## Quick Start

### Installation

```bash
pip install alur-framework
```

### Initialize a Project

```bash
alur init my_datalake
cd my_datalake
```

### Define a Table

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

### Create a Pipeline

```python
from alur import schedule, pipeline
from alur.ingestion import load_to_bronze
from contracts.bronze import OrdersBronze

@schedule(cron="0 2 * * ? *", description="Daily order ingestion")
@pipeline(sources={}, target=OrdersBronze)
def ingest_orders():
    """Daily ingestion of orders with automatic scheduling."""
    spark = get_spark_session()

    return load_to_bronze(
        spark,
        source_path="s3://landing-zone/orders/*.csv",
        source_system="sales_db",
        target=OrdersBronze,
        enable_idempotency=True
    )
```

### Deploy to AWS

```bash
alur deploy --env production
```

## Target Audience

- Small and mid-size companies building their first data lake
- Organizations seeking cost-effective alternatives to expensive enterprise platforms
- Teams without dedicated data infrastructure engineers
- Companies requiring modern data capabilities without operational complexity

## Core Philosophy

- **Zero Idle Costs** - Built on AWS serverless infrastructure (Glue, S3, Lambda), you only pay when pipelines run
- **Accessible Technology** - Enterprise-grade capabilities without enterprise complexity
- **Developer-First** - Python-based declarative API that feels familiar to application developers
- **Production-Ready** - Built-in best practices for data quality, lineage, and reliability

## Next Steps

- [Installation Guide](getting-started/installation.md)
- [Quick Start Tutorial](getting-started/quickstart.md)
- [Core Concepts](getting-started/concepts.md)
- [Bronze Ingestion Guide](user-guide/bronze-ingestion.md)
- [Scheduling Guide](user-guide/scheduling.md)

## Community

- [GitHub Repository](https://github.com/ParmenidesSartre/Alur)
- [Issue Tracker](https://github.com/ParmenidesSartre/Alur/issues)
- [Changelog](CHANGELOG.md)
- [Contributing Guide](CONTRIBUTING.md)

## License

This project is licensed under the MIT License. See the [LICENSE](https://github.com/ParmenidesSartre/Alur/blob/main/LICENSE) file for details.
