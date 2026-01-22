import io

import boto3
from botocore.response import StreamingBody
from botocore.stub import Stubber
import unittest

from alur.batch_ingestion import S3CsvSource, ingest_csv_sources_to_bronze
from alur.core import BronzeTable, IntegerField, StringField, TimestampField


class OrdersBronze(BronzeTable):
    order_id = StringField(nullable=False)
    quantity = IntegerField(nullable=False)
    created_at = TimestampField(nullable=False)

class TestBatchIngestionIntegration(unittest.TestCase):
    def test_ingest_csv_sources_to_bronze_s3_stubbed_skips_bad_files(self):
        s3 = boto3.client("s3", region_name="us-east-1")
        stubber = Stubber(s3)

        source_bucket = "source-a"
        bronze_bucket = "alur-bronze-dev"

        good_key = "incoming/good.csv"
        bad_key = "incoming/bad.csv"

        good_csv = b"order_id,quantity,created_at\n1,2,2024-01-01T00:00:00\n"
        bad_csv = b"order_id,created_at\n1,2024-01-01T00:00:00\n"

        stubber.add_response(
            "list_objects_v2",
            {
                "IsTruncated": False,
                "Contents": [
                    {"Key": good_key, "Size": len(good_csv)},
                    {"Key": bad_key, "Size": len(bad_csv)},
                ],
            },
            {"Bucket": source_bucket, "Prefix": "incoming/"},
        )

        stubber.add_response(
            "get_object",
            {"Body": StreamingBody(io.BytesIO(good_csv), len(good_csv))},
            {"Bucket": source_bucket, "Key": good_key},
        )

        stubber.add_response(
            "put_object",
            {"ETag": '"etag"'},
            {
                "Bucket": bronze_bucket,
                "Key": f"orders/{source_bucket}/{good_key}",
                "Body": good_csv,
                "ContentType": "text/csv",
                "Metadata": {
                    "alur_source_bucket": source_bucket,
                    "alur_source_key": good_key,
                    "alur_table": "orders",
                },
            },
        )

        stubber.add_response(
            "get_object",
            {"Body": StreamingBody(io.BytesIO(bad_csv), len(bad_csv))},
            {"Bucket": source_bucket, "Key": bad_key},
        )

        with stubber:
            report = ingest_csv_sources_to_bronze(
                [S3CsvSource(f"s3://{source_bucket}/incoming/*.csv")],
                contract=OrdersBronze,
                bronze_bucket=bronze_bucket,
                s3_client=s3,
                on_error="skip",
                sample_rows=10,
            )

        self.assertEqual(report.attempted, 2)
        self.assertEqual(report.succeeded, 1)
        self.assertEqual(report.failed, 1)
        self.assertTrue(
            any(
                r.ok
                and r.dest_uri
                == f"s3://{bronze_bucket}/orders/{source_bucket}/{good_key}"
                for r in report.results
            )
        )
        self.assertTrue(
            any((not r.ok) and r.source_uri.endswith(bad_key) for r in report.results)
        )

    def test_ingest_supports_multiple_source_buckets(self):
        s3 = boto3.client("s3", region_name="us-east-1")
        stubber = Stubber(s3)

        bronze_bucket = "alur-bronze-dev"

        src_a = "source-a"
        key_a = "incoming/a.csv"
        csv_a = b"order_id,quantity,created_at\n1,1,2024-01-01T00:00:00\n"

        src_b = "source-b"
        key_b = "incoming/b.csv"
        csv_b = b"order_id,quantity,created_at\n2,2,2024-01-01T00:00:00\n"

        stubber.add_response(
            "list_objects_v2",
            {"IsTruncated": False, "Contents": [{"Key": key_a, "Size": len(csv_a)}]},
            {"Bucket": src_a, "Prefix": "incoming/"},
        )
        stubber.add_response(
            "get_object",
            {"Body": StreamingBody(io.BytesIO(csv_a), len(csv_a))},
            {"Bucket": src_a, "Key": key_a},
        )
        stubber.add_response(
            "put_object",
            {"ETag": '"etag-a"'},
            {
                "Bucket": bronze_bucket,
                "Key": f"orders/{src_a}/{key_a}",
                "Body": csv_a,
                "ContentType": "text/csv",
                "Metadata": {
                    "alur_source_bucket": src_a,
                    "alur_source_key": key_a,
                    "alur_table": "orders",
                },
            },
        )

        stubber.add_response(
            "list_objects_v2",
            {"IsTruncated": False, "Contents": [{"Key": key_b, "Size": len(csv_b)}]},
            {"Bucket": src_b, "Prefix": "incoming/"},
        )
        stubber.add_response(
            "get_object",
            {"Body": StreamingBody(io.BytesIO(csv_b), len(csv_b))},
            {"Bucket": src_b, "Key": key_b},
        )
        stubber.add_response(
            "put_object",
            {"ETag": '"etag-b"'},
            {
                "Bucket": bronze_bucket,
                "Key": f"orders/{src_b}/{key_b}",
                "Body": csv_b,
                "ContentType": "text/csv",
                "Metadata": {
                    "alur_source_bucket": src_b,
                    "alur_source_key": key_b,
                    "alur_table": "orders",
                },
            },
        )

        with stubber:
            report = ingest_csv_sources_to_bronze(
                [
                    S3CsvSource(f"s3://{src_a}/incoming/*.csv"),
                    S3CsvSource(f"s3://{src_b}/incoming/*.csv"),
                ],
                contract=OrdersBronze,
                bronze_bucket=bronze_bucket,
                s3_client=s3,
                on_error="raise",
                sample_rows=10,
            )

        self.assertEqual(report.attempted, 2)
        self.assertEqual(report.succeeded, 2)
        self.assertEqual(report.failed, 0)
