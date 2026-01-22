"""
Configuration settings for your Alur project.
Edit these values to match your environment.

Environment variables can override these settings:
- ALUR_AWS_REGION
- ALUR_BRONZE_BUCKET, ALUR_ARTIFACTS_BUCKET, ALUR_LANDING_BUCKET
- ALUR_ENV (dev/staging/production)
"""

import os

# AWS Configuration
AWS_REGION = os.getenv("ALUR_AWS_REGION", "ap-southeast-5")  # Singapore
AWS_ACCOUNT_ID = os.getenv("ALUR_AWS_ACCOUNT_ID", "123456789012")  # Replace with your AWS account ID

# S3 Bucket Names (can be overridden via environment variables)
BRONZE_BUCKET = os.getenv("ALUR_BRONZE_BUCKET", "alur-bronze-dev")
ARTIFACTS_BUCKET = os.getenv("ALUR_ARTIFACTS_BUCKET", "alur-artifacts-dev")
LANDING_BUCKET = os.getenv("ALUR_LANDING_BUCKET", "alur-landing-dev")  # Source data bucket

# Glue Database
GLUE_DATABASE = os.getenv("ALUR_GLUE_DATABASE", "alur_datalake_dev")

# DynamoDB State Table
STATE_TABLE = os.getenv("ALUR_STATE_TABLE", "alur-state-dev")

# Environment
ENVIRONMENT = os.getenv("ALUR_ENV", "dev")  # dev, staging, production

# Spark Configuration (for local development)
SPARK_CONFIG = {
    "spark.driver.memory": "2g",
    "spark.executor.memory": "2g",
    "spark.sql.shuffle.partitions": "4",
}
