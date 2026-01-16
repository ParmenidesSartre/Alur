Here is the **Master Technical Specification** for **Project Alur**.

This document is formatted specifically for an **AI Agent (Coder)**. You can feed this into an IDE cursor/copilot or an LLM to generate the actual code files module by module.

It covers the Python Package structure (for PyPI) and the Infrastructure Strategy (Terraform).

---

# **Project Specification: Alur Framework**

**Version:** 0.1.0-alpha
**Type:** Python Package (PyPI) & Infrastructure Generator
**Repository Name:** `alur-framework`
**Target Environment:** Local (Dev) -> AWS (Production: S3 + Glue/EMR)

---

## **1. Packaging & Project Structure (For PyPI)**

The goal is to allow users to run `pip install alur-framework`.

### **1.1. Directory Layout (Source Code)**

```text
alur-framework/
├── pyproject.toml          # Build system requirements (Poetry or Setuptools)
├── README.md
├── src/
│   └── alur/
│       ├── __init__.py
│       ├── cli.py          # Entry point (Click)
│       ├── core/           # Base Classes (The OLM Logic)
│       │   ├── __init__.py
│       │   ├── contracts.py # BronzeTable, SilverTable, GoldTable
│       │   └── fields.py    # StringField, IntegerField, etc.
│       ├── decorators/     # @pipeline
│       │   └── __init__.py
│       ├── engine/         # Execution Logic
│       │   ├── __init__.py
│       │   ├── adapter.py   # RuntimeAdapter (Local vs AWS)
│       │   ├── spark.py     # SparkSession Factory
│       │   └── runner.py    # DAG Executor
│       ├── sources/        # Ingestion Logic
│       │   ├── __init__.py
│       │   └── postgres.py
│       └── templates/      # Jinja2 Templates for Scaffolding & Terraform
│           ├── project/    # Template for 'alur init'
│           └── terraform/  # Template for 'alur infra'

```

### **1.2. Dependencies (`pyproject.toml`)**

* `pyspark >= 3.3.0`
* `click >= 8.0` (CLI)
* `pydantic >= 2.0` (Configuration validation)
* `pyyaml` (Config parsing)
* `jinja2` (Code/Terraform generation)
* `boto3` (AWS interaction)
* `networkx` (DAG dependency resolution)

---

## **2. Core Modules Specification**

### **2.1. `alur.core.contracts` (The Model Layer)**

**Goal:** Define the Metaclasses that convert Python Classes into Iceberg Schemas.

* **Class `BaseTable**`:
* Must store schema metadata (`_fields`, `_partition_by`) during class creation (`__init_subclass__`).
* Method `to_iceberg_schema()`: Returns a Spark StructType.
* Method `get_s3_path()`: Returns `{bucket}/{layer}/{table_name}`.


* **Class `BronzeTable(BaseTable)**`:
* Enforces `format="parquet"`.
* Logic: Append-only.


* **Class `SilverTable(BaseTable)**`:
* Enforces `format="iceberg"`.
* Must have a `primary_key` defined in `Meta`.
* Logic: Merge-on-Read (Upsert).



### **2.2. `alur.decorators` (The Pipeline Layer)**

**Goal:** Decouple logic from execution.

* **Decorator `@pipeline**`:
* Arguments:
* `sources`: `Dict[str, Type[BaseTable]]`
* `target`: `Type[BaseTable]`
* `resource_profile`: `str` (optional)


* **Behavior:**
* Does NOT execute the function immediately.
* Registers the function in a global `PipelineRegistry`.
* Wraps the function to allow dependency injection (injects Spark DataFrames instead of Classes).





### **2.3. `alur.engine.adapter` (The Interface)**

**Goal:** Handle Local vs. Cloud differences.

* **Abstract Class `RuntimeAdapter**`:
* Method `read_table(table_cls) -> DataFrame`
* Method `write_table(df, table_cls, mode)`
* Method `get_state(key)` (For incremental watermark)


