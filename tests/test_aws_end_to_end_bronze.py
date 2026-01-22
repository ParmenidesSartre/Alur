import os
import unittest
from uuid import uuid4

import boto3
from botocore.exceptions import ClientError

from alur.batch_ingestion import S3CsvSource, ingest_csv_sources_to_bronze
from alur.core import BronzeTable, IntegerField, StringField, TimestampField


class OrdersBronze(BronzeTable):
    order_id = StringField(nullable=False)
    quantity = IntegerField(nullable=False)
    created_at = TimestampField(nullable=False)


DEFAULT_REGION = "ap-southeast-5"


def _optional_env(name: str) -> str:
    return os.getenv(name, "").strip()


def _create_bucket_if_needed(s3, bucket: str, region: str) -> None:
    try:
        s3.head_bucket(Bucket=bucket)
        return
    except ClientError:
        pass

    params = {"Bucket": bucket}
    if region != "us-east-1":
        params["CreateBucketConfiguration"] = {"LocationConstraint": region}
    s3.create_bucket(**params)


def _unique_bucket_name(prefix: str, run_id: str) -> str:
    # Keep short to satisfy S3 limits; ensure globally unique enough for tests.
    return f"{prefix}-{run_id[:12]}".lower()


def _s3_uri(bucket: str, key: str) -> str:
    return f"s3://{bucket}/{key}"


class TestAwsEndToEndBronze(unittest.TestCase):
    """
    Real AWS end-to-end test (writes to S3).

    It will:
    - Upload 1 good + 1 bad CSV into each source bucket under a unique prefix
    - Run ingestion (CSV -> schema check -> write to bronze bucket)
    - Verify bronze objects exist only for the good CSVs
    - Clean up uploaded test objects (best-effort)

    Enable by setting:
      ALUR_AWS_E2E=1
      (Optional) ALUR_AWS_REGION=ap-southeast-5
      (Optional) ALUR_AWS_E2E_PREFIX=my-s3-bucket-prefix
    """

    @classmethod
    def setUpClass(cls):
        if os.getenv("ALUR_AWS_E2E", "").strip() != "1":
            raise unittest.SkipTest("Set ALUR_AWS_E2E=1 to run real AWS end-to-end test")

        cls.region = _optional_env("ALUR_AWS_REGION") or DEFAULT_REGION
        cls.s3 = boto3.client("s3", region_name=cls.region)

        cls.run_id = uuid4().hex
        cls.prefix = f"alur-tests/e2e/{cls.run_id}/"

        bucket_prefix = _optional_env("ALUR_AWS_E2E_PREFIX") or "alur-e2e"

        cls.source_buckets = [
            _unique_bucket_name(f"{bucket_prefix}-source-a", cls.run_id),
            _unique_bucket_name(f"{bucket_prefix}-source-b", cls.run_id),
        ]
        cls.bronze_bucket = _unique_bucket_name(f"{bucket_prefix}-bronze", cls.run_id)

        # Create buckets
        _create_bucket_if_needed(cls.s3, cls.bronze_bucket, cls.region)
        for bucket in cls.source_buckets:
            _create_bucket_if_needed(cls.s3, bucket, cls.region)

        cls.created_objects = []  # list[(bucket,key)]

        cls.good_csv = b"order_id,quantity,created_at\n1,2,2024-01-01T00:00:00Z\n"
        cls.bad_csv = b"order_id,created_at\n1,2024-01-01T00:00:00Z\n"

        # Upload fixtures to each source bucket
        for bucket in cls.source_buckets:
            good_key = f"{cls.prefix}{bucket}/good.csv"
            bad_key = f"{cls.prefix}{bucket}/bad.csv"
            cls.s3.put_object(Bucket=bucket, Key=good_key, Body=cls.good_csv, ContentType="text/csv")
            cls.s3.put_object(Bucket=bucket, Key=bad_key, Body=cls.bad_csv, ContentType="text/csv")
            cls.created_objects.append((bucket, good_key))
            cls.created_objects.append((bucket, bad_key))

    @classmethod
    def tearDownClass(cls):
        if not hasattr(cls, "s3"):
            return

        # Best-effort cleanup for both source + bronze buckets
        for bucket, key in getattr(cls, "created_objects", []):
            try:
                cls.s3.delete_object(Bucket=bucket, Key=key)
            except Exception:
                pass

        # Delete bronze objects written by this test (best-effort)
        for bucket in getattr(cls, "source_buckets", []):
            good_key = f"orders/{bucket}/{cls.prefix}{bucket}/good.csv"
            try:
                cls.s3.delete_object(Bucket=cls.bronze_bucket, Key=good_key)
            except Exception:
                pass

        # Best-effort delete buckets (must be empty)
        for bucket in getattr(cls, "source_buckets", []):
            try:
                cls.s3.delete_bucket(Bucket=bucket)
            except Exception:
                pass
        try:
            cls.s3.delete_bucket(Bucket=cls.bronze_bucket)
        except Exception:
            pass

    def test_end_to_end_ingests_good_and_skips_bad(self):
        sources = [
            S3CsvSource(_s3_uri(bucket, f"{self.prefix}{bucket}/*.csv"))
            for bucket in self.source_buckets
        ]

        report = ingest_csv_sources_to_bronze(
            sources,
            contract=OrdersBronze,
            bronze_bucket=self.bronze_bucket,
            dest_prefix="",  # keep deterministic pathing
            s3_client=self.s3,
            on_error="skip",
            sample_rows=25,
        )

        # 2 files per bucket (good+bad)
        self.assertEqual(report.attempted, 2 * len(self.source_buckets))
        self.assertEqual(report.succeeded, 1 * len(self.source_buckets))
        self.assertEqual(report.failed, 1 * len(self.source_buckets))

        # Verify bronze has only the good files
        for bucket in self.source_buckets:
            dest_key = f"orders/{bucket}/{self.prefix}{bucket}/good.csv"
            dest_uri = _s3_uri(self.bronze_bucket, dest_key)

            obj = self.s3.get_object(Bucket=self.bronze_bucket, Key=dest_key)
            body = obj["Body"].read()
            self.assertEqual(body, self.good_csv)

            # Bad file should not exist
            bad_dest_key = f"orders/{bucket}/{self.prefix}{bucket}/bad.csv"
            try:
                self.s3.head_object(Bucket=self.bronze_bucket, Key=bad_dest_key)
                self.fail(f"Bad file should not have been written: {_s3_uri(self.bronze_bucket, bad_dest_key)}")
            except ClientError as e:
                code = e.response.get("Error", {}).get("Code", "")
                self.assertIn(code, {"404", "NoSuchKey", "NotFound"})
