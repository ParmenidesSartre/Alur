# Local Testing Guide - Simple Start

Quick guide to use Alur locally without AWS for simple testing.

## Prerequisites

You already have everything installed! ✅
- Python 3.8+
- PySpark (installed earlier)
- Alur framework

## Quick Start - 5 Minutes

### 1. Create a Test Project

```bash
cd c:\Users\USER\Desktop
python -m alur.cli init my_test_lake
cd my_test_lake
```

### 2. Look at the Example Files

The project comes with example tables and a pipeline:

**contracts/bronze.py** - Raw data table definition
**contracts/silver.py** - Cleaned data table definition
**pipelines/orders.py** - Example transformation pipeline

### 3. Create Some Test Data

Create a simple script to generate test data:

**generate_data.py:**
```python
from pyspark.sql import SparkSession
from datetime import datetime

# Create Spark session
spark = SparkSession.builder \
    .appName("GenerateTestData") \
    .master("local[*]") \
    .config("spark.driver.memory", "2g") \
    .getOrCreate()

# Create sample orders data
data = [
    ("order_1", "cust_1", "prod_1", 2, 2000, "valid", datetime.now(), datetime.now()),
    ("order_2", "cust_2", "prod_2", 1, 1500, "valid", datetime.now(), datetime.now()),
    ("order_3", "cust_3", "prod_1", 3, 3000, "valid", datetime.now(), datetime.now()),
    ("order_4", "cust_1", "prod_3", 1, 1000, None, datetime.now(), datetime.now()),  # null status
    ("order_5", "cust_2", "prod_2", 5, 5000, "valid", datetime.now(), datetime.now()),
]

columns = ["order_id", "customer_id", "product_id", "quantity", "amount", "status", "created_at", "ingested_at"]

df = spark.createDataFrame(data, columns)

# Write to local bronze layer
output_path = "C:/tmp/alur/bronze/ordersbronze"
df.write.mode("overwrite").parquet(output_path)

print(f"[OK] Created {df.count()} test orders in {output_path}")
df.show()

spark.stop()
```

### 4. Run the Data Generator

```bash
python generate_data.py
```

Output:
```
[OK] Created 5 test orders in C:/tmp/alur/bronze/ordersbronze
```

### 5. Run the Pipeline Locally

**Option A: Using main.py**
```bash
python main.py
```

**Option B: Using the CLI**
```bash
python -m alur.cli run clean_orders --local
```

### 6. Check the Results

```python
# check_results.py
from pyspark.sql import SparkSession

spark = SparkSession.builder \
    .appName("CheckResults") \
    .master("local[*]") \
    .getOrCreate()

# Read silver data
silver_path = "C:/tmp/alur/silver/orderssilver"
df = spark.read.parquet(silver_path)

print(f"Found {df.count()} records in Silver layer")
df.show()

spark.stop()
```

Run it:
```bash
python check_results.py
```

## Simple Custom Example

Let's create a really simple example from scratch:

### Step 1: Define a Simple Table

**contracts/simple.py:**
```python
from alur.core import BronzeTable, SilverTable, StringField, IntegerField

class NumbersBronze(BronzeTable):
    """Simple bronze table with numbers."""
    id = StringField(nullable=False)
    value = IntegerField(nullable=False)

    class Meta:
        partition_by = []

class NumbersSilver(SilverTable):
    """Simple silver table - only even numbers."""
    id = StringField(nullable=False)
    value = IntegerField(nullable=False)
    is_even = StringField(nullable=False)

    class Meta:
        primary_key = ["id"]
```

### Step 2: Create a Simple Pipeline

**pipelines/simple.py:**
```python
from alur.decorators import pipeline
from contracts.simple import NumbersBronze, NumbersSilver
from pyspark.sql import functions as F

@pipeline(
    sources={"numbers": NumbersBronze},
    target=NumbersSilver
)
def process_numbers(numbers):
    """Keep only even numbers and add a flag."""
    return numbers.filter(F.col("value") % 2 == 0) \
                  .withColumn("is_even", F.lit("yes"))
```