* **Implementation `LocalAdapter**`:
* Uses local filesystem `/tmp/alur/`.
* Uses SQLite for state tracking.


* **Implementation `AWSAdapter**`:
* Uses `s3://...`.
* Uses Glue Catalog.
* Uses DynamoDB for state tracking.



---

## **3. The CLI & User Workflow (`alur.cli`)**

This is how the user interacts with the library.

### **Command 1: `alur init <project_name>**`

* **Action:** Copies `src/alur/templates/project/` to the current directory.
* **Result:** Creates the user's `config/`, `contracts/`, `pipelines/` folders.

### **Command 2: `alur infra generate` (Deployment Logic)**

* **Action:** Reads `config/settings.py` (bucket names, region).
* **Logic:** Uses Jinja2 to fill in `src/alur/templates/terraform/`.
* **Output:** Generates a `terraform/` folder in the user's project containing:
* `s3.tf`: Buckets for Bronze/Silver/Gold.
* `glue.tf`: Glue Database definitions.
* `iam.tf`: Roles for the Glue Jobs/EMR.
* `dynamodb.tf`: State table for watermarks.


* **Why:** We prefer generating TF files so the user can audit/commit them to Git.

### **Command 3: `alur build**`

* **Action:**
1. Packages the user's current project into a Python Wheel (`.whl`).
2. Validates the DAG (Circular dependency check).



### **Command 4: `alur deploy**`

* **Action:**
1. Runs `alur build`.
2. Uploads the `.whl` to the S3 Artifacts Bucket.
3. (Optional) Updates AWS Glue Job definitions to point to the new Wheel file.



---

## **4. Deployment Architecture (AWS via Terraform)**

The AI Agent should generate Terraform templates that implement this architecture:

1. **Storage (S3):**
* `alur-bronze-{env}`
* `alur-silver-{env}`
* `alur-gold-{env}`
* `alur-artifacts-{env}` (Stores the Python code/wheels)


2. **Compute (AWS Glue / EMR Serverless):**
* **Main Job Wrapper:** A generic PySpark script (`driver.py`) provided by the Alur framework.
* **Execution:** The Glue Job accepts parameters: `--pipeline_name` and `--job_args`.
* **Logic:** The `driver.py` imports the user's package, finds the pipeline function by name, and executes it.


3. **Metadata (Glue Data Catalog):**
* Database: `alur_datalake_{env}`.
* Tables: Managed automatically by Iceberg/Alur.



---

## **5. Example User Experience (The "Readme" Code)**

Once the AI builds this library, the user should be able to do this:

```bash
# 1. Install
pip install alur-framework

# 2. Start
alur init my_lake
cd my_lake

# 3. Code (User edits contracts/silver.py etc.)

# 4. Local Test (Uses LocalAdapter)
alur run pipeline_clean_orders --local

# 5. Infrastructure Setup
alur infra generate
cd terraform && terraform apply

# 6. Deploy Code
alur deploy --env production

```

---

## **6. Task List for the AI Agent**

**Phase 1: The Core (Local)**

1. Implement `BaseTable` metaclass logic to parse fields.
2. Implement `LocalAdapter` to read/write Parquet locally.
3. Implement `@pipeline` registry logic.
4. Create `alur init` scaffolding.

**Phase 2: The Spark Engine**

1. Implement `alur.engine.spark` to handle Session creation.
2. Implement the logic for `SilverTable` MERGE (Iceberg upsert) in PySpark.

**Phase 3: The Source System**

1. Implement `PostgresSource` with JDBC reading logic.
2. Implement the Watermark/State logic in `LocalAdapter` (SQLite).

**Phase 4: AWS & Terraform**

1. Create `AWSAdapter` (Boto3 + Glue support).
2. Create the Jinja2 Terraform templates.
3. Implement `alur infra generate`.

**Phase 5: Packaging**

1. Create `pyproject.toml`.
2. Ensure `pip build` works.