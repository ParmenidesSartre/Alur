"""
AWS utility helpers for S3, Boto3 client management, and common operations.
Centralizes AWS-related utilities to avoid code duplication across the codebase.
"""

from typing import Optional, Dict, Any
from urllib.parse import urlparse
from dataclasses import dataclass
import boto3
import logging

logger = logging.getLogger(__name__)


@dataclass
class S3Path:
    """
    Parsed S3 path with structured access to bucket and key components.

    Usage:
        path = S3Path.from_uri("s3://my-bucket/path/to/file.csv")
        print(path.bucket)  # "my-bucket"
        print(path.key)     # "path/to/file.csv"
        print(path.uri)     # "s3://my-bucket/path/to/file.csv"
    """

    bucket: str
    key: str

    @classmethod
    def from_uri(cls, s3_uri: str) -> 'S3Path':
        """
        Parse an S3 URI into bucket and key components.

        Args:
            s3_uri: S3 URI in format s3://bucket/key

        Returns:
            S3Path instance with parsed components

        Raises:
            ValueError: If URI is not a valid S3 path
        """
        if not s3_uri.startswith('s3://'):
            raise ValueError(f"Invalid S3 URI (must start with s3://): {s3_uri}")

        parsed = urlparse(s3_uri)
        bucket = parsed.netloc
        key = parsed.path.lstrip('/')

        if not bucket:
            raise ValueError(f"S3 URI missing bucket: {s3_uri}")

        return cls(bucket=bucket, key=key)

    @property
    def uri(self) -> str:
        """Get the full S3 URI."""
        return f"s3://{self.bucket}/{self.key}"

    @property
    def key_prefix(self) -> str:
        """
        Get key prefix for wildcard patterns.
        For "path/to/*.csv", returns "path/to/".
        """
        if '*' in self.key:
            return self.key.split('*')[0]
        return self.key

    def __str__(self) -> str:
        return self.uri


class AWSClientFactory:
    """
    Centralized factory for creating and caching AWS boto3 clients.

    Avoids creating multiple clients for the same service and region.
    Thread-safe for single-process usage (not multiprocess).
    """

    _clients: Dict[str, Any] = {}

    @classmethod
    def get_s3_client(cls, region: Optional[str] = None) -> Any:
        """
        Get or create an S3 client.

        Args:
            region: AWS region (optional, uses default if not specified)

        Returns:
            Boto3 S3 client
        """
        key = f"s3:{region or 'default'}"

        if key not in cls._clients:
            if region:
                cls._clients[key] = boto3.client('s3', region_name=region)
            else:
                # S3 client doesn't require region - it auto-detects from bucket
                cls._clients[key] = boto3.client('s3')
            logger.debug(f"Created new S3 client: {key}")

        return cls._clients[key]

    @classmethod
    def get_glue_client(cls, region: str) -> Any:
        """
        Get or create a Glue client.

        Args:
            region: AWS region

        Returns:
            Boto3 Glue client
        """
        key = f"glue:{region}"

        if key not in cls._clients:
            cls._clients[key] = boto3.client('glue', region_name=region)
            logger.debug(f"Created new Glue client: {key}")

        return cls._clients[key]

    @classmethod
    def get_secrets_client(cls, region: Optional[str] = None) -> Any:
        """
        Get or create a Secrets Manager client.

        Args:
            region: AWS region (optional, uses default if not specified)

        Returns:
            Boto3 Secrets Manager client
        """
        key = f"secretsmanager:{region or 'default'}"

        if key not in cls._clients:
            if region:
                cls._clients[key] = boto3.client('secretsmanager', region_name=region)
            else:
                cls._clients[key] = boto3.client('secretsmanager')
            logger.debug(f"Created new Secrets Manager client: {key}")

        return cls._clients[key]

    @classmethod
    def clear(cls) -> None:
        """Clear all cached clients (useful for testing)."""
        cls._clients.clear()
        logger.debug("Cleared all AWS clients from cache")


__all__ = [
    "S3Path",
    "AWSClientFactory",
]
