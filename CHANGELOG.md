# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.6.0] - 2026-01-22

### Added
- **File-Level Idempotency for Bronze Ingestion** - Prevent duplicate ingestion of already-processed CSV files
  - DynamoDB-based state tracking (table: `alur-ingestion-state`)
  - Each file tracked by ingestion key (table name) + file path (S3 path)
  - Stores metadata: file size, S3 ETag, rows ingested, timestamp
  - Automatically skips already-processed files on pipeline re-runs
  - Enabled by default via `enable_idempotency=True` parameter
  - Safe for scheduled/automated pipelines
  - Minimal overhead (~100ms per pipeline run)
  - Cost: ~$0.03/month for 1000 files/day

- **Multi-Source CSV Ingestion** - Ingest from multiple S3 locations in a single pipeline
  - `source_path` parameter now accepts list of paths: `["s3://bucket1/*.csv", "s3://bucket2/*.csv"]`
  - All sources processed and tracked independently
  - Useful for backfills, archive ingestion, and multi-location data

- **State Management Methods in AWSAdapter**
  - `is_file_processed()` - Check if a file was already processed
  - `mark_file_processed()` - Mark file as successfully processed with metadata
  - `get_processed_files()` - Get all processed files for a table

### Changed
- **Default State Table Name** - Changed from `alur-state` to `alur-ingestion-state` for clarity
- **Parameter Naming** - Replaced `check_duplicates` with `enable_idempotency` in `load_to_bronze()` (more accurate name)

### Documentation
- Added comprehensive testing guide: `test_idempotency.md`
- Updated template pipeline to show idempotency and multi-source examples
- Covers usage, testing scenarios, troubleshooting, and best practices

## [0.5.0] - 2026-01-22

### Added
- **Automatic Partition Registration** - Data written to partitioned tables is now immediately queryable in Athena without manual `MSCK REPAIR TABLE` commands
  - Automatically runs `MSCK REPAIR TABLE` after each write operation
  - Eliminates common friction point for new users
  - Logged warnings if auto-registration fails (data still written successfully)

### Fixed
- **CSV Header Validation** - Files with missing required columns are now properly rejected before data ingestion
  - Prevents data corruption from column shifting
  - Validates headers against contract schema before reading data
  - Supports strict mode (fail immediately) and non-strict mode (log and skip)
- **Landing Bucket IAM Permissions** - Landing bucket permissions are now automatically included in Terraform-generated IAM policies
  - No manual IAM policy updates required
  - Landing bucket automatically created during deployment
- **Metadata Column Validation** - Fixed false validation errors about metadata columns (`_ingested_at`, `_source_system`, `_source_file`)
  - Metadata columns now properly excluded from schema validation
- **Windows CLI Support** - Replaced Unicode characters with ASCII for Windows cmd.exe compatibility
  - No more `UnicodeEncodeError` on Windows
- **Athena Database Structure** - Simplified database naming convention
  - Database now named `bronze_layer` (was `alur_bronze_{env}`)
  - One source = one table (no duplicate base class tables)
  - Easier to find and query data

### Changed
- **Table Format** - Using Parquet with Hive partitioning (simple, proven, widely compatible)
- **Database Naming** - All bronze tables now in `bronze_layer` database regardless of environment/project

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

### Planned
- Additional source connectors (MySQL, PostgreSQL, REST APIs, Kafka)
- Data lineage tracking
- Web UI for monitoring
- Cost optimization features
- Schema evolution support

---

## [0.4.0] - 2026-01-18

### 🔧 Fixed - CRITICAL BUGS

**This release fixes 9 critical bugs discovered during bronze layer testing.**
The framework was NOT production-ready before this version.

#### Major Architecture Fix - Bronze/Silver/Gold as Databases

**BEFORE (v0.3.x):**
- Single database: `alur_datalake_dev`
- Awkward table names: `ordersbronze`, `orderssilver`

**AFTER (v0.4.0):**
- Separate databases: `alur_bronze_dev`, `alur_silver_dev`, `alur_gold_dev`
- Clean table names: `orders`, `customers`, `products`

**Developer Impact**: NONE - existing code works unchanged.

#### Changes

