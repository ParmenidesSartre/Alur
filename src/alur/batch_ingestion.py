"""
Batch CSV ingestion utilities (bronze-only).

Scope:
- Read CSV from S3 (s3://bucket/prefix/*.csv)
- Validate CSV header + sample rows against a BronzeTable contract
- Write validated CSV bytes into a bronze S3 bucket
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple, Type

import csv
import fnmatch
import io
from urllib.parse import urlparse

import boto3

from alur.core.contracts import BronzeTable
from alur.core.fields import (
    BooleanField,
    DateField,
    DecimalField,
    DoubleField,
    Field,
    IntegerField,
    LongField,
    StringField,
    TimestampField,
)


class BatchSchemaError(ValueError):
    """Raised when a source CSV does not satisfy the contract schema."""


@dataclass(frozen=True)
class S3CsvSource:
    """
    A CSV source location in S3.

    uri supports wildcards like: s3://bucket/path/*.csv
    """

    uri: str
    source_system: Optional[str] = None

    @property
    def bucket(self) -> str:
        parsed = urlparse(self.uri)
        return parsed.netloc

    @property
    def key_pattern(self) -> str:
        parsed = urlparse(self.uri)
        return parsed.path.lstrip("/")


@dataclass(frozen=True)
class CsvValidationResult:
    ok: bool
    errors: Tuple[str, ...] = ()
    sampled_rows: int = 0
    header: Tuple[str, ...] = ()


@dataclass(frozen=True)
class IngestedObject:
    source_uri: str
    dest_uri: Optional[str]
    ok: bool
    error: Optional[str] = None


@dataclass(frozen=True)
class BatchIngestionReport:
    started_at_utc: str
    finished_at_utc: str
    attempted: int
    succeeded: int
    failed: int
    results: Tuple[IngestedObject, ...] = field(default_factory=tuple)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _require_csv_s3_uri(uri: str) -> None:
    uri_lower = uri.lower()
    if not uri_lower.startswith("s3://"):
        raise ValueError(f"Only s3:// URIs are supported: {uri}")
    if not (uri_lower.endswith(".csv") or "*.csv" in uri_lower):
        raise ValueError(f"Only CSV URIs are supported: {uri}")


def _iter_s3_objects_matching(
    s3_client,
    bucket: str,
    key_pattern: str,
) -> Iterable[Dict[str, Any]]:
    search_prefix = key_pattern.split("*", 1)[0] if "*" in key_pattern else key_pattern
    paginator = s3_client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=search_prefix):
        for obj in page.get("Contents", []) or []:
            key = obj.get("Key", "")
            if not key or key.endswith("/"):
                continue
            if not fnmatch.fnmatch(key, key_pattern):
                continue
            if not key.lower().endswith(".csv"):
                continue
            yield obj


def _expected_contract_fields(contract: Type[BronzeTable]) -> Dict[str, Field]:
    fields = contract.get_fields()
    return {name: field for name, field in fields.items() if not name.startswith("_")}


def _parse_bool(value: str) -> bool:
    v = value.strip().lower()
    if v in {"true", "t", "1", "yes", "y"}:
        return True
    if v in {"false", "f", "0", "no", "n"}:
        return False
    raise ValueError(f"Invalid boolean: {value!r}")


def _parse_timestamp(value: str):
    v = value.strip()
    if v.endswith("Z"):
        v = v[:-1] + "+00:00"
    return datetime.fromisoformat(v)


def _parse_date(value: str):
    from datetime import date

    return date.fromisoformat(value.strip())


def _validate_value(field: Field, raw: str) -> None:
    if raw is None:
        raw = ""
    value = raw.strip()
    if value == "":
        if field.nullable:
            return
        raise ValueError("value is required")

    if isinstance(field, (StringField,)):
        return
    if isinstance(field, (IntegerField, LongField)):
        int(value)
        return
    if isinstance(field, (DoubleField,)):
        float(value)
        return
    if isinstance(field, (BooleanField,)):
        _parse_bool(value)
        return
    if isinstance(field, (TimestampField,)):
        _parse_timestamp(value)
        return
    if isinstance(field, (DateField,)):
        _parse_date(value)
        return
    if isinstance(field, (DecimalField,)):
        from decimal import Decimal

        Decimal(value)
        return

    # For complex/nested fields, do not enforce row-level parsing in batch-only mode.
    return


def validate_csv_bytes(
    csv_bytes: bytes,
    contract: Type[BronzeTable],
    *,
    sample_rows: int = 50,
    encoding: str = "utf-8",
    delimiter: str = ",",
) -> CsvValidationResult:
    expected = _expected_contract_fields(contract)
    required_columns = {name for name, field in expected.items() if not field.nullable}

    errors: List[str] = []
    text = csv_bytes.decode(encoding, errors="replace")
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)

    if reader.fieldnames is None:
        return CsvValidationResult(ok=False, errors=("missing header row",), sampled_rows=0, header=())

    header = tuple(reader.fieldnames)
    header_set = set(reader.fieldnames)

    missing = sorted(required_columns - header_set)
    if missing:
        errors.append(f"missing required columns: {missing}")

    # Validate sample rows (type + required non-empty)
    sampled = 0
    if not errors:
        for row in reader:
            sampled += 1
            for col, field in expected.items():
                if col not in row:
                    continue
                try:
                    _validate_value(field, row.get(col, ""))
                except Exception as e:  # noqa: BLE001
                    errors.append(f"row {sampled}: column '{col}': {str(e)}")
                    break
            if errors or sampled >= sample_rows:
                break

    return CsvValidationResult(
        ok=(len(errors) == 0),
        errors=tuple(errors),
        sampled_rows=sampled,
        header=header,
    )


def ingest_csv_sources_to_bronze(
    sources: Sequence[S3CsvSource],
    *,
    contract: Type[BronzeTable],
    bronze_bucket: str,
    dest_prefix: Optional[str] = None,
    s3_client=None,
    on_error: str = "skip",  # "skip" | "raise"
    sample_rows: int = 50,
) -> BatchIngestionReport:
    """
    Batch ingest CSVs from one or more S3 sources to a bronze S3 bucket.

    Writes the raw CSV bytes (after validation) to:
      s3://{bronze_bucket}/{dest_prefix}{table_name}/{source_bucket}/{source_key}
    """
    started_at = _utc_now_iso()
    s3_client = s3_client or boto3.client("s3")

    table_name = contract.get_table_name()
    dest_prefix = "" if dest_prefix is None else dest_prefix.strip("/")
    dest_prefix = (dest_prefix + "/") if dest_prefix else ""

    results: List[IngestedObject] = []
    attempted = 0
    succeeded = 0

    for src in sources:
        _require_csv_s3_uri(src.uri)

        bucket = src.bucket
        key_pattern = src.key_pattern

        for obj in _iter_s3_objects_matching(s3_client, bucket=bucket, key_pattern=key_pattern):
            key = obj["Key"]
            attempted += 1
            source_uri = f"s3://{bucket}/{key}"

            try:
                resp = s3_client.get_object(Bucket=bucket, Key=key)
                body = resp["Body"].read()

                validation = validate_csv_bytes(body, contract, sample_rows=sample_rows)
                if not validation.ok:
                    raise BatchSchemaError("; ".join(validation.errors))

                dest_key = f"{dest_prefix}{table_name}/{bucket}/{key}"
                s3_client.put_object(
                    Bucket=bronze_bucket,
                    Key=dest_key,
                    Body=body,
                    ContentType="text/csv",
                    Metadata={
                        "alur_source_bucket": bucket,
                        "alur_source_key": key,
                        "alur_table": table_name,
                        **({"alur_source_system": src.source_system} if src.source_system else {}),
                    },
                )

                succeeded += 1
                results.append(
                    IngestedObject(
                        source_uri=source_uri,
                        dest_uri=f"s3://{bronze_bucket}/{dest_key}",
                        ok=True,
                    )
                )
            except Exception as e:  # noqa: BLE001
                results.append(
                    IngestedObject(
                        source_uri=source_uri,
                        dest_uri=None,
                        ok=False,
                        error=str(e),
                    )
                )
                if on_error == "raise":
                    finished_at = _utc_now_iso()
                    failed = attempted - succeeded
                    raise BatchSchemaError(
                        f"Ingestion failed for {source_uri}: {str(e)}"
                    ) from e

    finished_at = _utc_now_iso()
    failed = attempted - succeeded
    return BatchIngestionReport(
        started_at_utc=started_at,
        finished_at_utc=finished_at,
        attempted=attempted,
        succeeded=succeeded,
        failed=failed,
        results=tuple(results),
    )
