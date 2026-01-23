# Pipeline Scheduling

Alur supports automatic pipeline scheduling via AWS Glue SCHEDULED triggers. Use the `@schedule` decorator to configure cron-based execution for your pipelines.

## Table of Contents

- [Quick Start](#quick-start)
- [Decorator API](#decorator-api)
- [Cron Format Reference](#cron-format-reference)
- [Common Patterns](#common-patterns)
- [Deployment](#deployment)
- [Managing Schedules](#managing-schedules)
- [Best Practices](#best-practices)
- [Limitations](#limitations)

## Quick Start

Add scheduling to any pipeline using the `@schedule` decorator:

```python
from alur import schedule, pipeline
from contracts.bronze import OrdersBronze

@schedule(
    cron="0 2 * * ? *",  # Daily at 2 AM UTC
    description="Daily order ingestion"
)
@pipeline(sources={}, target=OrdersBronze)
def ingest_orders():
    """Ingest orders from S3 daily."""
    return load_to_bronze(...)
```

**Important:** The `@schedule` decorator must be placed **before** the `@pipeline` decorator.

## Decorator API

### `@schedule(cron, enabled=True, timezone="UTC", description=None, max_concurrent_runs=1)`

Configure automatic pipeline execution.

**Parameters:**

- `cron` (str, required): AWS Glue cron expression (6 fields)
- `enabled` (bool, default=True): Whether schedule is active
- `timezone` (str, default="UTC"): Timezone for documentation (Glue triggers use UTC)
- `description` (str, optional): Human-readable description
- `max_concurrent_runs` (int, default=1): Maximum concurrent executions

**Example:**

```python
@schedule(
    cron="0 */4 * * ? *",
    enabled=True,
    description="Ingest orders every 4 hours",
    max_concurrent_runs=1
)
@pipeline(sources={}, target=OrdersBronze)
def ingest_orders():
    pass
```

## Cron Format Reference

AWS Glue SCHEDULED triggers use **6-field cron format**, different from Unix cron (5 fields).

### Format

```
cron(minute hour day-of-month month day-of-week year)
```

### Field Values

| Field         | Values          | Wildcards |
|---------------|-----------------|-----------|
| minute        | 0-59            | , - * /   |
| hour          | 0-23            | , - * /   |
| day-of-month  | 1-31            | , - * ? / |
| month         | 1-12 or JAN-DEC | , - * /   |
| day-of-week   | 1-7 or SUN-SAT  | , - * ? / |
| year          | 1970-2199       | , - * /   |

### Important Rules

1. **Use `?` (question mark)** in either `day-of-month` OR `day-of-week` (not both)
   - `?` means "no specific value"
   - Required to avoid ambiguity

2. **Wildcards:**
   - `*` - All values
   - `?` - No specific value (day fields only)
   - `-` - Range (e.g., `10-12`)
   - `,` - List (e.g., `MON,WED,FRI`)
   - `/` - Increments (e.g., `*/5` = every 5)

## Common Patterns

### Daily Schedules

```python
# Daily at 2 AM UTC
cron="0 2 * * ? *"

# Daily at midnight UTC
cron="0 0 * * ? *"

# Daily at 6 PM UTC
cron="0 18 * * ? *"
```

### Hourly Schedules

```python
# Every hour
cron="0 * * * ? *"

# Every 4 hours
cron="0 */4 * * ? *"

# Every 30 minutes
cron="*/30 * * * ? *"
```

### Weekly Schedules

```python
# Monday at 9 AM UTC
cron="0 9 ? * MON *"

# Every weekday at 8 AM UTC
cron="0 8 ? * MON-FRI *"

# Sunday at midnight UTC
cron="0 0 ? * SUN *"
```

### Monthly Schedules

```python
# First day of month at midnight UTC
cron="0 0 1 * ? *"

# Last day of month (not directly supported, use Lambda)
# Workaround: Schedule daily and check date in pipeline

# 15th of every month at 3 AM UTC
cron="0 3 15 * ? *"
```

### Custom Schedules

```python
# Twice daily (6 AM and 6 PM UTC)
cron="0 6,18 * * ? *"

# Every 15 minutes during business hours (9 AM - 5 PM UTC)
cron="*/15 9-17 * * ? *"

# First Monday of every month at 10 AM UTC
cron="0 10 ? * MON#1 *"
```

## Deployment

Schedules are automatically deployed as AWS Glue SCHEDULED triggers during deployment.

### Deploy with Schedules

```bash
# Deploy infrastructure with schedules
alur deploy --env production

# Verify Glue SCHEDULED triggers created
aws glue list-triggers --max-results 20
```

### Generated Infrastructure

The `@schedule` decorator automatically generates:

1. **Glue SCHEDULED Trigger** - Cron-based trigger that invokes the Glue job

All Terraform code is auto-generated in `terraform/schedules.tf`.

## Managing Schedules

### List Schedules

```bash
# List all schedules
alur schedules

# List only enabled schedules
alur schedules --enabled-only
```

**Example output:**

```
================================================================================
SCHEDULED PIPELINES
================================================================================

Pipeline                       Schedule                  Status     Description
--------------------------------------------------------------------------------
ingest_orders                  0 2 * * ? *               ✓ Enabled  Daily order ingestion
ingest_customers               0 3 * * ? *               ✓ Enabled  Daily customer sync
process_analytics              0 */4 * * ? *             ✓ Enabled  Hourly analytics update

Total: 3 schedule(s) | Enabled: 3 | Disabled: 0
```

### Disable a Schedule

To temporarily disable a schedule without removing the decorator:

```python
@schedule(
    cron="0 2 * * ? *",
    enabled=False,  # Disable schedule
    description="Daily ingestion (currently disabled)"
)
@pipeline(sources={}, target=OrdersBronze)
def ingest_orders():
    pass
```

Redeploy to remove the Glue SCHEDULED trigger:

```bash
alur deploy --env production
```

### Remove a Schedule

Simply remove the `@schedule` decorator and redeploy:

```python
# Before
@schedule(cron="0 2 * * ? *")
@pipeline(sources={}, target=OrdersBronze)
def ingest_orders():
    pass

# After
@pipeline(sources={}, target=OrdersBronze)
def ingest_orders():
    pass
```

```bash
alur deploy --env production
```

## Best Practices

### 1. Use Descriptive Descriptions

```python
# Good
@schedule(
    cron="0 2 * * ? *",
    description="Daily ingestion of orders from production database"
)

# Bad
@schedule(cron="0 2 * * ? *")  # No description
```

### 2. Prevent Concurrent Runs

For pipelines that shouldn't overlap:

```python
@schedule(
    cron="0 */4 * * ? *",
    max_concurrent_runs=1  # Prevent overlapping executions
)
@pipeline(sources={}, target=OrdersBronze)
def long_running_pipeline():
    pass
```

### 3. Use UTC for Consistency

Glue always uses UTC internally. Avoid timezone confusion by thinking in UTC:

```python
# Good - Explicit UTC time
@schedule(
    cron="0 14 * * ? *",  # 2 PM UTC
    description="Daily ingestion at 2 PM UTC (9 AM EST)"
)

# Confusing - Timezone parameter is for documentation only
@schedule(
    cron="0 14 * * ? *",
    timezone="America/New_York",  # Misleading - Glue still uses UTC!
    description="Daily ingestion at 9 AM EST"
)
```

### 4. Test Schedules Manually First

Before scheduling, test the pipeline manually:

```bash
# Test pipeline on Glue
alur run ingest_orders --env dev

# Check logs
alur logs --tail --env dev

# If successful, deploy schedule
alur deploy --env production
```

### 5. Monitor Scheduled Runs

Check recent executions:

```bash
# View Glue job runs
aws glue get-job-runs --job-name alur-ingest_orders-production --max-results 10

# View Glue SCHEDULED trigger details
aws glue get-trigger --name alur-ingest_orders-schedule-production
```

### 6. Use Idempotency

Ensure your pipelines are idempotent (safe to run multiple times):

```python
@schedule(cron="0 2 * * ? *")
@pipeline(sources={}, target=OrdersBronze)
def ingest_orders():
    """
    Idempotent ingestion - files tracked in DynamoDB.
    Re-running won't create duplicates.
    """
    return load_to_bronze(
        spark,
        source_path="s3://bucket/orders/*.csv",
        target=OrdersBronze,
        enable_idempotency=True  # Prevents duplicate ingestion
    )
```

## Limitations

### 1. One Schedule Per Pipeline

Each pipeline can only have one schedule:

```python
# ✗ NOT ALLOWED
@schedule(cron="0 2 * * ? *")
@schedule(cron="0 14 * * ? *")  # Error: already registered
@pipeline(sources={}, target=OrdersBronze)
def ingest_orders():
    pass

# ✓ WORKAROUND: Create separate pipelines
@schedule(cron="0 2 * * ? *")
@pipeline(sources={}, target=OrdersBronze)
def ingest_orders_morning():
    return _shared_ingestion_logic()

@schedule(cron="0 14 * * ? *")
@pipeline(sources={}, target=OrdersBronze)
def ingest_orders_afternoon():
    return _shared_ingestion_logic()
```

### 2. Glue Uses UTC Only

All schedules run in UTC. Glue does not support timezone-aware scheduling.

### 3. Minimum Frequency: 1 Minute

Glue has a minimum interval of 1 minute. For sub-minute scheduling, use alternative solutions (Lambda, Kinesis, etc.).

### 4. Execution Not Guaranteed

Glue is "at least once" delivery. In rare cases, a schedule may trigger multiple times or not at all. Design pipelines to handle this.

## Troubleshooting

### Schedule Not Triggering

1. **Check Glue SCHEDULED trigger status:**
   ```bash
   aws glue get-trigger --name alur-ingest_orders-schedule-production
   ```

2. **Verify trigger is ACTIVATED:**
   ```json
   {
     "State": "ACTIVATED",  // Should be ACTIVATED
     "Type": "SCHEDULED",
     "Schedule": "cron(0 2 * * ? *)"
   }
   ```

3. **Glue triggers don't require additional IAM permissions** - the Glue job role is used automatically

4. **Verify Glue job exists:**
   ```bash
   aws glue get-job --job-name alur-ingest_orders-production
   ```

### Invalid Cron Expression

**Error:** `ValueError: Glue cron expression must have 6 fields`

**Solution:** Use Glue format (6 fields), not Unix cron (5 fields):

```python
# ✗ Unix cron (5 fields)
@schedule(cron="0 2 * * *")  # ERROR

# ✓ Glue cron (6 fields)
@schedule(cron="0 2 * * ? *")  # CORRECT
```

### Duplicate Schedule Error

**Error:** `ValueError: Schedule for pipeline 'ingest_orders' is already registered`

**Solution:** Remove duplicate `@schedule` decorator. Each pipeline can only have one schedule.

## Cost Considerations

- **Glue Rules:** Free for first 100 rules/month
- **Glue Invocations:** $1.00 per million invocations
- **Glue Job Runs:** Standard Glue pricing (based on DPU-hours)

**Example Cost (Daily Schedule):**
- 1 pipeline × 1 run/day × 30 days = 30 invocations/month
- Glue cost: 30 / 1,000,000 × $1.00 = $0.00003/month (negligible)
- Glue cost: Depends on job runtime (unchanged from manual runs)

**Conclusion:** Scheduling adds virtually zero cost overhead. You only pay for Glue execution time.
