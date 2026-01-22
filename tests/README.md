# Tests

Run all tests:

`python -m tests`

Run only the integration test (stubbed S3 via `botocore.stub.Stubber`):

`python -m unittest tests.test_batch_ingestion_integration`

Run real AWS end-to-end test (writes to S3; requires credentials and buckets):

```
$env:ALUR_AWS_E2E="1"
$env:ALUR_AWS_REGION="ap-southeast-5"
# Optional: prefix for auto-created test buckets
# $env:ALUR_AWS_E2E_PREFIX="alur-e2e"
python -m unittest -v tests.test_aws_end_to_end_bronze
```
