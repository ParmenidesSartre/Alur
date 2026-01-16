# Alur Phase 1 - Improvements Summary

## New CLI Commands

### 1. `alur run <pipeline>`
Run a specific pipeline on AWS Glue.

```bash
# Run a pipeline and wait for completion
alur run clean_orders

# Run in production environment
alur run calculate_daily_sales --env prod

# Start job without waiting
alur run process_data --no-wait
```

**Features:**
- Starts AWS Glue job
- Waits for completion by default
- Shows job run ID
- Displays final status
- Suggests log viewing on failure

### 2. `alur logs <job-run-id>`
Fetch and display Glue job logs.

```bash
# View logs for specific job run
alur logs jr_abc123...

# Tail recent logs (last hour)
alur logs

# Follow logs in real-time
alur logs --tail
```

**Features:**
- Fetches CloudWatch logs
- Can tail recent activity
- Real-time log streaming option

### 3. `alur validate`
Validate contracts and pipelines before deployment.

```bash
alur validate
```

**Checks:**
- Contract imports and field definitions
- Pipeline registration and dependencies
- DAG validation (no circular dependencies)
- Configuration completeness
- Terraform generation

**Output Example:**
```
[1/5] Validating contracts...
  ✓ OrdersBronze: 8 fields
  ✓ OrdersSilver: 7 fields
  ✓ DailySalesMetrics: 5 fields

[2/5] Validating pipelines...
  ✓ clean_orders
      Sources: ['orders']
      Target: orderssilver

[3/5] Validating pipeline DAG...
  ✓ No circular dependencies detected

[4/5] Validating configuration...
  ✓ AWS_REGION: ap-southeast-5
  ✓ BRONZE_BUCKET: alur-bronze-dev

[5/5] Testing Terraform generation...
  ✓ Terraform generation successful

[OK] Validation passed!
```

### 4. `alur list`
List all registered pipelines and tables.

```bash
# Basic list
alur list

# Detailed view
alur list --verbose
```

**Output Example:**
```
📋 CONTRACTS
Bronze Layer (1 tables):
  • OrdersBronze (ordersbronze) - 8 fields

Silver Layer (1 tables):
  • OrdersSilver (orderssilver) - 7 fields

Gold Layer (1 tables):
  • DailySalesMetrics (dailysalesmetrics) - 5 fields

⚙️  PIPELINES (2 total)
  • clean_orders: [orders] → orderssilver
  • calculate_daily_sales: [orders] → dailysalesmetrics

📊 EXECUTION ORDER
  1. clean_orders
  2. calculate_daily_sales
```

### 5. `alur destroy` (Already Existed - Enhanced)
Clean up all infrastructure.

```bash
# Interactive destroy
alur destroy --env dev

# Force empty buckets first
alur destroy --env dev --force

# Auto-approve (no confirmation)
alur destroy --env dev --force --auto-approve
```

---

## EventBridge Scheduling

### New `@schedule` Decorator

Users write Python code to define schedules - framework generates EventBridge infrastructure automatically.

### Basic Usage

```python
from alur.decorators import pipeline
from alur.scheduling import schedule

@schedule(
    cron="cron(0 2 * * ? *)",  # Daily at 2am UTC
    description="Calculate daily sales metrics"
)
@pipeline(
    sources={"orders": OrdersSilver},
    target=DailySalesMetrics
)
def daily_sales_rollup(orders):
    """Runs automatically every day at 2am."""
    return orders.groupBy("date").agg(...)
```

### Common Cron Patterns

```python
# Every 15 minutes
@schedule(cron="cron(0/15 * * * ? *)")

# Every hour
@schedule(cron="cron(0 * * * ? *)")

# Daily at noon
@schedule(cron="cron(0 12 * * ? *)")

# Every Monday at 9am
@schedule(cron="cron(0 9 ? * MON *)")

# First day of month
@schedule(cron="cron(0 0 1 * ? *)")
```

### Rate Expressions

