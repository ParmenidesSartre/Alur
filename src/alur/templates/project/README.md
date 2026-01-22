# Alur Data Lake Project

This project was generated using the Alur Framework.

## Project Structure

```
.
|-- config/          # AWS configuration
|-- contracts/       # Table definitions (Bronze)
`-- pipelines/       # Data pipelines (Bronze ingestion)
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

Edit files in `contracts/` to define your Bronze (raw) tables:
- `bronze.py` - Raw data tables

### 4. Create Pipelines

Add ingestion logic in `pipelines/` using the `@pipeline` decorator.

### 5. Deploy to AWS

```bash
alur deploy --env dev
```

### 6. Run Pipelines

```bash
alur run ingest_orders
alur logs ingest_orders  # View CloudWatch logs
```

## Documentation

For more information, visit: https://github.com/ParmenidesSartre/Alur
