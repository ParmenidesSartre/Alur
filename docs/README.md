# Alur Framework Documentation

## Guides

| Document | Description |
|----------|-------------|
| [DEPLOY.md](DEPLOY.md) | Deployment commands and options |
| [AWS_DEPLOYMENT_GUIDE.md](AWS_DEPLOYMENT_GUIDE.md) | How code runs in AWS Glue |
| [BRONZE_INGESTION.md](BRONZE_INGESTION.md) | Bronze layer ingestion helpers |
| [SCHEDULING.md](SCHEDULING.md) | Pipeline scheduling with @schedule decorator |
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
│     S3      │  AWS Glue   │  DynamoDB   │  Glue SCHEDULED  │
│  (Storage)  │   (Spark)   │   (State)   │    (Triggers)    │
└─────────────┴─────────────┴─────────────┴──────────────────┘
```

## Layer Architecture

| Layer | Class | Format | Write Mode | Purpose |
|-------|-------|--------|------------|---------|
| Bronze | `BronzeTable` | Parquet | Append | Raw data + metadata |
| Silver | `SilverTable` | Iceberg | Merge | Cleaned, validated |
| Gold | `GoldTable` | Iceberg | Overwrite | Business aggregates |