```python
# Every 5 minutes
@schedule(cron="rate(5 minutes)")

# Every hour
@schedule(cron="rate(1 hour)")

# Every day
@schedule(cron="rate(1 day)")
```

### Disabled Schedules

```python
@schedule(
    cron="cron(0 0 * * ? *)",
    enabled=False  # Won't trigger automatically
)
@pipeline(...)
def monthly_report(data):
    """Can still run manually: alur run monthly_report"""
    return data
```

### Generated Infrastructure

When you run `alur deploy`, EventBridge resources are auto-generated:

**eventbridge.tf:**
```hcl
# IAM Role for EventBridge to invoke Glue
resource "aws_iam_role" "eventbridge_glue_role" {
  name = "alur-eventbridge-glue-role-dev"
  ...
}

# EventBridge Rule
resource "aws_cloudwatch_event_rule" "daily_sales_rollup_schedule" {
  name                = "alur-schedule-daily_sales_rollup-dev"
  description         = "Calculate daily sales metrics"
  schedule_expression = "cron(0 2 * * ? *)"
  is_enabled          = true
}

# Target - Glue Job
resource "aws_cloudwatch_event_target" "daily_sales_rollup_target" {
  rule      = aws_cloudwatch_event_rule.daily_sales_rollup_schedule.name
  arn       = "arn:aws:glue:region:account:job/alur-daily_sales_rollup-dev"
  role_arn  = aws_iam_role.eventbridge_glue_role.arn
  ...
}
```

---

## Complete Workflow Example

### 1. Define Scheduled Pipeline

```python
# pipelines/scheduled_metrics.py

from alur.decorators import pipeline
from alur.scheduling import schedule
from contracts.silver import OrdersSilver
from contracts.gold import DailySalesMetrics
from pyspark.sql import functions as F

@schedule(
    cron="cron(0 2 * * ? *)",
    description="Daily sales rollup"
)
@pipeline(
    sources={"orders": OrdersSilver},
    target=DailySalesMetrics,
    resource_profile="medium"
)
def daily_sales_rollup(orders):
    """Runs automatically every day at 2am UTC."""

    daily = orders.withColumn("report_date", F.to_date("created_at"))

    return daily.groupBy("report_date").agg(
        F.count("order_id").alias("total_orders"),
        F.sum("amount").alias("total_revenue"),
        F.countDistinct("customer_id").alias("unique_customers")
    )
```

### 2. Validate Before Deployment

```bash
$ alur validate

[1/5] Validating contracts...
  ✓ OrdersSilver: 7 fields
  ✓ DailySalesMetrics: 5 fields

[2/5] Validating pipelines...
  ✓ daily_sales_rollup
      Sources: ['orders']
      Target: dailysalesmetrics

[3/5] Validating pipeline DAG...
  ✓ No circular dependencies detected

[4/5] Validating configuration...
  ✓ All settings configured

[5/5] Testing Terraform generation...
  ✓ Terraform generation successful

[OK] Validation passed!
```

### 3. View All Pipelines

```bash
$ alur list

⚙️  PIPELINES (1 total)
  • daily_sales_rollup: [orders] → dailysalesmetrics
    Schedule: cron(0 2 * * ? *) - Daily sales rollup
```

### 4. Deploy

```bash
$ alur deploy --env dev

[1/6] Loading configuration...
[2/6] Building Python wheel...
[3/6] Generating Terraform files...
  Generated: provider.tf
  Generated: s3.tf
  Generated: iam.tf
  Generated: glue_database.tf
  Generated: glue_jobs.tf
  Generated: eventbridge.tf  ← NEW!
[4/6] Applying Terraform...
[5/6] Uploading to S3...
[6/6] Deployment complete!
```

### 5. Run Manually (Optional)

```bash
$ alur run daily_sales_rollup

Starting Glue job: alur-daily_sales_rollup-dev
  ✓ Job started successfully
  Job Run ID: jr_abc123...

Waiting for job to complete...
  Status: RUNNING...
  Status: RUNNING...

[OK] Pipeline 'daily_sales_rollup' completed successfully!
```

