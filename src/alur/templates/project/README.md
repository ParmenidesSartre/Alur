# Alur Data Lake Project

This project was generated using the Alur Framework.

## Project Structure

```
.
├── config/          # Configuration files
├── contracts/       # Table definitions (Bronze, Silver, Gold)
├── pipelines/       # Data transformation pipelines
└── main.py          # Main entry point
```

## Getting Started

### 1. Install Dependencies

```bash
pip install alur-framework
```

### 2. Define Your Tables

Edit files in `contracts/` to define your data lake tables:
- `bronze.py` - Raw data tables
- `silver.py` - Cleaned, deduplicated tables
- `gold.py` - Business-level aggregates (optional)

### 3. Create Pipelines

Add transformation logic in `pipelines/` using the `@pipeline` decorator.

### 4. Run Locally

```bash
python main.py
```

This will execute all pipelines using the LocalAdapter (data stored in `/tmp/alur`).

### 5. Deploy to AWS

Generate Terraform infrastructure:

```bash
alur infra generate
cd terraform
terraform init
terraform apply
```

Deploy your code:

```bash
alur deploy --env production
```

## Example Pipeline

```python
from alur.decorators import pipeline
from contracts.bronze import OrdersBronze
from contracts.silver import OrdersSilver

@pipeline(
    sources={"orders": OrdersBronze},
    target=OrdersSilver
)
def clean_orders(orders):
    return orders.filter(orders.status == "valid")
```

## Documentation

For more information, visit: https://github.com/alur-framework/alur-framework
