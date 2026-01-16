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
        from alur.core.contracts import BaseTable

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

            # Find all BaseTable subclasses
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (isinstance(attr, type) and
                    issubclass(attr, BaseTable) and
                    attr is not BaseTable):

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
        """Determine which layer (bronze/silver/gold) a table belongs to."""
        from alur.core.contracts import BronzeTable, SilverTable, GoldTable

        if issubclass(table_class, BronzeTable):
            return "bronze"
        elif issubclass(table_class, SilverTable):
            return "silver"
        elif issubclass(table_class, GoldTable):
            return "gold"
        return "unknown"

    def _get_s3_location(self, table_class) -> str:
        """Get S3 location for a table based on its metadata."""
        table_name = table_class.get_table_name()
        layer = self._get_layer(table_class)

        bucket_map = {
            "bronze": "BRONZE_BUCKET",
            "silver": "SILVER_BUCKET",
            "gold": "GOLD_BUCKET",
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
        silver = getattr(self.config, "SILVER_BUCKET", f"alur-silver-{env}")
        gold = getattr(self.config, "GOLD_BUCKET", f"alur-gold-{env}")
        artifacts = getattr(self.config, "ARTIFACTS_BUCKET", f"alur-artifacts-{env}")

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

resource "aws_s3_bucket" "silver" {{
  bucket = "{silver}"
  tags = {{
    Environment = "{env}"
    Layer       = "silver"
    ManagedBy   = "alur"
  }}
}}

resource "aws_s3_bucket" "gold" {{
  bucket = "{gold}"
  tags = {{
    Environment = "{env}"
    Layer       = "gold"
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
          "${{aws_s3_bucket.silver.arn}}/*",
          "${{aws_s3_bucket.silver.arn}}",
          "${{aws_s3_bucket.gold.arn}}/*",
          "${{aws_s3_bucket.gold.arn}}",
          "${{aws_s3_bucket.artifacts.arn}}/*",
          "${{aws_s3_bucket.artifacts.arn}}"
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
      }}
    ]
  }})
}}
'''

    def generate_glue_database_tf(self, contracts: Dict[str, Any]) -> str:
        """Generate Glue database and tables terraform."""
        env = getattr(self.config, "ENVIRONMENT", "dev")
        db_name = getattr(self.config, "GLUE_DATABASE", f"alur_datalake_{env}")

        tf_content = f'''# Glue Catalog Database and Tables
# Auto-generated from contracts - do not edit manually

resource "aws_glue_catalog_database" "main" {{
  name = "{db_name}"

  description = "Alur data lake database - auto-generated"

  tags = {{
    Environment = "{env}"
    ManagedBy   = "alur"
  }}
}}

'''

        # Generate table resources for each contract
        for contract_name, contract_info in contracts.items():
            table_name = contract_info["table_name"]
            layer = contract_info["layer"]
            format_type = contract_info.get("format", "parquet")

            # Map layer to bucket variable
            bucket_var = {
                "bronze": "aws_s3_bucket.bronze.bucket",
                "silver": "aws_s3_bucket.silver.bucket",
                "gold": "aws_s3_bucket.gold.bucket",
            }.get(layer, "aws_s3_bucket.bronze.bucket")

            # Determine input/output format and SerDe based on format type
            if format_type == "parquet":
                input_format = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat"
                output_format = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat"
                serde_lib = "org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe"
            elif format_type == "json":
                input_format = "org.apache.hadoop.mapred.TextInputFormat"
                output_format = "org.apache.hadoop.hive.ql.io.HiveIgnoreKeyTextOutputFormat"
                serde_lib = "org.openx.data.jsonserde.JsonSerDe"
            else:
                # Default to parquet
                input_format = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat"
                output_format = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat"
                serde_lib = "org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe"

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

            tf_content += f'''
