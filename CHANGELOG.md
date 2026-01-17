# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-01-16

### Added

#### Core Framework
- **Declarative Table Definitions** - Define data lake tables using Python classes (similar to Django ORM)
  - `BronzeTable` - Raw data tables (append-only, Parquet format)
  - `SilverTable` - Cleaned data tables (Iceberg format with ACID upserts)
  - `GoldTable` - Business aggregates (Iceberg format)
- **Type-Safe Field Types** - Strong typing for all schema fields
  - `StringField`, `IntegerField`, `LongField`, `DoubleField`
  - `BooleanField`, `TimestampField`, `DateField`, `DecimalField`
  - `ArrayField`, `StructField` for complex types
- **Pipeline Decorator** - Register transformations with `@pipeline` decorator
  - Automatic dependency injection
  - Source/target contract validation
  - Resource profile configuration

#### CLI Commands
- `alur init <project>` - Initialize new data lake projects
- `alur infra generate` - Generate Terraform infrastructure automatically
- `alur deploy --env <env>` - Deploy to AWS with single command
- `alur run <pipeline>` - Execute pipelines on AWS Glue
- `alur logs <pipeline>` - View CloudWatch logs
- `alur validate` - Validate contracts and pipelines
- `alur list` - List all registered pipelines
- `alur destroy` - Destroy AWS infrastructure

#### Bronze Ingestion Helpers
- `add_bronze_metadata()` - Add standard metadata fields (_ingested_at, _source_system, _source_file)
- `load_csv_to_bronze()` - Load CSV files with automatic metadata
- `load_json_to_bronze()` - Load JSON files with automatic metadata
- `load_parquet_to_bronze()` - Load Parquet files with automatic metadata
- `handle_bad_records()` - Save and filter corrupted records
- `IncrementalLoader` - Watermark-based incremental loading

#### Data Quality Checks
- `@expect` decorator for pipeline quality validation
- Built-in checks:
  - `not_empty` - Ensure data exists
  - `min_row_count` / `max_row_count` - Row count bounds
  - `no_nulls_in_column` - Null value detection
  - `no_duplicates_in_column` - Uniqueness validation
  - `schema_has_columns` - Schema validation
  - `column_values_in_range` - Range validation
  - `freshness_check` - Data freshness validation
- Severity levels: `ERROR` (fails pipeline) and `WARN` (logs only)
- Custom check function support

#### EventBridge Scheduling
- `@schedule` decorator for automated pipeline runs
- Cron expression support (AWS EventBridge format)
- Automatic infrastructure generation for scheduled pipelines
- IAM role and policy management

#### AWS Infrastructure (Terraform)
- S3 buckets for Bronze/Silver/Gold layers
- AWS Glue jobs with PySpark 3.x
- Glue Data Catalog tables
- DynamoDB for state management
- IAM roles and policies
- EventBridge rules for scheduling
- CloudWatch logging

#### Engine & Adapters
- `LocalAdapter` - Run pipelines locally for development
- `AWSAdapter` - Run pipelines on AWS Glue
- `PipelineRunner` - Execute pipelines with dependency resolution
- Automatic Spark session management

### Documentation
- README.md with quick start guide
- BRONZE_INGESTION.md - Bronze layer best practices
- DATA_QUALITY.md - Quality checks documentation
- PHASE1_IMPROVEMENTS.md - CLI and scheduling guide
- Example project templates

---

## [Unreleased]

### Changed
- **BREAKING: Streamlined Bronze Ingestion API**
  - Consolidated `load_csv_to_bronze()`, `load_json_to_bronze()`, and `load_parquet_to_bronze()` into single `load_to_bronze()` function
  - Added automatic format detection from file extension
  - Simplified `add_bronze_metadata()` parameters: replaced three boolean flags (`add_ingestion_timestamp`, `add_source_system`, `add_source_file`) with single `exclude` list parameter
  - New API is more concise and easier to use while maintaining all functionality

### Planned
- Additional source connectors (MySQL, PostgreSQL, REST APIs, Kafka)
- Data lineage tracking
- Web UI for monitoring
- Cost optimization features
- Schema evolution support

---

## Version History

| Version | Date | Description |
|---------|------|-------------|
| 0.1.0 | 2026-01-16 | Initial release with core framework |

## Migration Guide

### From Pre-release to 0.1.0

This is the first official release. No migration needed.

## Contributors

- Alur Framework Contributors

## License

MIT License - see [LICENSE](LICENSE) for details.
