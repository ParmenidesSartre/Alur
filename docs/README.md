# Alur Framework Documentation

## Guides

| Document | Description |
|----------|-------------|
| [DEPLOY.md](DEPLOY.md) | Deployment commands and options |
| [AWS_DEPLOYMENT_GUIDE.md](AWS_DEPLOYMENT_GUIDE.md) | How code runs in AWS Glue |
| [LOCAL_TESTING.md](LOCAL_TESTING.md) | Local development and testing |
| [BRONZE_INGESTION.md](BRONZE_INGESTION.md) | Bronze layer ingestion helpers |
| [DATA_QUALITY.md](DATA_QUALITY.md) | Data quality checks with @expect |

## Quick Links

- [Main README](../README.md) - Project overview and quick start
- [CHANGELOG](../CHANGELOG.md) - Version history
- [CONTRIBUTING](../CONTRIBUTING.md) - Development workflow

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Your Project                            │
├──────────────┬──────────────┬──────────────┬───────────────┤
│  contracts/  │  pipelines/  │   config/    │    main.py    │
│  (Tables)    │  (Transform) │  (Settings)  │   (Entry)     │
└──────────────┴──────────────┴──────────────┴───────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Alur Framework                           │
├─────────────┬─────────────┬─────────────┬──────────────────┤
│    core/    │  decorators │   engine/   │     infra/       │
│  (Tables,   │  (@pipeline)│  (Runners,  │   (Terraform     │
│   Fields)   │             │   Adapters) │    Generator)    │
├─────────────┼─────────────┼─────────────┼──────────────────┤
│  ingestion/ │   quality/  │ scheduling/ │    sources/      │
│  (Bronze    │  (@expect)  │ (@schedule) │  (Connectors)    │
│   Helpers)  │             │             │                  │
└─────────────┴─────────────┴─────────────┴──────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                        AWS                                  │
├─────────────┬─────────────┬─────────────┬──────────────────┤
│     S3      │  AWS Glue   │  DynamoDB   │   EventBridge    │
│  (Storage)  │   (Spark)   │   (State)   │   (Scheduling)   │
└─────────────┴─────────────┴─────────────┴──────────────────┘
```

## Layer Architecture

| Layer | Class | Format | Write Mode | Purpose |
|-------|-------|--------|------------|---------|
| Bronze | `BronzeTable` | Parquet | Append | Raw data + metadata |
| Silver | `SilverTable` | Iceberg | Merge | Cleaned, validated |
| Gold | `GoldTable` | Iceberg | Overwrite | Business aggregates |
