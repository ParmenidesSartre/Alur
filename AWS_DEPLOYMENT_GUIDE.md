# AWS Deployment Guide - How Your Code Runs

This guide explains how your Python code actually runs in AWS Glue.

## Overview

```
┌─────────────────────┐
│  Your Project       │
│  (Python Code)      │
└──────────┬──────────┘
           │
           │ pip install build
           │ python -m build
           ▼
┌─────────────────────┐
│  Wheel Package      │
│  project-0.1.0.whl  │
└──────────┬──────────┘
           │
           │ Upload to S3
           ▼
┌─────────────────────┐
│  S3 Artifacts       │
│  + driver.py        │
│  + your_project.whl │
└──────────┬──────────┘
           │
           │ AWS Glue Job References
           ▼
┌─────────────────────┐
│  AWS Glue Job       │
│  Runs driver.py     │
└──────────┬──────────┘
           │
           │ Imports and Executes
           ▼
┌─────────────────────┐
│  Your Pipeline      │
│  Processes Data     │
└─────────────────────┘
```

## Step-by-Step Deployment

### Phase 1: Package Your Project

Your project needs to be a proper Python package.

**Project Structure:**
```
my_datalake/
├── setup.py or pyproject.toml
├── config/
├── contracts/
└── pipelines/
```

**Create `setup.py`:**
```python
from setuptools import setup, find_packages

setup(
    name="my_datalake",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "alur-framework>=0.1.0",
    ],
)
```

**Or use `pyproject.toml`:**
```toml
[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"

[project]
name = "my_datalake"
version = "0.1.0"
dependencies = [
    "alur-framework>=0.1.0",
]
```

**Build the wheel:**
```bash
pip install build
python -m build
# Creates: dist/my_datalake-0.1.0-py3-none-any.whl
```

### Phase 2: Upload to S3

Upload your wheel and the driver script:

```bash
# Upload your project wheel
aws s3 cp dist/my_datalake-0.1.0-py3-none-any.whl \
    s3://alur-artifacts-dev/wheels/

# Upload the Alur driver script
aws s3 cp driver.py s3://alur-artifacts-dev/scripts/driver.py
```

The driver.py script is located at:
```
alur-framework/src/alur/templates/aws/driver.py
```

### Phase 3: Create Glue Job

You can create the Glue job using:

**A. AWS Console:**
1. Go to AWS Glue Console
2. Jobs → Create Job
3. Configure:
   - **Script location**: `s3://alur-artifacts-dev/scripts/driver.py`
   - **Python library path**: `s3://alur-artifacts-dev/wheels/my_datalake-0.1.0-py3-none-any.whl`
   - **Job parameters**:
     - `--pipeline_name`: `clean_orders`
   - **IAM Role**: Choose role with S3, Glue access
   - **Glue version**: 4.0
   - **Language**: Python 3

**B. AWS CLI:**
```bash
aws glue create-job \
  --name "alur-clean-orders" \
  --role "AWSGlueServiceRole" \
  --command '{
    "Name": "glueetl",
    "ScriptLocation": "s3://alur-artifacts-dev/scripts/driver.py",
    "PythonVersion": "3"
  }' \
  --default-arguments '{
    "--pipeline_name": "clean_orders",
    "--extra-py-files": "s3://alur-artifacts-dev/wheels/my_datalake-0.1.0-py3-none-any.whl"
  }' \
  --glue-version "4.0" \
  --number-of-workers 2 \
  --worker-type "G.1X"
```

**C. Terraform (Recommended):**

Add to your Terraform:

```hcl
# glue_jobs.tf

resource "aws_glue_job" "clean_orders" {
  name     = "alur-clean-orders"
  role_arn = aws_iam_role.glue_role.arn
  glue_version = "4.0"

  command {
    name            = "glueetl"
    script_location = "s3://alur-artifacts-dev/scripts/driver.py"
    python_version  = "3"
  }

  default_arguments = {
    "--pipeline_name" = "clean_orders"
    "--extra-py-files" = "s3://alur-artifacts-dev/wheels/my_datalake-0.1.0-py3-none-any.whl"
    "--enable-glue-datacatalog" = ""
  }

  number_of_workers = 2
  worker_type       = "G.1X"

  tags = {
    Pipeline = "clean_orders"
    ManagedBy = "Alur"
  }
}
```

### Phase 4: Run the Job

**Manually trigger:**
```bash
aws glue start-job-run --job-name alur-clean-orders
```

**Check status:**
```bash
aws glue get-job-runs --job-name alur-clean-orders
```

**View logs:**
- CloudWatch Logs → `/aws-glue/jobs/output`
- Look for: `[Alur Driver]` prefix

## How the Driver Script Works

When Glue runs, here's what happens:

### 1. Driver Script Starts
```python
# driver.py on S3
from awsglue.utils import getResolvedOptions
args = getResolvedOptions(sys.argv, ['pipeline_name'])
```

### 2. Imports Your Code
```python
# Your wheel is in PYTHONPATH via --extra-py-files
import pipelines  # This loads your pipelines module
```

### 3. Finds Your Pipeline
```python
from alur.decorators import PipelineRegistry
pipeline = PipelineRegistry.get("clean_orders")
```

### 4. Runs Your Pipeline
```python
from alur.engine import AWSAdapter, PipelineRunner
adapter = AWSAdapter()
runner = PipelineRunner(adapter)
runner.run_pipeline("clean_orders")
```

### 5. Your Code Executes
```python
# Your pipeline function from pipelines/orders.py
@pipeline(sources={"orders": OrdersBronze}, target=OrdersSilver)
def clean_orders(orders):
    return orders.filter(...)  # Your transformation
```

## Example: Complete Deployment

Here's a complete example from start to finish:

