"""
Command-line interface for Alur Framework.
"""

import click
import os
import shutil
from pathlib import Path


@click.group()
@click.version_option(version="0.2.0")
def main():
    """
    Alur Framework - A Python framework for building data lake pipelines.

    Use 'alur --help' to see available commands.
    """
    pass


@main.command()
@click.argument("project_name")
@click.option(
    "--path",
    default=".",
    help="Directory where the project should be created (default: current directory)",
)
def init(project_name: str, path: str):
    """
    Initialize a new Alur project.

    Creates a new project directory with sample contracts, pipelines, and configuration.

    Example:
        alur init my_datalake
    """
    # Resolve paths
    target_dir = Path(path) / project_name
    template_dir = Path(__file__).parent / "templates" / "project"

    # Check if target directory already exists
    if target_dir.exists():
        click.echo(f"Error: Directory '{target_dir}' already exists!", err=True)
        return 1

    # Create target directory
    click.echo(f"Creating new Alur project: {project_name}")
    target_dir.mkdir(parents=True, exist_ok=True)

    # Copy template files
    try:
        # Copy all template files
        for item in template_dir.rglob("*"):
            if item.is_file():
                # Calculate relative path
                relative_path = item.relative_to(template_dir)
                target_file = target_dir / relative_path

                # Create parent directory if needed
                target_file.parent.mkdir(parents=True, exist_ok=True)

                # Handle pyproject.toml specially (replace PROJECT_NAME)
                if item.name == "pyproject.toml":
                    content = item.read_text()
                    content = content.replace("PROJECT_NAME", project_name)
                    target_file.write_text(content)
                else:
                    # Copy file
                    shutil.copy2(item, target_file)

                click.echo(f"  Created: {relative_path}")

        click.echo(f"\n[SUCCESS] Project '{project_name}' created successfully!")
        click.echo(f"\nNext steps:")
        click.echo(f"  cd {project_name}")
        click.echo(f"  # Edit contracts in contracts/")
        click.echo(f"  # Edit pipelines in pipelines/")
        click.echo(f"  python main.py  # Run locally")

    except Exception as e:
        click.echo(f"Error creating project: {str(e)}", err=True)
        # Clean up on failure
        if target_dir.exists():
            shutil.rmtree(target_dir)
        return 1

    return 0


@main.command()
@click.argument("pipeline_name", required=False)
@click.option("--local", is_flag=True, default=True, help="Run in local mode (default)")
@click.option("--all", "run_all", is_flag=True, help="Run all pipelines")
def run(pipeline_name: str, local: bool, run_all: bool):
    """
    Run a pipeline or all pipelines.

    Example:
        alur run clean_orders --local
        alur run --all
    """
    if not run_all and not pipeline_name:
        click.echo("Error: Must specify a pipeline name or use --all", err=True)
        return 1

    # Import dependencies
    try:
        from .engine import LocalAdapter, AWSAdapter, PipelineRunner

        # Import user's pipelines to register them
        import pipelines  # noqa: F401

    except ImportError as e:
        click.echo(f"Error: Could not import pipelines. Make sure you're in an Alur project directory.", err=True)
        click.echo(f"Details: {str(e)}", err=True)
        return 1

    # Create adapter
    if local:
        click.echo("Running in local mode...")
        adapter = LocalAdapter(base_path="/tmp/alur")
    else:
        click.echo("Running in AWS mode...")
        adapter = AWSAdapter()

    # Create runner
    runner = PipelineRunner(adapter)

    try:
        if run_all:
            click.echo("Running all pipelines...")
            runner.run_all()
        else:
            click.echo(f"Running pipeline: {pipeline_name}")
            runner.run_pipeline(pipeline_name)

        click.echo("\n[OK] Pipeline execution completed successfully!")
        return 0

    except Exception as e:
        click.echo(f"\n[ERROR] Pipeline execution failed: {str(e)}", err=True)
        return 1


@main.command()
def validate():
    """
    Validate the pipeline DAG for circular dependencies.

    Example:
        alur validate
    """
    try:
        # Import user's pipelines to register them
        import pipelines  # noqa: F401
        from .decorators import PipelineRegistry

        click.echo("Validating pipeline DAG...")

        PipelineRegistry.validate_dag()

        pipelines_count = len(PipelineRegistry.get_all())
        click.echo(f"[OK] DAG validation passed! Found {pipelines_count} pipeline(s).")

        # Show execution order
        execution_order = PipelineRegistry.get_execution_order()
        if execution_order:
            click.echo("\nExecution order:")
            for i, table_name in enumerate(execution_order, 1):
                click.echo(f"  {i}. {table_name}")

        return 0

    except Exception as e:
        click.echo(f"[ERROR] Validation failed: {str(e)}", err=True)
        return 1


@main.command()
def build():
    """
    Build the project into a distributable wheel file.

    Example:
        alur build
    """
    import subprocess

    click.echo("Building project...")

    try:
        # Run pip build
        result = subprocess.run(
            ["python", "-m", "build"],
            capture_output=True,
            text=True,
            check=True
        )

        click.echo(result.stdout)
        click.echo("[OK] Build completed successfully!")
        click.echo("\nWheel file created in: ./dist/")
        return 0

    except subprocess.CalledProcessError as e:
        click.echo(f"[ERROR] Build failed: {e.stderr}", err=True)
        return 1
    except FileNotFoundError:
        click.echo("Error: 'build' module not found. Install it with: pip install build", err=True)
        return 1