- **Added** `BaseTableMeta._derive_clean_table_name()` - automatically strips layer suffixes
  - `OrdersBronze` → `orders`, `CustomersSilver` → `customers`
- **Added** `BaseTable.get_layer()` - auto-detect bronze/silver/gold from class hierarchy
- **Added** `BaseTable.get_database_name()` - generate correct database name per layer
- **Changed** Infrastructure generator creates 3 separate databases instead of 1
- **Fixed** S3 paths use clean table names: `s3://alur-bronze-dev/orders/`

#### Bug Fixes

1. **Fixed** `AttributeError: field.spark_type` - changed to `field.to_spark_type()`
2. **Fixed** DynamoDB schema mismatch - synchronized code and Terraform
3. **Fixed** `to_iceberg_schema()` method name in empty DataFrame creation
4. **Fixed** Framework wheel upload - auto-builds during deployment
5. **Fixed** Pipeline registry clearing - can now redeploy without restart
6. **Added** DynamoDB infrastructure auto-generation
7. **Added** DynamoDB IAM permissions to Glue role
8. **Fixed** S3 paths to use clean table names

#### SQL Examples

```sql
-- Before (v0.3.x):
SELECT * FROM alur_datalake_dev.ordersbronze;

-- After (v0.4.0):
SELECT * FROM alur_bronze_dev.orders;
SELECT * FROM alur_silver_dev.orders;
```

#### Migration

**No code changes required** - this is a library fix.

AWS resources will change:
- Database `alur_datalake_dev` → `alur_bronze_dev`, `alur_silver_dev`, `alur_gold_dev`
- Table `ordersbronze` → `orders` in `alur_bronze_dev`

**Recommendation**: Run `alur destroy` then redeploy.

---

## [0.3.0] - 2026-01-17

### Changed
- **BREAKING: Removed Local Testing Capabilities**
  - Removed `LocalAdapter` - framework is now AWS-only
  - Removed `--local` flag from `alur run` command
  - Removed `main.py` from project templates
  - Removed `local` optional dependency from pyproject.toml
  - Deleted docs/LOCAL_TESTING.md

### Rationale
Alur is designed as an AWS-native serverless framework. Local testing introduced complexity
and maintenance overhead without providing significant value for the target use case.
Users building data lakes on AWS benefit from testing directly in the cloud environment
where pipelines will run in production.

### Migration
If you were using `alur run <pipeline> --local`:
- Use `alur run <pipeline>` instead (runs on AWS Glue)
- All pipelines now execute on AWS infrastructure
- No local Spark installation required

---

## [0.2.0] - 2026-01-17

### Changed
- **BREAKING: Streamlined Bronze Ingestion API**
  - Consolidated `load_csv_to_bronze()`, `load_json_to_bronze()`, and `load_parquet_to_bronze()` into single `load_to_bronze()` function
  - Added automatic format detection from file extension
  - Simplified `add_bronze_metadata()` parameters: replaced three boolean flags (`add_ingestion_timestamp`, `add_source_system`, `add_source_file`) with single `exclude` list parameter
  - New API is more concise and easier to use while maintaining all functionality

### Added
- Pre-deployment validation to catch import errors before AWS deployment
- Import validation checks for broken module references in `__init__.py` files
- Enhanced error messages in deployment validation
- Comprehensive validation function to prevent deployment failures

### Fixed
- PathLib compatibility issues in framework wheel build on Windows
- Subprocess calls now properly handle Path objects as strings
- Framework wheel upload failures during deployment

### Improved
- Updated project templates to use new streamlined API
- Better deployment reliability with early validation
- Cleaner codebase with removed redundant documentation

---

## Version History

| Version | Date | Description |
|---------|------|-------------|
| 0.3.0 | 2026-01-17 | Removed local testing (breaking), AWS-only framework |
| 0.2.0 | 2026-01-17 | Streamlined bronze API (breaking), deployment fixes |
| 0.1.0 | 2026-01-16 | Initial release with core framework |

## Migration Guide

### From Pre-release to 0.1.0

This is the first official release. No migration needed.

## Contributors

- Alur Framework Contributors

## License

MIT License - see [LICENSE](LICENSE) for details.