```bash
# 1. In your project directory
cd my_datalake

# 2. Build the wheel
python -m build

# 3. Upload to S3
aws s3 cp dist/my_datalake-0.1.0-py3-none-any.whl \
    s3://alur-artifacts-dev/wheels/

# 4. Upload driver.py (from Alur installation)
aws s3 cp $(python -c "import alur; print(alur.__path__[0])")/templates/aws/driver.py \
    s3://alur-artifacts-dev/scripts/

# 5. Create Glue job (using CLI)
aws glue create-job \
  --name "alur-clean-orders" \
  --role "arn:aws:iam::123456789012:role/GlueRole" \
  --command '{
    "Name": "glueetl",
    "ScriptLocation": "s3://alur-artifacts-dev/scripts/driver.py",
    "PythonVersion": "3"
  }' \
  --default-arguments '{
    "--pipeline_name": "clean_orders",
    "--extra-py-files": "s3://alur-artifacts-dev/wheels/my_datalake-0.1.0-py3-none-any.whl"
  }' \
  --glue-version "4.0"

# 6. Run it!
aws glue start-job-run --job-name alur-clean-orders

# 7. Check logs
aws logs tail /aws-glue/jobs/output --follow
```

## Automated Deployment Script

Create a `deploy.sh` script:

```bash
#!/bin/bash
set -e

PROJECT_NAME="my_datalake"
VERSION=$(python -c "import tomli; print(tomli.load(open('pyproject.toml', 'rb'))['project']['version'])")
BUCKET="alur-artifacts-dev"

echo "Deploying $PROJECT_NAME v$VERSION..."

# Build
echo "Building wheel..."
python -m build

# Upload
echo "Uploading to S3..."
aws s3 cp "dist/${PROJECT_NAME}-${VERSION}-py3-none-any.whl" \
    "s3://${BUCKET}/wheels/"

# Upload driver
echo "Uploading driver..."
DRIVER_PATH=$(python -c "import alur; import os; print(os.path.join(alur.__path__[0], 'templates/aws/driver.py'))")
aws s3 cp "$DRIVER_PATH" "s3://${BUCKET}/scripts/driver.py"

echo "✓ Deployment complete!"
echo "Run with: aws glue start-job-run --job-name alur-<pipeline-name>"
```

Make it executable:
```bash
chmod +x deploy.sh
./deploy.sh
```

## IAM Role Requirements

Your Glue job needs an IAM role with these permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::alur-bronze-dev/*",
        "arn:aws:s3:::alur-silver-dev/*",
        "arn:aws:s3:::alur-gold-dev/*",
        "arn:aws:s3:::alur-artifacts-dev/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "glue:GetDatabase",
        "glue:GetTable",
        "glue:CreateTable",
        "glue:UpdateTable",
        "glue:GetPartitions"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:GetItem",
        "dynamodb:PutItem",
        "dynamodb:UpdateItem"
      ],
      "Resource": "arn:aws:dynamodb:*:*:table/alur-state-dev"
    },
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:*:*:*"
    }
  ]
}
```

## Monitoring

### CloudWatch Logs

Glue writes logs to CloudWatch:
- `/aws-glue/jobs/output` - Standard output
- `/aws-glue/jobs/error` - Error logs

Look for these log messages:
```
[Alur Driver] Starting job: alur-clean-orders
[Alur Driver] Pipeline: clean_orders
[Alur Driver] Found 1 registered pipelines
[Alur Driver] Executing pipeline: clean_orders
[Alur] Reading source: orders (ordersbronze)
[Alur] Executing transformation: clean_orders
[Alur] Writing to target: orderssilver (mode=merge)
[Alur] Pipeline 'clean_orders' completed successfully
[Alur Driver] Pipeline 'clean_orders' completed successfully
```

### Check Job Status

```bash
# Get recent runs
aws glue get-job-runs --job-name alur-clean-orders --max-results 5

# Get specific run
aws glue get-job-run --job-name alur-clean-orders --run-id jr_abc123
```

## Cost Tracking

Each Glue job run costs:
- **Data Processing Units (DPU)**: $0.44 per DPU-hour
- **Minimum**: 2 DPUs (can configure 1 with G.1X)
- **Example**: 5-minute job with 2 DPUs = $0.44 × 2 × (5/60) = ~$0.07

Track costs:
```bash
aws ce get-cost-and-usage \
  --time-period Start=2026-01-01,End=2026-01-31 \
  --granularity MONTHLY \
  --metrics "UnblendedCost" \
  --filter file://filter.json
```

## Troubleshooting

**"Module not found: pipelines"**
- Check `--extra-py-files` points to correct wheel
- Verify wheel was built correctly

**"Pipeline 'X' not found"**
- Ensure pipeline is imported in your package
- Check `__init__.py` files import the pipeline modules

**"Access Denied" errors**
- Check IAM role permissions
- Verify S3 bucket policies

**Logs not appearing**
- Wait 1-2 minutes for logs to appear
- Check CloudWatch Logs in correct region

## Future: alur deploy Command

In Phase 4, this will be automated with:

```bash
alur deploy --env prod
```

Which will:
1. Build your project wheel
2. Upload to S3
3. Update/create Glue jobs
4. Handle versioning

But for now, use the manual steps above.

## Summary

**The flow is:**
1. Package your code → `.whl` file
2. Upload to S3 → artifacts bucket
3. Glue job references → driver.py + your .whl
4. Driver imports your code → runs pipeline
5. Pipeline processes data → writes to S3
6. Results available → in Glue Catalog

**Key files:**
- `driver.py` - Generic runner (provided by Alur)
- `your_project.whl` - Your packaged code
- Glue job definition - Points to both

This keeps your code separate from the execution environment, making updates easy!
