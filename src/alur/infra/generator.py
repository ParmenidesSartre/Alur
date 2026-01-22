"""
Automatic infrastructure generation for Alur projects.

This module scans your contracts and pipelines, then generates all necessary
Terraform configuration automatically.
"""

import os
import importlib.util
from pathlib import Path
from typing import Dict, List, Any
from alur.decorators import PipelineRegistry


class InfrastructureGenerator:
    """Generates complete Terraform infrastructure from Alur project."""

    def __init__(self, project_root: Path):
        self.project_root = Path(project_root)
        self.contracts_dir = self.project_root / "contracts"
        self.pipelines_dir = self.project_root / "pipelines"
        self.config = None

    def load_config(self):
        """Load project configuration."""
        try:
            spec = importlib.util.spec_from_file_location(
                "config",
                self.project_root / "config" / "settings.py"
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            self.config = module
            return module
        except Exception as e:
            raise RuntimeError(f"Failed to load config: {e}")

    def scan_contracts(self) -> Dict[str, Any]:
        """Scan contracts directory and extract table definitions."""
        from alur.core.contracts import BaseTable, BronzeTable

        contracts = {}

        if not self.contracts_dir.exists():
            return contracts

        # Import all contract modules
        for py_file in self.contracts_dir.glob("*.py"):
            if py_file.name.startswith("_"):
                continue

            module_name = f"contracts.{py_file.stem}"
            spec = importlib.util.spec_from_file_location(module_name, py_file)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # Find all BaseTable subclasses (exclude base layer classes)
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (isinstance(attr, type) and
                    issubclass(attr, BaseTable) and
                    attr is not BaseTable and
                    attr is not BronzeTable):  # Don't create tables for base layer classes

                    table_info = {
                        "name": attr.__name__,
                        "table_name": attr.get_table_name(),
                        "layer": self._get_layer(attr),
                        "location": self._get_s3_location(attr),
                        "fields": attr._fields if hasattr(attr, "_fields") else {},
                        "partition_by": getattr(attr.Meta, "partition_by", []) if hasattr(attr, "Meta") else [],
                        "format": getattr(attr, "_format", "parquet"),
                    }
                    contracts[attr.__name__] = table_info

        return contracts

    def _get_layer(self, table_class) -> str:
        """Determine which layer (bronze) a table belongs to."""
        from alur.core.contracts import BronzeTable

        if issubclass(table_class, BronzeTable):
            return "bronze"
        return "unknown"

    def _get_s3_location(self, table_class) -> str:
        """Get S3 location for a table based on its metadata."""
        table_name = table_class.get_table_name()
        layer = self._get_layer(table_class)

        bucket_map = {
            "bronze": "BRONZE_BUCKET",
        }

        bucket_var = bucket_map.get(layer, "BRONZE_BUCKET")
        return f"s3://${{{bucket_var}}}/{table_name}/"

    def generate_provider_tf(self) -> str:
        """Generate provider.tf with AWS provider configuration."""
        region = getattr(self.config, "AWS_REGION", "ap-southeast-5")

        return f'''terraform {{
  required_providers {{
    aws = {{
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }}
  }}
}}

provider "aws" {{
  region = "{region}"
}}
'''

    def generate_s3_tf(self) -> str:
        """Generate S3 buckets terraform."""
        env = getattr(self.config, "ENVIRONMENT", "dev")
        region = getattr(self.config, "AWS_REGION", "ap-southeast-5")

        bronze = getattr(self.config, "BRONZE_BUCKET", f"alur-bronze-{env}")
        artifacts = getattr(self.config, "ARTIFACTS_BUCKET", f"alur-artifacts-{env}")
        landing = getattr(self.config, "LANDING_BUCKET", f"alur-landing-{env}")

        return f'''# S3 Buckets for Alur Data Lake
# Auto-generated - do not edit manually

resource "aws_s3_bucket" "bronze" {{
  bucket = "{bronze}"
  tags = {{
    Environment = "{env}"
    Layer       = "bronze"
    ManagedBy   = "alur"
  }}
}}

resource "aws_s3_bucket" "artifacts" {{
  bucket = "{artifacts}"
  tags = {{
    Environment = "{env}"
    ManagedBy   = "alur"
  }}
}}

resource "aws_s3_bucket" "landing" {{
  bucket = "{landing}"
  tags = {{
    Environment = "{env}"
    Layer       = "landing"
    ManagedBy   = "alur"
  }}
}}
'''

    def generate_iam_tf(self) -> str:
        """Generate IAM roles and policies for Glue."""
        env = getattr(self.config, "ENVIRONMENT", "dev")

        return f'''# IAM Role for AWS Glue
# Auto-generated - do not edit manually

resource "aws_iam_role" "glue_role" {{
  name = "alur-glue-role-{env}"

  assume_role_policy = jsonencode({{
    Version = "2012-10-17"
    Statement = [
      {{
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {{
          Service = "glue.amazonaws.com"
        }}
      }}
    ]
  }})

  tags = {{
    Environment = "{env}"
    ManagedBy   = "alur"
  }}
}}

# Attach AWS managed policy for Glue
resource "aws_iam_role_policy_attachment" "glue_service" {{
  role       = aws_iam_role.glue_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSGlueServiceRole"
}}

# Custom policy for S3 and CloudWatch access
resource "aws_iam_role_policy" "glue_s3_policy" {{
  name = "alur-glue-s3-policy-{env}"
  role = aws_iam_role.glue_role.id

  policy = jsonencode({{
    Version = "2012-10-17"
    Statement = [
      {{
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket"
        ]
        Resource = [
          "${{aws_s3_bucket.bronze.arn}}/*",
          "${{aws_s3_bucket.bronze.arn}}",
          "${{aws_s3_bucket.artifacts.arn}}/*",
          "${{aws_s3_bucket.artifacts.arn}}",
          "${{aws_s3_bucket.landing.arn}}/*",
          "${{aws_s3_bucket.landing.arn}}"
        ]
      }},
      {{
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      }},
      {{
        Effect = "Allow"
        Action = [
          "glue:GetDatabase",
          "glue:GetTable",
          "glue:GetTables",
          "glue:GetPartition",
          "glue:GetPartitions",
          "glue:CreateTable",
          "glue:UpdateTable",
          "glue:DeleteTable",
          "glue:BatchCreatePartition",
          "glue:BatchDeletePartition"
        ]
        Resource = "*"
      }},
      {{
        Effect = "Allow"
        Action = [
          "dynamodb:PutItem",
          "dynamodb:GetItem",
          "dynamodb:UpdateItem",
          "dynamodb:Query",
          "dynamodb:Scan",
          "dynamodb:DescribeTable"
        ]
        Resource = "arn:aws:dynamodb:*:*:table/alur-ingestion-state"
      }},
      {{
        Effect = "Allow"
        Action = [
          "lakeformation:GetDataAccess",
          "lakeformation:GrantPermissions",
          "lakeformation:RevokePermissions",
          "lakeformation:BatchGrantPermissions",
          "lakeformation:BatchRevokePermissions",
          "lakeformation:ListPermissions",
          "lakeformation:RegisterResource",
          "lakeformation:DeregisterResource"
        ]
        Resource = "*"
      }}
    ]
  }})
}}
'''

    def generate_dynamodb_tf(self) -> str:
        """Generate DynamoDB table for ingestion state tracking."""
        env = getattr(self.config, "ENVIRONMENT", "dev")

        return f'''# DynamoDB Table for Ingestion State Tracking
# Auto-generated - do not edit manually
# Used for idempotency to prevent duplicate ingestion

resource "aws_dynamodb_table" "ingestion_state" {{
  name           = "alur-ingestion-state"
  billing_mode   = "PAY_PER_REQUEST"  # On-demand pricing for SMEs
  hash_key       = "ingestion_key"
  range_key      = "file_path"

  attribute {{
    name = "ingestion_key"
    type = "S"
  }}

  attribute {{
    name = "file_path"
    type = "S"
  }}

  tags = {{
    Environment = "{env}"
    ManagedBy   = "alur"
    Purpose     = "ingestion-state-tracking"
  }}
}}
'''

    def generate_glue_database_tf(self, contracts: Dict[str, Any]) -> str:
        """
        Generate Glue databases and tables terraform.

        Creates:
        - bronze_layer database (contains all bronze tables)

        Each source gets one table in the bronze_layer database.
        """
        env = getattr(self.config, "ENVIRONMENT", "dev")

        tf_content = f'''# Glue Catalog Database - Bronze Layer
# Auto-generated from contracts - do not edit manually

# Bronze Database - Raw data layer with metadata
resource "aws_glue_catalog_database" "bronze" {{
  name = "bronze_layer"

  description = "Bronze layer - raw data as-is with ingestion metadata"

  tags = {{
    Environment = "{env}"
    Layer       = "bronze"
    ManagedBy   = "alur"
  }}
}}

'''

        # Generate table resources for each contract
        for contract_name, contract_info in contracts.items():
            table_name = contract_info["table_name"]
            layer = contract_info["layer"]
            format_type = "parquet"  # Use Parquet for all tables

            # Map layer to database and bucket
            layer_resources = {
                "bronze": {
                    "database": "aws_glue_catalog_database.bronze.name",
                    "bucket": "aws_s3_bucket.bronze.bucket"
                },
            }

            resources = layer_resources.get(layer, layer_resources["bronze"])
            database_ref = resources["database"]
            bucket_var = resources["bucket"]

            # Generate column definitions as individual blocks
            # Exclude partition columns from regular columns
            columns_blocks = []
            partition_cols = set(contract_info["partition_by"])
            for field_name, field in contract_info["fields"].items():
                # Skip if this field is a partition column
                if field_name in partition_cols:
                    continue
                field_type = self._map_field_type(field.__class__.__name__)
                columns_blocks.append(f'''
    columns {{
      name = "{field_name}"
      type = "{field_type}"
    }}''')

            columns_str = "".join(columns_blocks)

            # Partition keys as individual blocks
            partition_blocks = []
            for part_col in contract_info["partition_by"]:
                if part_col in contract_info["fields"]:
                    field = contract_info["fields"][part_col]
                    field_type = self._map_field_type(field.__class__.__name__)
                    partition_blocks.append(f'''
  partition_keys {{
    name = "{part_col}"
    type = "{field_type}"
  }}''')

            partition_str = "".join(partition_blocks)

            # Use unique resource name combining table and layer
            resource_name = f"{table_name}_{layer}"

            # Hive/Parquet tables
            tf_content += f'''
resource "aws_glue_catalog_table" "{resource_name}" {{
  name          = "{table_name}"
  database_name = {database_ref}

  table_type = "EXTERNAL_TABLE"
{partition_str}

  storage_descriptor {{
    location = "s3://${{{bucket_var}}}/{table_name}/"
    input_format  = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat"
    output_format = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat"

    ser_de_info {{
      serialization_library = "org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe"
    }}
{columns_str}
  }}

  parameters = {{
    "layer" = "{layer}"
  }}
}}
'''

        return tf_content

    def _map_field_type(self, alur_type: str) -> str:
        """Map Alur field types to Hive/Glue types."""
        type_map = {
            "StringField": "string",
            "IntegerField": "int",
            "FloatField": "float",
            "DoubleField": "double",
            "BooleanField": "boolean",
            "TimestampField": "timestamp",
            "DateField": "date",
            "DecimalField": "decimal(10,2)",
            "ArrayField": "array<string>",
            "MapField": "map<string,string>",
            "StructField": "struct<>",
        }
        return type_map.get(alur_type, "string")

    def generate_glue_jobs_tf(self) -> str:
        """Generate Glue jobs for all registered pipelines."""
        env = getattr(self.config, "ENVIRONMENT", "dev")

        # Get project wheel name from dist/ directory
        project_dist = self.project_root / "dist"
        project_wheel_name = None
        if project_dist.exists():
            project_wheels = list(project_dist.glob("*.whl"))
            if project_wheels:
                project_wheel_name = project_wheels[-1].name

        # Get framework wheel name from Alur dist/ directory
        import alur
        alur_root = Path(alur.__path__[0]).parent.parent
        alur_dist = alur_root / "dist"
        framework_wheel_name = None
        if alur_dist.exists():
            framework_wheels = list(alur_dist.glob("*.whl"))
            if framework_wheels:
                framework_wheel_name = framework_wheels[-1].name

        # Fallback to pattern if wheels not found
        if not framework_wheel_name:
            # Use exact version from __version__
            from alur import __version__
            framework_wheel_name = f"alur_framework-{__version__}-py3-none-any.whl"
        if not project_wheel_name:
            project_name = self.project_root.name
            project_wheel_name = f"{project_name}-*.whl"

        # Construct extra-py-files path
        extra_py_files = f"s3://${{aws_s3_bucket.artifacts.bucket}}/wheels/{framework_wheel_name},s3://${{aws_s3_bucket.artifacts.bucket}}/wheels/{project_wheel_name}"

        tf_content = '''# AWS Glue Jobs for Pipelines
# Auto-generated from pipelines - do not edit manually

'''

        # Get all registered pipelines
        pipelines = PipelineRegistry.get_all()

        for pipeline_name, pipeline in pipelines.items():
            job_name = f"alur-{pipeline_name}-{env}"

            tf_content += f'''
resource "aws_glue_job" "{pipeline_name}_job" {{
  name     = "{job_name}"
  role_arn = aws_iam_role.glue_role.arn

  command {{
    name            = "glueetl"
    script_location = "s3://${{aws_s3_bucket.artifacts.bucket}}/scripts/driver.py"
    python_version  = "3"
  }}

  default_arguments = {{
    "--job-language"                     = "python"
    "--pipeline_name"                    = "{pipeline_name}"
    "--extra-py-files"                   = "{extra_py_files}"
    "--enable-metrics"                   = "true"
    "--enable-continuous-cloudwatch-log" = "true"
    "--enable-spark-ui"                  = "true"
    "--spark-event-logs-path"            = "s3://${{aws_s3_bucket.artifacts.bucket}}/spark-logs/"
    "--TempDir"                          = "s3://${{aws_s3_bucket.artifacts.bucket}}/temp/"
  }}

  glue_version = "4.0"
  max_capacity = 2.0
  timeout      = 30

  tags = {{
    Environment = "{env}"
    Pipeline    = "{pipeline_name}"
    ManagedBy   = "alur"
  }}
}}
'''

        return tf_content

    def generate_eventbridge_tf(self) -> str:
        """Generate EventBridge rules for scheduled pipelines."""
        return "# Scheduling disabled (batch-only mode)\n"

    def generate_all(self, output_dir: Path):
        """Generate all Terraform files."""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Clear registries from previous runs
        from alur.decorators import PipelineRegistry
        PipelineRegistry.clear()

        # Load configuration
        self.load_config()

        # Scan contracts
        contracts = self.scan_contracts()

        # Import pipelines to register them
        for py_file in self.pipelines_dir.glob("*.py"):
            if py_file.name.startswith("_"):
                continue

            module_name = f"pipelines.{py_file.stem}"
            spec = importlib.util.spec_from_file_location(module_name, py_file)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

        # Generate each file
        files = {
            "provider.tf": self.generate_provider_tf(),
            "s3.tf": self.generate_s3_tf(),
            "iam.tf": self.generate_iam_tf(),
            "dynamodb.tf": self.generate_dynamodb_tf(),
            "glue_database.tf": self.generate_glue_database_tf(contracts),
            "glue_jobs.tf": self.generate_glue_jobs_tf(),
            "eventbridge.tf": self.generate_eventbridge_tf(),
        }

        for filename, content in files.items():
            filepath = output_dir / filename
            filepath.write_text(content)
            print(f"  Generated: {filename}")

        return output_dir