### Step 3: Generate Test Data

**simple_data.py:**
```python
from pyspark.sql import SparkSession

spark = SparkSession.builder \
    .appName("SimpleData") \
    .master("local[*]") \
    .getOrCreate()

# Create numbers 1-10
data = [(f"num_{i}", i) for i in range(1, 11)]
df = spark.createDataFrame(data, ["id", "value"])

# Write to bronze
df.write.mode("overwrite").parquet("C:/tmp/alur/bronze/numbersbronze")

print(f"[OK] Created {df.count()} numbers")
df.show()

spark.stop()
```

### Step 4: Run It

```bash
# Create data
python simple_data.py

# Run pipeline
python -c "from alur.engine import LocalAdapter, PipelineRunner; import pipelines.simple; adapter = LocalAdapter(); runner = PipelineRunner(adapter); runner.run_pipeline('process_numbers')"

# Check results
python -c "from pyspark.sql import SparkSession; spark = SparkSession.builder.master('local[*]').getOrCreate(); df = spark.read.parquet('C:/tmp/alur/silver/numbersssilver'); df.show(); spark.stop()"
```

## Even Simpler: Pure Python Test

If you just want to test table definitions without Spark:

```python
# test_tables.py
from alur.core import BronzeTable, StringField, IntegerField

class MyTable(BronzeTable):
    id = StringField(nullable=False)
    count = IntegerField()

    class Meta:
        partition_by = ["id"]

# Test it
print("Table name:", MyTable.get_table_name())
print("Fields:", list(MyTable._fields.keys()))
print("Partitions:", MyTable.get_partition_by())
print("Schema:", MyTable.to_iceberg_schema())
```

Run:
```bash
python test_tables.py
```

Output:
```
Table name: mytable
Fields: ['id', 'count']
Partitions: ['id']
Schema: StructType([...])
```

## Common Local Tasks

### View Data
```python
from pyspark.sql import SparkSession

spark = SparkSession.builder.master("local[*]").getOrCreate()
df = spark.read.parquet("C:/tmp/alur/bronze/ordersbronze")
df.show()
spark.stop()
```

### Delete All Local Data
```bash
# Windows
rmdir /s /q C:\tmp\alur

# Or manually navigate and delete
```

### Validate Your Pipelines
```bash
python -m alur.cli validate
```

## What You Can Test Locally

✅ **Table Definitions** - Define schemas
✅ **Pipeline Logic** - Test transformations
✅ **DAG Validation** - Check dependencies
✅ **Simple Workflows** - End-to-end with small data

❌ **Not Local:**
- AWS S3 integration (needs AWS)
- Glue Catalog (needs AWS)
- Large-scale data processing

## Troubleshooting

**"Java not found"**
- Download Java 11: https://adoptium.net/
- Install and restart terminal

**"spark-warehouse directory errors"**
- Ignore them, they're just warnings

**"Permission denied on /tmp/alur"**
- Already using C:/tmp/alur for Windows

**"Module not found: pipelines"**
- Make sure you're in the project directory
- Try: `cd my_test_lake`

## Quick Reference

```bash
# Create project
python -m alur.cli init myproject
cd myproject

# Validate pipelines
python -m alur.cli validate

# Run locally (if main.py is set up)
python main.py

# Or run specific pipeline
python -m alur.cli run pipeline_name --local
```

## Tips for Local Development

1. **Start Small** - Test with 10-100 rows, not millions
2. **Use Parquet** - Faster than CSV for testing
3. **Check C:/tmp/alur/** - That's where data goes
4. **Validate First** - Run `alur validate` before executing
5. **Clean Often** - Delete C:/tmp/alur to start fresh

## Next Steps

Once you're comfortable locally:
1. Test your logic with small datasets
2. Validate transformations work correctly
3. Then deploy to AWS for production testing

**Local = Fast iteration and learning**
**AWS = Production-ready testing and deployment**

---

Happy local testing! 🚀