def validate_project_imports():
    """
    Validate that all Python imports in the project can be resolved.
    Returns (success: bool, errors: list).
    """
    import sys
    import importlib.util

    errors = []

    # Add current directory to Python path temporarily
    project_root = str(Path.cwd())
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    try:
        # Validate contracts module
        if Path("contracts").exists():
            try:
                import contracts
                click.echo("  Validating contracts module...")

                # Check __init__.py imports
                init_file = Path("contracts/__init__.py")
                if init_file.exists():
                    with open(init_file, 'r') as f:
                        content = f.read()

                    # Look for 'from .module import' patterns
                    import re
                    imports = re.findall(r'from\s+\.(\w+)\s+import', content)

                    for module_name in imports:
                        module_file = Path(f"contracts/{module_name}.py")
                        if not module_file.exists():
                            errors.append(f"contracts/__init__.py imports '{module_name}' but contracts/{module_name}.py doesn't exist")

            except ImportError as e:
                errors.append(f"Failed to import contracts module: {str(e)}")

        # Validate pipelines module
        if Path("pipelines").exists():
            try:
                import pipelines
                click.echo("  Validating pipelines module...")

                # Check __init__.py imports
                init_file = Path("pipelines/__init__.py")
                if init_file.exists():
                    with open(init_file, 'r') as f:
                        content = f.read()

                    # Look for 'from .module import' patterns
                    import re
                    imports = re.findall(r'from\s+\.(\w+)\s+import', content)

                    for module_name in imports:
                        module_file = Path(f"pipelines/{module_name}.py")
                        if not module_file.exists():
                            errors.append(f"pipelines/__init__.py imports '{module_name}' but pipelines/{module_name}.py doesn't exist")

            except ImportError as e:
                errors.append(f"Failed to import pipelines module: {str(e)}")

        # Try to import config.settings
        try:
            import config.settings
            click.echo("  Validating config.settings...")
        except ImportError as e:
            errors.append(f"Failed to import config.settings: {str(e)}")

    finally:
        # Clean up sys.path
        if project_root in sys.path:
            sys.path.remove(project_root)

    return len(errors) == 0, errors