### 6. View Logs

```bash
$ alur logs jr_abc123...

2026-01-16 02:00:15 [Alur Driver] Starting job
2026-01-16 02:00:16 [Alur Driver] Pipeline: daily_sales_rollup
2026-01-16 02:00:18 [Alur] Reading source: orders
2026-01-16 02:00:25 [Alur] Executing transformation
2026-01-16 02:00:40 [Alur] Writing to target: dailysalesmetrics
2026-01-16 02:00:45 [Alur] Pipeline completed successfully
```

### 7. Destroy When Done

```bash
$ alur destroy --env dev --force --auto-approve

[1/2] Emptying S3 buckets...
  ✓ Emptied alur-bronze-dev
  ✓ Emptied alur-silver-dev
  ✓ Emptied alur-gold-dev
  ✓ Emptied alur-artifacts-dev

[2/2] Destroying Terraform infrastructure...
  Destroy complete! Resources: 20 destroyed.

[OK] Infrastructure destroyed successfully!
```

---

## Complete CLI Reference

```bash
# Project management
alur init <project_name>              # Create new project
alur validate                         # Validate before deploy
alur list                             # List pipelines & tables
alur list --verbose                   # Detailed view

# Deployment
alur deploy --env dev                 # Deploy infrastructure
alur deploy --env prod --auto-approve # Deploy to prod
alur destroy --env dev --force        # Clean up everything

# Job execution
alur run <pipeline>                   # Run a pipeline
alur run <pipeline> --env prod        # Run in prod
alur run <pipeline> --no-wait         # Start without waiting
alur logs <job-run-id>                # View specific logs
alur logs --tail                      # Follow recent logs

# Infrastructure
alur infra generate                   # Generate Terraform
alur status --env dev                 # Check deployment status
```

---

## What Changed

### New Files
- `src/alur/scheduling/__init__.py` - Schedule decorator and registry
- `pipelines/scheduled_example.py` - Example scheduled pipelines

### Enhanced Files
- `src/alur/cli.py` - Added 4 new commands (run, logs, validate, list)
- `src/alur/infra/generator.py` - Added EventBridge generation
- `src/alur/__init__.py` - Exported scheduling module

### Features Added
1. ✅ CLI: run, logs, validate, list commands
2. ✅ EventBridge scheduling with @schedule decorator
3. ✅ Automatic EventBridge infrastructure generation
4. ✅ Validation before deployment
5. ✅ Pipeline listing and execution order display

---

## Benefits

### For Users
- **Write Python code** - Define schedules in code, not YAML
- **Automatic infrastructure** - EventBridge rules generated automatically
- **Better DX** - Run, validate, and monitor from CLI
- **Type-safe** - Schedule decorator validates at import time
- **AWS-native** - EventBridge > cron for cloud workloads

### For DevOps
- **Infrastructure as Code** - Schedules in version control
- **Easy debugging** - `alur logs` for quick troubleshooting
- **Pre-deployment validation** - Catch errors before deploy
- **Visibility** - `alur list` shows all pipelines and schedules

---

## Next Steps (Phase 1.2)

1. **Local development** - LocalAdapter for testing without AWS
2. **Incremental processing** - Append/merge modes
3. **Data quality checks** - Built-in validation
4. **Better error messages** - More helpful feedback
5. **Environment configs** - Multi-env management

---

## AWS EventBridge Format Reference

**Cron Format:** `cron(minute hour day month day-of-week year)`

- `*` = all values
- `?` = no specific value
- `/` = increments
- `-` = ranges
- `,` = multiple values

**Examples:**
- `cron(0 2 * * ? *)` - Daily at 2am
- `cron(0/15 * * * ? *)` - Every 15 minutes
- `cron(0 9 ? * MON-FRI *)` - Weekdays at 9am
- `cron(0 0 1 * ? *)` - First of every month

**Rate Format:** `rate(value unit)`
- `rate(5 minutes)` - Every 5 minutes
- `rate(1 hour)` - Every hour
- `rate(7 days)` - Every week