resource "aws_glue_catalog_table" "{table_name}" {{
  name          = "{table_name}"
  database_name = aws_glue_catalog_database.main.name

  table_type = "EXTERNAL_TABLE"
{partition_str}

  storage_descriptor {{
    location      = "s3://${{{bucket_var}}}/{table_name}/"
    input_format  = "{input_format}"
    output_format = "{output_format}"

    ser_de_info {{
      serialization_library = "{serde_lib}"
    }}
{columns_str}
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
            framework_wheel_name = "alur_framework-*.whl"
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
        try:
            from alur.scheduling import ScheduleRegistry
        except ImportError:
            # Scheduling module not available, skip
            return "# No scheduled pipelines\n"

        env = getattr(self.config, "ENVIRONMENT", "dev")
        region = getattr(self.config, "AWS_REGION", "us-east-1")
        account_id = getattr(self.config, "AWS_ACCOUNT_ID", "")

        schedules = ScheduleRegistry.get_all()

        if not schedules:
            return "# No scheduled pipelines\n"

        tf_content = '''# EventBridge Scheduler for Pipeline Automation
# Auto-generated by Alur Framework

'''

        # Generate IAM role for EventBridge to invoke Glue
        tf_content += f'''
# IAM Role for EventBridge to invoke Glue jobs
resource "aws_iam_role" "eventbridge_glue_role" {{
  name = "alur-eventbridge-glue-role-{env}"

  assume_role_policy = jsonencode({{
    Version = "2012-10-17"
    Statement = [
      {{
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {{
          Service = "events.amazonaws.com"
        }}
      }}
    ]
  }})

  tags = {{
    Environment = "{env}"
    ManagedBy   = "alur"
  }}
}}

# IAM Policy for EventBridge to start Glue jobs
resource "aws_iam_role_policy" "eventbridge_glue_policy" {{
  name = "alur-eventbridge-glue-policy-{env}"
  role = aws_iam_role.eventbridge_glue_role.id

  policy = jsonencode({{
    Version = "2012-10-17"
    Statement = [
      {{
        Effect = "Allow"
        Action = [
          "glue:StartJobRun"
        ]
        Resource = "arn:aws:glue:{region}:{account_id}:job/alur-*-{env}"
      }}
    ]
  }})
}}
'''

        # Generate EventBridge rule for each scheduled pipeline
        for pipeline_name, schedule in schedules.items():
            job_name = f"alur-{pipeline_name}-{env}"
            rule_name = f"alur-schedule-{pipeline_name}-{env}"

            enabled_str = "true" if schedule.enabled else "false"

            tf_content += f'''
# EventBridge Rule for {pipeline_name}
resource "aws_cloudwatch_event_rule" "{pipeline_name}_schedule" {{
  name                = "{rule_name}"
  description         = "{schedule.description}"
  schedule_expression = "{schedule.cron_expression}"
  is_enabled          = {enabled_str}

  tags = {{
    Environment = "{env}"
    Pipeline    = "{pipeline_name}"
    ManagedBy   = "alur"
  }}
}}

# EventBridge Target - Glue Job
resource "aws_cloudwatch_event_target" "{pipeline_name}_target" {{
  rule      = aws_cloudwatch_event_rule.{pipeline_name}_schedule.name
  target_id = "glue-job-{pipeline_name}"
  arn       = "arn:aws:glue:{region}:{account_id}:job/{job_name}"
  role_arn  = aws_iam_role.eventbridge_glue_role.arn

  input = jsonencode({{
    "--pipeline_name" = "{pipeline_name}"
  }})
}}
'''

        return tf_content

    def generate_all(self, output_dir: Path):
        """Generate all Terraform files."""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

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
            "glue_database.tf": self.generate_glue_database_tf(contracts),
            "glue_jobs.tf": self.generate_glue_jobs_tf(),
            "eventbridge.tf": self.generate_eventbridge_tf(),
        }

        for filename, content in files.items():
            filepath = output_dir / filename
            filepath.write_text(content)
            print(f"  Generated: {filename}")

        return output_dir