@main.command()
@click.option("--env", default="dev", help="Environment (dev, staging, prod)")
@click.option("--skip-build", is_flag=True, help="Skip building wheel")
@click.option("--skip-terraform", is_flag=True, help="Skip Terraform apply")
@click.option("--auto-approve", is_flag=True, help="Auto-approve Terraform changes")
def deploy(env: str, skip_build: bool, skip_terraform: bool, auto_approve: bool):
    """
    Deploy your project to AWS (one-command deployment).

    This command does everything:
    1. Builds your Python wheel
    2. Generates Terraform files
    3. Applies Terraform (creates AWS resources)
    4. Uploads code to S3
    5. Creates/updates Glue jobs

    Example:
        alur deploy --env dev
        alur deploy --env prod --auto-approve
        alur deploy --skip-terraform  # Just upload code
    """
    import subprocess
    import glob

    click.echo("=" * 60)
    click.echo(f"ALUR DEPLOYMENT - Environment: {env}")
    click.echo("=" * 60)

    # Step 1: Load configuration and validate
    click.echo("\n[1/6] Loading configuration...")
    try:
        from config import settings

        # Validate required settings
        required_settings = ['AWS_REGION', 'BRONZE_BUCKET', 'SILVER_BUCKET', 'GOLD_BUCKET', 'ARTIFACTS_BUCKET']
        missing = [s for s in required_settings if not hasattr(settings, s)]
        if missing:
            click.echo(f"[ERROR] Missing required settings in config/settings.py:", err=True)
            for setting in missing:
                click.echo(f"  - {setting}", err=True)
            click.echo("\nPlease add these to your config/settings.py file", err=True)
            return 1

        bucket = settings.ARTIFACTS_BUCKET
        region = settings.AWS_REGION

        click.echo(f"  Region: {region}")
        click.echo(f"  Artifacts bucket: {bucket}")

        # Validate AWS credentials
        try:
            import boto3
            sts = boto3.client('sts', region_name=region)
            identity = sts.get_caller_identity()
            click.echo(f"  AWS Account: {identity['Account']}")
        except Exception as e:
            click.echo(f"[ERROR] AWS credentials not configured or invalid", err=True)
            click.echo(f"  Details: {str(e)}", err=True)
            click.echo("\nTo fix:", err=True)
            click.echo("  1. Run 'aws configure' to set up credentials", err=True)
            click.echo("  2. Or set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY environment variables", err=True)
            return 1

        # Check if required directories exist
        if not Path("contracts").exists():
            click.echo("[ERROR] contracts/ directory not found", err=True)
            click.echo("  Create at least one contract file in contracts/", err=True)
            return 1

        if not Path("pipelines").exists():
            click.echo("[ERROR] pipelines/ directory not found", err=True)
            click.echo("  Create at least one pipeline file in pipelines/", err=True)
            return 1

        # Validate Python imports
        click.echo("\n  Validating project imports...")
        success, import_errors = validate_project_imports()
        if not success:
            click.echo("\n[ERROR] Import validation failed:", err=True)
            for error in import_errors:
                click.echo(f"  - {error}", err=True)
            click.echo("\nPlease fix these import errors before deploying", err=True)
            return 1
        click.echo("  [OK] All imports validated successfully")

    except ImportError:
        click.echo("[ERROR] Could not import config/settings.py", err=True)
        click.echo("\nMake sure you're in an Alur project directory with:", err=True)
        click.echo("  - config/settings.py file", err=True)
        click.echo("  - contracts/ directory", err=True)
        click.echo("  - pipelines/ directory", err=True)
        return 1

    # Step 2: Build wheel
    if not skip_build:
        click.echo("\n[2/6] Building Python wheel...")
        try:
            result = subprocess.run(
                ["python", "-m", "build"],
                capture_output=True,
                text=True,
                check=True
            )
            click.echo("  [OK] Build complete")

            # Find the wheel file
            wheel_files = glob.glob("dist/*.whl")
            if not wheel_files:
                click.echo("[ERROR] No wheel file found in dist/", err=True)
                return 1

            wheel_file = wheel_files[-1]  # Get latest
            click.echo(f"  Wheel: {wheel_file}")

        except subprocess.CalledProcessError as e:
            click.echo(f"[ERROR] Build failed: {e.stderr}", err=True)
            return 1
        except FileNotFoundError:
            click.echo("[ERROR] 'build' module not found. Install: pip install build", err=True)
            return 1
    else:
        click.echo("\n[2/6] Skipping build...")
        wheel_files = glob.glob("dist/*.whl")
        if not wheel_files:
            click.echo("[ERROR] No wheel file found. Run without --skip-build first", err=True)
            return 1
        wheel_file = wheel_files[-1]

    # Step 3: Generate Terraform (if not skipping)
    if not skip_terraform:
        click.echo("\n[3/6] Generating Terraform files...")
        terraform_dir = Path("terraform")
        terraform_dir.mkdir(parents=True, exist_ok=True)

        # Auto-generate all infrastructure from contracts and pipelines
        try:
            from alur.infra import InfrastructureGenerator

            generator = InfrastructureGenerator(Path.cwd())
            generator.generate_all(terraform_dir)

            click.echo("  [OK] Terraform files generated automatically from contracts and pipelines")

        except Exception as e:
            click.echo(f"[ERROR] Terraform generation failed: {e}", err=True)
            import traceback
            traceback.print_exc()
            return 1
    else:
        click.echo("\n[3/6] Skipping Terraform...")
        terraform_dir = Path("terraform")

    # Step 4: Apply Terraform (if not skipping)
    if not skip_terraform:
        click.echo("\n[4/6] Applying Terraform...")

        try:
            # Check if terraform is installed
            subprocess.run(["terraform", "version"], capture_output=True, check=True)

            # Initialize
            click.echo("  Running: terraform init...")
            result = subprocess.run(
                ["terraform", "init"],
                cwd=terraform_dir,
                capture_output=True,
                text=True
            )

            if result.returncode != 0:
                click.echo(f"  Warning: terraform init had issues: {result.stderr}")

            # Apply
            apply_cmd = ["terraform", "apply"]
            if auto_approve:
                apply_cmd.append("-auto-approve")

            click.echo(f"  Running: terraform apply{' -auto-approve' if auto_approve else ''}...")

            if auto_approve:
                result = subprocess.run(
                    apply_cmd,
                    cwd=terraform_dir,
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0:
                    click.echo("  [OK] Infrastructure deployed")
                else:
                    click.echo(f"  [ERROR] Terraform apply failed: {result.stderr}", err=True)
                    return 1
            else:
                # Interactive mode
                result = subprocess.run(apply_cmd, cwd=terraform_dir)
                if result.returncode != 0:
                    click.echo("  [ERROR] Terraform apply failed", err=True)
                    return 1

        except FileNotFoundError:
            click.echo("  [ERROR] Terraform not found. Install from: https://www.terraform.io/downloads", err=True)
            click.echo("  Or use --skip-terraform to just upload code", err=True)
            return 1
    else:
        click.echo("\n[4/6] Skipping Terraform apply...")

    # Step 5: Upload to S3
    click.echo("\n[5/6] Uploading to S3...")

    try:
        # Check AWS CLI
        subprocess.run(["aws", "--version"], capture_output=True, check=True)

        # Build and upload Alur framework wheel
        import alur
        alur_root = Path(alur.__path__[0]).parent.parent  # Go to Alur project root
        alur_root_str = str(alur_root)  # Convert to string for subprocess compatibility

        click.echo("  Building Alur framework wheel...")
        try:
            result = subprocess.run(
                ["python", "-m", "build"],
                cwd=alur_root_str,
                capture_output=True,
                text=True,
                check=True
            )

            # Find the framework wheel
            framework_wheels = list((Path(alur_root_str) / "dist").glob("*.whl"))
            if framework_wheels:
                framework_wheel = framework_wheels[-1]
                framework_wheel_name = framework_wheel.name
                s3_framework_path = f"s3://{bucket}/wheels/{framework_wheel_name}"

                click.echo(f"  Uploading framework: {framework_wheel_name}")
                result = subprocess.run(
                    ["aws", "s3", "cp", str(framework_wheel), s3_framework_path],
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0:
                    click.echo("  [OK] Framework wheel uploaded")
                else:
                    click.echo(f"  Warning: Framework upload failed: {result.stderr}")
            else:
                click.echo("  Warning: Framework wheel not found")

        except Exception as e:
            click.echo(f"  Warning: Could not build framework wheel: {e}")

        # Upload user project wheel
        wheel_name = os.path.basename(wheel_file)
        s3_wheel_path = f"s3://{bucket}/wheels/{wheel_name}"

        click.echo(f"  Uploading project: {wheel_file}")
        click.echo(f"  To: {s3_wheel_path}")

        result = subprocess.run(
            ["aws", "s3", "cp", wheel_file, s3_wheel_path],
            capture_output=True,
            text=True
        )

        if result.returncode == 0:
            click.echo("  [OK] Project wheel uploaded")
        else:
            click.echo(f"  [ERROR] Upload failed: {result.stderr}", err=True)
            return 1

        # Upload driver.py
        driver_path = Path(alur.__path__[0]) / "templates" / "aws" / "driver.py"

        if driver_path.exists():
            s3_driver_path = f"s3://{bucket}/scripts/driver.py"
            click.echo(f"  Uploading: driver.py")

            result = subprocess.run(
                ["aws", "s3", "cp", str(driver_path), s3_driver_path],
                capture_output=True,
                text=True
            )

            if result.returncode == 0:
                click.echo("  [OK] Driver script uploaded")
            else:
                click.echo(f"  Warning: Driver upload failed: {result.stderr}")

    except FileNotFoundError:
        click.echo("  [ERROR] AWS CLI not found. Install: pip install awscli", err=True)
        return 1
    except Exception as e:
        click.echo(f"  [ERROR] Upload failed: {str(e)}", err=True)
        return 1

    # Step 6: Summary
    click.echo("\n[6/6] Deployment Summary")
    click.echo("  " + "=" * 56)
    click.echo(f"  Environment: {env}")
    click.echo(f"  Wheel: {wheel_name}")
    click.echo(f"  S3 Location: {s3_wheel_path}")
    click.echo(f"  Region: {region}")
    click.echo("  " + "=" * 56)

    click.echo("\n[OK] Deployment complete!")

    click.echo("\nNext steps:")
    click.echo("  1. Create Glue jobs pointing to:")
    click.echo(f"     Script: s3://{bucket}/scripts/driver.py")
    click.echo(f"     Library: {s3_wheel_path}")
    click.echo("  2. Or use AWS Console to create jobs manually")
    click.echo(f"  3. Run with: aws glue start-job-run --job-name <job-name>")

    return 0


@main.group()
def infra():
    """Infrastructure management commands."""
    pass


@infra.command()
@click.option("--output", default="terraform", help="Output directory for Terraform files")
def generate(output: str):
    """
    Generate Terraform infrastructure files.

    Example:
        alur infra generate
        alur infra generate --output ./infrastructure
    """
    click.echo(f"Generating Terraform files in: {output}")

    # Create output directory
    output_path = Path(output)
    output_path.mkdir(parents=True, exist_ok=True)

    # Import settings
    try:
        from config import settings
    except ImportError:
        click.echo("Error: Could not import config/settings.py", err=True)
        click.echo("Make sure you're in an Alur project directory.", err=True)
        return 1

    # Create basic Terraform files
    # This is a simplified version - full implementation would use Jinja2 templates

    # S3 buckets
    s3_tf = f"""# S3 Buckets for Alur Data Lake

resource "aws_s3_bucket" "bronze" {{
  bucket = "{getattr(settings, 'BRONZE_BUCKET', 'alur-bronze-dev')}"

  tags = {{
    Name        = "Alur Bronze Layer"
    Environment = "{getattr(settings, 'ENVIRONMENT', 'dev')}"
    Layer       = "bronze"
  }}
}}

resource "aws_s3_bucket" "silver" {{
  bucket = "{getattr(settings, 'SILVER_BUCKET', 'alur-silver-dev')}"

  tags = {{
    Name        = "Alur Silver Layer"
    Environment = "{getattr(settings, 'ENVIRONMENT', 'dev')}"
    Layer       = "silver"
  }}
}}

resource "aws_s3_bucket" "gold" {{
  bucket = "{getattr(settings, 'GOLD_BUCKET', 'alur-gold-dev')}"

  tags = {{
    Name        = "Alur Gold Layer"
    Environment = "{getattr(settings, 'ENVIRONMENT', 'dev')}"
    Layer       = "gold"
  }}
}}

resource "aws_s3_bucket" "artifacts" {{
  bucket = "{getattr(settings, 'ARTIFACTS_BUCKET', 'alur-artifacts-dev')}"

  tags = {{
    Name        = "Alur Artifacts"
    Environment = "{getattr(settings, 'ENVIRONMENT', 'dev')}"
  }}
}}
"""

    # Write S3 file
    with open(output_path / "s3.tf", "w") as f:
        f.write(s3_tf)
    click.echo("  Created: s3.tf")

    # Glue database
    glue_tf = f"""# AWS Glue Database

resource "aws_glue_catalog_database" "alur" {{
  name        = "{getattr(settings, 'GLUE_DATABASE', 'alur_datalake_dev')}"
  description = "Alur Data Lake Catalog"

  tags = {{
    Environment = "{getattr(settings, 'ENVIRONMENT', 'dev')}"
  }}
}}
"""

    with open(output_path / "glue.tf", "w") as f:
        f.write(glue_tf)
    click.echo("  Created: glue.tf")

    # DynamoDB state table
    dynamodb_tf = f"""# DynamoDB Table for Pipeline State

resource "aws_dynamodb_table" "state" {{
  name           = "{getattr(settings, 'STATE_TABLE', 'alur-state-dev')}"
  billing_mode   = "PAY_PER_REQUEST"
  hash_key       = "key"

  attribute {{
    name = "key"
    type = "S"
  }}

  tags = {{
    Name        = "Alur State Table"
    Environment = "{getattr(settings, 'ENVIRONMENT', 'dev')}"
  }}
}}
"""

    with open(output_path / "dynamodb.tf", "w") as f:
        f.write(dynamodb_tf)
    click.echo("  Created: dynamodb.tf")

    # Provider configuration
    provider_tf = f"""# Terraform Provider Configuration

terraform {{
  required_version = ">= 1.0"

  required_providers {{
    aws = {{
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }}
  }}
}}

provider "aws" {{
  region = "{getattr(settings, 'AWS_REGION', 'us-east-1')}"

  default_tags {{
    tags = {{
      Project     = "Alur"
      ManagedBy   = "Terraform"
      Environment = "{getattr(settings, 'ENVIRONMENT', 'dev')}"
    }}
  }}
}}
"""

    with open(output_path / "provider.tf", "w") as f:
        f.write(provider_tf)
    click.echo("  Created: provider.tf")

    click.echo(f"\n[OK] Terraform files generated successfully in: {output}")
    click.echo("\nNext steps:")
    click.echo(f"  cd {output}")
    click.echo("  terraform init")
    click.echo("  terraform plan")
    click.echo("  terraform apply")

    return 0


@main.command()
@click.option("--env", default="dev", help="Environment to check status for")
def status(env: str):
    """Check deployment status and show resource information."""
    import subprocess

    click.echo("=" * 60)
    click.echo(f"ALUR STATUS - Environment: {env}")
    click.echo("=" * 60)

    # Load configuration
    try:
        from config import settings
        region = settings.AWS_REGION
        bronze_bucket = settings.BRONZE_BUCKET
        silver_bucket = settings.SILVER_BUCKET
        gold_bucket = settings.GOLD_BUCKET
        artifacts_bucket = settings.ARTIFACTS_BUCKET
        glue_database = settings.GLUE_DATABASE
    except ImportError:
        click.echo("[ERROR] Not in an Alur project directory", err=True)
        return 1

    click.echo(f"\nConfiguration:")
    click.echo(f"  Region: {region}")
    click.echo(f"  Environment: {env}")
    click.echo(f"  Glue Database: {glue_database}")

    # Check S3 buckets
    click.echo(f"\nS3 Buckets:")
    for bucket_name, layer in [(bronze_bucket, "Bronze"), (silver_bucket, "Silver"),
                                (gold_bucket, "Gold"), (artifacts_bucket, "Artifacts")]:
        try:
            result = subprocess.run(
                ["aws", "s3", "ls", f"s3://{bucket_name}/", "--region", region],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                # Count objects
                result_du = subprocess.run(
                    ["aws", "s3", "ls", f"s3://{bucket_name}/", "--recursive",
                     "--summarize", "--region", region],
                    capture_output=True,
                    text=True
                )
                lines = result_du.stdout.strip().split('\n')
                size_line = [l for l in lines if 'Total Size' in l]
                objects_line = [l for l in lines if 'Total Objects' in l]

                size = size_line[0].split(':')[1].strip() if size_line else "Unknown"
                objects = objects_line[0].split(':')[1].strip() if objects_line else "Unknown"

                click.echo(f"  ✓ {layer:10} {bucket_name:30} ({objects} objects, {size} bytes)")
            else:
                click.echo(f"  ✗ {layer:10} {bucket_name:30} (not found)")
        except Exception as e:
            click.echo(f"  ? {layer:10} {bucket_name:30} (error checking: {str(e)})")

    # Check Glue database and tables
    click.echo(f"\nGlue Database:")
    try:
        result = subprocess.run(
            ["aws", "glue", "get-database", "--name", glue_database, "--region", region],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            click.echo(f"  ✓ Database exists: {glue_database}")

            # List tables
            result_tables = subprocess.run(
                ["aws", "glue", "get-tables", "--database-name", glue_database,
                 "--region", region, "--query", "TableList[].Name", "--output", "text"],
                capture_output=True,
                text=True
            )
            if result_tables.returncode == 0 and result_tables.stdout.strip():
                tables = result_tables.stdout.strip().split('\t')
                click.echo(f"  Tables ({len(tables)}):")
                for table in tables:
                    click.echo(f"    - {table}")
            else:
                click.echo(f"  No tables found")
        else:
            click.echo(f"  ✗ Database not found: {glue_database}")
    except Exception as e:
        click.echo(f"  ? Error checking database: {str(e)}")

    # Check Glue jobs
    click.echo(f"\nGlue Jobs:")
    try:
        result = subprocess.run(
            ["aws", "glue", "list-jobs", "--region", region,
             "--query", f"JobNames[?contains(@, 'alur-') && contains(@, '-{env}')]", "--output", "text"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0 and result.stdout.strip():
            jobs = result.stdout.strip().split('\t')
            click.echo(f"  Found {len(jobs)} job(s):")
            for job in jobs:
                click.echo(f"    - {job}")
        else:
            click.echo(f"  No Alur jobs found for environment '{env}'")
    except Exception as e:
        click.echo(f"  ? Error checking jobs: {str(e)}")

    click.echo(f"\nTo deploy or update: alur deploy --env {env}")
    click.echo(f"To destroy infrastructure: alur destroy --env {env}")


@main.command()
@click.option("--env", default="dev", help="Environment to destroy")
@click.option("--force", is_flag=True, help="Force destroy by emptying S3 buckets first")
@click.option("--auto-approve", is_flag=True, help="Auto-approve Terraform destroy")
def destroy(env: str, force: bool, auto_approve: bool):
    """Destroy all Alur infrastructure for an environment."""
    import subprocess

    click.echo("=" * 60)
    click.echo(f"ALUR DESTROY - Environment: {env}")
    click.echo("=" * 60)

    if not force and not auto_approve:
        click.echo("\n⚠️  WARNING: This will destroy all infrastructure!")
        click.echo("  - S3 buckets (data will be lost)")
        click.echo("  - Glue database and tables")
        click.echo("  - Glue jobs")
        click.echo("  - IAM roles")

        if not click.confirm("\nAre you sure you want to continue?"):
            click.echo("Destroy cancelled")
            return 0

    # Load configuration
    try:
        from config import settings
        region = settings.AWS_REGION
        bronze_bucket = settings.BRONZE_BUCKET
        silver_bucket = settings.SILVER_BUCKET
        gold_bucket = settings.GOLD_BUCKET
        artifacts_bucket = settings.ARTIFACTS_BUCKET
    except ImportError:
        click.echo("[ERROR] Not in an Alur project directory", err=True)
        return 1

    # Empty S3 buckets if force is enabled
    if force:
        click.echo("\n[1/2] Emptying S3 buckets...")
        for bucket in [bronze_bucket, silver_bucket, gold_bucket, artifacts_bucket]:
            try:
                click.echo(f"  Emptying: {bucket}")
                result = subprocess.run(
                    ["aws", "s3", "rm", f"s3://{bucket}/", "--recursive", "--region", region],
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0:
                    click.echo(f"    ✓ Emptied {bucket}")
                else:
                    # Bucket might not exist, that's okay
                    click.echo(f"    - {bucket} (already empty or doesn't exist)")
            except Exception as e:
                click.echo(f"    Warning: {str(e)}")

    # Run Terraform destroy
    click.echo(f"\n[2/2] Destroying Terraform infrastructure...")
    terraform_dir = Path("terraform")

    if not terraform_dir.exists():
        click.echo("[ERROR] terraform/ directory not found", err=True)
        click.echo("  Nothing to destroy", err=True)
        return 1

    try:
        cmd = ["terraform", "destroy"]
        if auto_approve:
            cmd.append("-auto-approve")

        result = subprocess.run(
            cmd,
            cwd=terraform_dir,
            text=True
        )

        if result.returncode == 0:
            click.echo("\n[OK] Infrastructure destroyed successfully!")
        else:
            click.echo("\n[ERROR] Terraform destroy failed", err=True)
            return 1

    except FileNotFoundError:
        click.echo("[ERROR] Terraform not installed", err=True)
        return 1


@main.command()
@click.argument("pipeline_name")
@click.option("--env", default="dev", help="Environment to run in")
@click.option("--wait/--no-wait", default=True, help="Wait for job to complete")
def run(pipeline_name: str, env: str, wait: bool):
    """
    Run a specific pipeline on AWS Glue.

    Example:
        alur run clean_orders
        alur run calculate_daily_sales --env prod
    """
    import subprocess
    import time

    click.echo("=" * 60)
    click.echo(f"ALUR RUN - Pipeline: {pipeline_name}")
    click.echo("=" * 60)

    # Load configuration
    try:
        from config import settings
        region = settings.AWS_REGION
    except ImportError:
        click.echo("[ERROR] Not in an Alur project directory", err=True)
        return 1

    # Construct job name (matches terraform naming convention)
    job_name = f"alur-{pipeline_name}-{env}"

    click.echo(f"\nStarting Glue job: {job_name}")

    # Start the job
    try:
        result = subprocess.run(
            ["aws", "glue", "start-job-run",
             "--job-name", job_name,
             "--arguments", f'{{"--pipeline_name":"{pipeline_name}"}}',
             "--region", region],
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            click.echo(f"[ERROR] Failed to start job: {result.stderr}", err=True)
            return 1

        # Parse job run ID
        import json
        response = json.loads(result.stdout)
        job_run_id = response.get("JobRunId")

        click.echo(f"  ✓ Job started successfully")
        click.echo(f"  Job Run ID: {job_run_id}")

        if not wait:
            click.echo(f"\nCheck status with: alur logs {job_run_id}")
            return 0

        # Wait for completion
        click.echo(f"\nWaiting for job to complete...")

        while True:
            time.sleep(10)

            result = subprocess.run(
                ["aws", "glue", "get-job-run",
                 "--job-name", job_name,
                 "--run-id", job_run_id,
                 "--region", region,
                 "--query", "JobRun.[JobRunState,ErrorMessage]",
                 "--output", "text"],
                capture_output=True,
                text=True
            )

            if result.returncode != 0:
                click.echo(f"[ERROR] Failed to check job status", err=True)
                return 1

            parts = result.stdout.strip().split('\t')
            state = parts[0] if len(parts) > 0 else "UNKNOWN"
            error_msg = parts[1] if len(parts) > 1 and parts[1] != "None" else None

            if state in ["SUCCEEDED", "FAILED", "STOPPED", "TIMEOUT"]:
                break

            click.echo(f"  Status: {state}...")

        if state == "SUCCEEDED":
            click.echo(f"\n[OK] Pipeline '{pipeline_name}' completed successfully!")
            return 0
        else:
            click.echo(f"\n[ERROR] Pipeline failed with state: {state}", err=True)
            if error_msg:
                click.echo(f"  Error: {error_msg}", err=True)
            click.echo(f"\nView logs: alur logs {job_run_id}")
            return 1

    except FileNotFoundError:
        click.echo("[ERROR] AWS CLI not installed", err=True)
        return 1
    except Exception as e:
        click.echo(f"[ERROR] {str(e)}", err=True)
        return 1


@main.command()
@click.argument("job_run_id", required=False)
@click.option("--env", default="dev", help="Environment")
@click.option("--tail/--no-tail", default=False, help="Follow logs in real-time")
def logs(job_run_id: str, env: str, tail: bool):
    """
    Fetch and display Glue job logs.

    Examples:
        alur logs jr_abc123...
        alur logs --tail  # Shows recent logs for environment
    """
    import subprocess

    # Load configuration
    try:
        from config import settings
        region = settings.AWS_REGION
    except ImportError:
        click.echo("[ERROR] Not in an Alur project directory", err=True)
        return 1

    if tail or not job_run_id:
        # Show recent logs for all jobs
        log_group = "/aws-glue/jobs/output"

        cmd = ["aws", "logs", "tail", log_group, "--region", region]
        if tail:
            cmd.append("--follow")
        else:
            cmd.extend(["--since", "1h"])

        try:
            subprocess.run(cmd)
        except FileNotFoundError:
            click.echo("[ERROR] AWS CLI not installed", err=True)
            return 1
    else:
        # Show logs for specific job run
        log_group = "/aws-glue/jobs/output"

        try:
            result = subprocess.run(
                ["aws", "logs", "tail", log_group,
                 "--log-stream-names", job_run_id,
                 "--region", region,
                 "--format", "short"],
                capture_output=True,
                text=True
            )

            if result.returncode == 0:
                click.echo(result.stdout)
            else:
                click.echo(f"[ERROR] Failed to fetch logs: {result.stderr}", err=True)
                return 1

        except FileNotFoundError:
            click.echo("[ERROR] AWS CLI not installed", err=True)
            return 1


@main.command()
def validate():
    """
    Validate contracts and pipelines before deployment.

    Checks for:
    - Import errors
    - Schema issues
    - Circular dependencies
    - Missing fields
    """
    click.echo("=" * 60)
    click.echo("ALUR VALIDATE")
    click.echo("=" * 60)

    errors = []
    warnings = []

    # Check 1: Import contracts
    click.echo("\n[1/5] Validating contracts...")
    try:
        import contracts.bronze
        import contracts.silver
        from alur.core import BronzeTable, SilverTable, GoldTable

        # Check all contract classes
        for module in [contracts.bronze, contracts.silver]:
            for name in dir(module):
                obj = getattr(module, name)
                if isinstance(obj, type) and issubclass(obj, (BronzeTable, SilverTable, GoldTable)):
                    if obj not in [BronzeTable, SilverTable, GoldTable]:
                        # Validate has fields
                        fields = obj.get_fields()
                        if not fields:
                            warnings.append(f"Table {name} has no fields defined")
                        else:
                            click.echo(f"  ✓ {name}: {len(fields)} fields")

        try:
            import contracts.gold
            for name in dir(contracts.gold):
                obj = getattr(contracts.gold, name)
                if isinstance(obj, type) and issubclass(obj, GoldTable):
                    if obj != GoldTable:
                        fields = obj.get_fields()
                        if not fields:
                            warnings.append(f"Table {name} has no fields defined")
                        else:
                            click.echo(f"  ✓ {name}: {len(fields)} fields")
        except ImportError:
            pass  # Gold layer is optional

    except ImportError as e:
        errors.append(f"Failed to import contracts: {str(e)}")

    # Check 2: Import pipelines
    click.echo("\n[2/5] Validating pipelines...")
    try:
        import pipelines
        from alur.decorators import PipelineRegistry

        all_pipelines = PipelineRegistry.get_all()
        if not all_pipelines:
            warnings.append("No pipelines registered")
        else:
            for name, pipeline in all_pipelines.items():
                click.echo(f"  ✓ {name}")
                click.echo(f"      Sources: {list(pipeline.sources.keys())}")
                click.echo(f"      Target: {pipeline.target.get_table_name()}")

    except ImportError as e:
        errors.append(f"Failed to import pipelines: {str(e)}")

    # Check 3: Validate DAG
    click.echo("\n[3/5] Validating pipeline DAG...")
    try:
        from alur.decorators import PipelineRegistry
        PipelineRegistry.validate_dag()
        click.echo("  ✓ No circular dependencies detected")
    except ValueError as e:
        errors.append(f"DAG validation failed: {str(e)}")
    except Exception as e:
        errors.append(f"DAG validation error: {str(e)}")

    # Check 4: Validate configuration
    click.echo("\n[4/5] Validating configuration...")
    try:
        from config import settings

        required_attrs = ['AWS_REGION', 'BRONZE_BUCKET', 'SILVER_BUCKET',
                         'GOLD_BUCKET', 'ARTIFACTS_BUCKET', 'GLUE_DATABASE']

        for attr in required_attrs:
            if not hasattr(settings, attr):
                errors.append(f"Missing required setting: {attr}")
            else:
                click.echo(f"  ✓ {attr}: {getattr(settings, attr)}")

    except ImportError:
        errors.append("Failed to import config.settings")

    # Check 5: Check Terraform generation
    click.echo("\n[5/5] Testing Terraform generation...")
    try:
        from alur.infra import InfrastructureGenerator
        from config import settings

        project_root = Path.cwd()
        generator = InfrastructureGenerator(settings, project_root)

        # Try to generate (but don't write)
        provider_tf = generator.generate_provider_tf()
        s3_tf = generator.generate_s3_tf()
        glue_db_tf = generator.generate_glue_database_tf()

        click.echo(f"  ✓ Terraform generation successful")

    except Exception as e:
        errors.append(f"Terraform generation failed: {str(e)}")

    # Summary
    click.echo("\n" + "=" * 60)
    click.echo("VALIDATION SUMMARY")
    click.echo("=" * 60)

    if warnings:
        click.echo(f"\n⚠️  {len(warnings)} warning(s):")
        for warning in warnings:
            click.echo(f"  - {warning}")

    if errors:
        click.echo(f"\n❌ {len(errors)} error(s):")
        for error in errors:
            click.echo(f"  - {error}")
        click.echo("\n[FAILED] Validation failed")
        return 1
    else:
        click.echo(f"\n[OK] Validation passed!")
        if warnings:
            click.echo(f"  ({len(warnings)} warnings)")
        return 0


@main.command()
@click.option("--verbose", "-v", is_flag=True, help="Show detailed information")
def list(verbose: bool):
    """
    List all registered pipelines and tables.

    Example:
        alur list
        alur list --verbose
    """
    click.echo("=" * 60)
    click.echo("ALUR PIPELINES & TABLES")
    click.echo("=" * 60)

    # Import to trigger registration
    try:
        import pipelines
        import contracts.bronze
        import contracts.silver
        try:
            import contracts.gold
        except ImportError:
            pass

    except ImportError as e:
        click.echo(f"[ERROR] Failed to import: {str(e)}", err=True)
        return 1

    # List contracts
    from alur.core import BronzeTable, SilverTable, GoldTable

    click.echo("\n📋 CONTRACTS")
    click.echo("-" * 60)

    for layer_name, base_class, module_name in [
        ("Bronze", BronzeTable, "contracts.bronze"),
        ("Silver", SilverTable, "contracts.silver"),
        ("Gold", GoldTable, "contracts.gold"),
    ]:
        try:
            module = __import__(module_name, fromlist=[''])
            tables = []

            for name in dir(module):
                obj = getattr(module, name)
                if isinstance(obj, type) and issubclass(obj, base_class) and obj != base_class:
                    tables.append((name, obj))

            if tables:
                click.echo(f"\n{layer_name} Layer ({len(tables)} tables):")
                for name, table_cls in tables:
                    table_name = table_cls.get_table_name()
                    fields = table_cls.get_fields()

                    if verbose:
                        click.echo(f"  • {name} ({table_name})")
                        click.echo(f"      Fields ({len(fields)}):")
                        for field_name, field in list(fields.items())[:5]:
                            field_type = field.__class__.__name__.replace("Field", "")
                            click.echo(f"        - {field_name}: {field_type}")
                        if len(fields) > 5:
                            click.echo(f"        ... and {len(fields) - 5} more")
                    else:
                        click.echo(f"  • {name} ({table_name}) - {len(fields)} fields")
        except ImportError:
            pass

    # List pipelines
    from alur.decorators import PipelineRegistry

    all_pipelines = PipelineRegistry.get_all()

    click.echo(f"\n⚙️  PIPELINES ({len(all_pipelines)} total)")
    click.echo("-" * 60)

    if not all_pipelines:
        click.echo("  No pipelines registered")
    else:
        for name, pipeline in all_pipelines.items():
            sources_str = ", ".join(pipeline.sources.keys())
            target_name = pipeline.target.get_table_name()

            if verbose:
                click.echo(f"\n  • {name}")
                click.echo(f"      Sources: {sources_str}")
                click.echo(f"      Target: {target_name}")
                click.echo(f"      Profile: {pipeline.resource_profile}")
            else:
                click.echo(f"  • {name}: [{sources_str}] → {target_name}")

    # Show execution order
    try:
        execution_order = PipelineRegistry.get_execution_order()

        # Map to pipeline names
        table_to_pipeline = {
            p.target.get_table_name(): name
            for name, p in all_pipelines.items()
        }

        pipeline_order = [
            table_to_pipeline.get(table_name, table_name)
            for table_name in execution_order
        ]

        click.echo(f"\n📊 EXECUTION ORDER")
        click.echo("-" * 60)
        for i, item in enumerate(pipeline_order, 1):
            if item in all_pipelines:
                click.echo(f"  {i}. {item}")

    except Exception as e:
        click.echo(f"\n⚠️  Could not determine execution order: {str(e)}")

    click.echo("\n")


if __name__ == "__main__":
    main()
