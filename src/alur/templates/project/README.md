# Alur Data Lake Project

This project was generated using the Alur Framework.

## Project Structure

```
.
├── config/          # AWS configuration
├── contracts/       # Table definitions (Bronze, Silver, Gold)
└── pipelines/       # Data transformation pipelines
```

## Getting Started

### 1. Install Dependencies

```bash
pip install alur-framework
```

### 2. Configure AWS Settings

Edit `config/settings.py` with your AWS account details:
- AWS region
- S3 bucket names (must be globally unique)
- Glue database name
- DynamoDB state table name

### 3. Define Your Tables

Edit files in `contracts/` to define your data lake tables:
- `bronze.py` - Raw data tables
- `silver.py` - Cleaned, deduplicated tables
- `gold.py` - Business-level aggregates (optional)

### 4. Create Pipelines

Add transformation logic in `pipelines/` using the `@pipeline` decorator.

### 5. Deploy to AWS

Deploy your project with one command:

```bash
alur deploy --env dev
```

This will:
1. Build Python wheel packages
2. Generate Terraform infrastructure
3. Deploy AWS resources (S3, Glue, DynamoDB, IAM)
4. Upload code to S3
5. Create/update Glue jobs

### 6. Run Pipelines

Execute pipelines on AWS Glue:

```bash
alur run clean_orders
alur logs clean_orders  # View CloudWatch logs
```

## Example Pipeline

```python
from alur.decorators import pipeline
from alur.quality import expect, not_empty
from contracts.bronze import OrdersBronze
from contracts.silver import OrdersSilver

@expect(name="has_data", check_fn=not_empty)
@pipeline(
    sources={"orders": OrdersBronze},
    target=OrdersSilver
)
def clean_orders(orders):
    return orders.filter(orders.status == "valid")
```

## Documentation

For more information, visit: https://github.com/ParmenidesSartre/Alur
