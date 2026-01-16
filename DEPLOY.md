# Alur One-Command Deployment

Deploy your Alur data lake project to AWS with a single command.

## Overview

The `alur deploy` command handles the entire deployment workflow:

1. **Load Configuration** - Reads your project settings
2. **Build Python Wheel** - Packages your pipelines, contracts, and config
3. **Generate Terraform** - Creates infrastructure-as-code files
4. **Apply Terraform** - Provisions AWS resources (S3, Glue, DynamoDB)
5. **Upload to S3** - Deploys your code and driver script
6. **Summary** - Shows deployment details and next steps

## Quick Start

```bash
# Full deployment (dev environment)
cd my_data_lake
alur deploy --env dev

# Production deployment with auto-approval
alur deploy --env prod --auto-approve

# Just upload code (skip infrastructure)
alur deploy --skip-terraform

# Quick redeploy (reuse existing wheel)
alur deploy --skip-build --skip-terraform
```

## Prerequisites

### Required
- Python 3.8+
- AWS CLI configured with credentials
- Your Alur project initialized with `alur init`

### Optional
- Terraform (if not using --skip-terraform)
- `build` module: `pip install build`

## Command Options

| Option | Description |
|--------|-------------|
| `--env` | Environment name (dev, staging, prod). Default: dev |
| `--skip-build` | Skip building the wheel, use existing one in dist/ |
| `--skip-terraform` | Skip Terraform generation and apply |
| `--auto-approve` | Auto-approve Terraform changes (no confirmation) |

## What Gets Deployed

### Your Code (Wheel Package)
- `contracts/` - Your table definitions
- `pipelines/` - Your pipeline functions
- `config/` - Your configuration settings

**Location**: `s3://alur-artifacts-{env}/wheels/{project}-{version}.whl`

### Driver Script
Generic Glue execution script that loads your wheel and runs pipelines.

**Location**: `s3://alur-artifacts-{env}/scripts/driver.py`

### Infrastructure (if not skipped)
- S3 buckets: bronze, silver, gold, artifacts
- IAM roles: Glue execution role
- DynamoDB table: watermarks and state
- Glue catalog: databases for each layer

## Example Workflow

### First Deployment

```bash
# 1. Create your project
alur init my_datalake
cd my_datalake

# 2. Edit your contracts and pipelines
# ... edit contracts/bronze.py, contracts/silver.py
# ... edit pipelines/orders.py

# 3. Configure AWS settings
# Edit config/settings.py with your bucket names

# 4. Deploy everything
alur deploy --env dev
```

### Subsequent Updates

```bash
# Made code changes? Redeploy just the code
alur deploy --skip-terraform

# Test build without deploying
python -m build
```

## Output Example

```
============================================================
ALUR DEPLOYMENT - Environment: dev
============================================================

[1/6] Loading configuration...
  Region: us-east-1
  Artifacts bucket: alur-artifacts-dev

[2/6] Building Python wheel...
  [OK] Build complete
  Wheel: dist/my_datalake-0.1.0-py3-none-any.whl

[3/6] Generating Terraform files...
  [OK] Terraform files generated

[4/6] Applying Terraform...
  Running: terraform init...
  Running: terraform apply...
  [OK] Infrastructure deployed

[5/6] Uploading to S3...
  Uploading: dist/my_datalake-0.1.0-py3-none-any.whl
  To: s3://alur-artifacts-dev/wheels/my_datalake-0.1.0-py3-none-any.whl
  [OK] Wheel uploaded
  Uploading: driver.py
  [OK] Driver script uploaded

[6/6] Deployment Summary
  ========================================================
  Environment: dev
  Wheel: my_datalake-0.1.0-py3-none-any.whl
  S3 Location: s3://alur-artifacts-dev/wheels/my_datalake-0.1.0-py3-none-any.whl
  Region: us-east-1
  ========================================================

[OK] Deployment complete!

Next steps:
  1. Create Glue jobs pointing to:
     Script: s3://alur-artifacts-dev/scripts/driver.py
     Library: s3://alur-artifacts-dev/wheels/my_datalake-0.1.0-py3-none-any.whl
  2. Or use AWS Console to create jobs manually
  3. Run with: aws glue start-job-run --job-name <job-name>
```

## How Glue Jobs Work

Once deployed, create a Glue job with:

**Script location**: `s3://alur-artifacts-{env}/scripts/driver.py`
**Python library path**: `s3://alur-artifacts-{env}/wheels/{project}.whl`
**Job parameters**:
- `--pipeline_name`: Name of the pipeline to run (e.g., `clean_orders`)

The driver script:
1. Loads your wheel package
2. Finds the specified pipeline in the registry
3. Executes it with the AWS adapter
4. Writes results to S3 (silver/gold layers)

## Troubleshooting

### Build fails
```
[ERROR] 'build' module not found. Install: pip install build
```
**Solution**: `pip install build`

### Terraform not found
```
[ERROR] Terraform not found. Install from: https://www.terraform.io/downloads
```
**Solution**: Install Terraform or use `--skip-terraform`

### AWS CLI not found
```
[ERROR] AWS CLI not found. Install: pip install awscli
```
**Solution**: `pip install awscli` and configure credentials

### Bucket doesn't exist
```
[ERROR] Upload failed: The specified bucket does not exist
```
**Solution**: Run without `--skip-terraform` to create infrastructure first

### No wheel file found
```
[ERROR] No wheel file found. Run without --skip-build first
```
**Solution**: Remove `--skip-build` flag or run `python -m build` manually

## Cost Considerations

With `alur deploy`, you create:
- **S3 buckets**: $0.023/GB stored (first 50 TB)
- **Glue jobs**: $0.44/DPU-hour (only when running)
- **DynamoDB**: On-demand pricing (only when accessed)

**Idle cost**: $0.00 when not running jobs!

## Advanced: Multi-Environment Setup

```bash
# Deploy to multiple environments
alur deploy --env dev
alur deploy --env staging
alur deploy --env prod --auto-approve

# Use different AWS profiles
AWS_PROFILE=dev-account alur deploy --env dev
AWS_PROFILE=prod-account alur deploy --env prod
```

## See Also

- [AWS Deployment Guide](AWS_DEPLOYMENT_GUIDE.md) - Detailed architecture
- [Local Testing](LOCAL_TESTING.md) - Test before deploying
- [Quick Start](QUICKSTART.md) - Getting started guide
