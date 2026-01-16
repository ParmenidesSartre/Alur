"""
Table contract definitions using metaclass pattern.
Defines BaseTable, BronzeTable, and SilverTable classes.
"""

from typing import Dict, List, Optional, Type, Any
from pyspark.sql.types import StructType
from .fields import Field


class TableMeta:
    """Metadata container for table configuration."""

    def __init__(self):
        self.partition_by: List[str] = []
        self.primary_key: Optional[List[str]] = None
        self.description: Optional[str] = None
        self.bucket: Optional[str] = None
        self.layer: Optional[str] = None


class BaseTableMeta(type):
    """Metaclass for BaseTable that processes field definitions."""

    def __new__(mcs, name, bases, namespace, **kwargs):
        # Skip processing for BaseTable itself
        if name == "BaseTable":
            return super().__new__(mcs, name, bases, namespace)

        # Extract fields from class definition
        fields: Dict[str, Field] = {}
        for attr_name, attr_value in list(namespace.items()):
            if isinstance(attr_value, Field):
                attr_value.name = attr_name
                fields[attr_name] = attr_value

        # Store fields in the class
        namespace["_fields"] = fields

        # Process Meta inner class if it exists
        meta = namespace.get("Meta", None)
        table_meta = TableMeta()

        if meta:
            table_meta.partition_by = getattr(meta, "partition_by", [])
            table_meta.primary_key = getattr(meta, "primary_key", None)
            table_meta.description = getattr(meta, "description", None)
            table_meta.bucket = getattr(meta, "bucket", None)

        namespace["_meta"] = table_meta
        namespace["_table_name"] = name.lower()

        return super().__new__(mcs, name, bases, namespace)


class BaseTable(metaclass=BaseTableMeta):
    """Base class for all table definitions."""

    _fields: Dict[str, Field] = {}
    _meta: TableMeta = TableMeta()
    _table_name: str = ""

    class Meta:
        """Override this in subclasses to provide table metadata."""
        partition_by: List[str] = []
        primary_key: Optional[List[str]] = None
        description: Optional[str] = None
        bucket: Optional[str] = None

    @classmethod
    def to_iceberg_schema(cls) -> StructType:
        """
        Convert the table definition to a Spark StructType schema.

        Returns:
            StructType: The Spark schema for this table
        """
        spark_fields = [field.to_spark_field() for field in cls._fields.values()]
        return StructType(spark_fields)

    @classmethod
    def get_table_name(cls) -> str:
        """Get the table name."""
        return cls._table_name

    @classmethod
    def get_fields(cls) -> Dict[str, Field]:
        """Get all fields defined for this table."""
        return cls._fields

    @classmethod
    def get_partition_by(cls) -> List[str]:
        """Get the partition columns for this table."""
        return cls._meta.partition_by

    @classmethod
    def get_primary_key(cls) -> Optional[List[str]]:
        """Get the primary key columns for this table."""
        return cls._meta.primary_key

    @classmethod
    def get_s3_path(cls, bucket: Optional[str] = None, layer: Optional[str] = None) -> str:
        """
        Generate the S3 path for this table.

        Args:
            bucket: Override bucket name (otherwise uses Meta.bucket)
            layer: Override layer name (e.g., 'bronze', 'silver', 'gold')

        Returns:
            str: S3 path in format s3://{bucket}/{layer}/{table_name}
        """
        bucket = bucket or cls._meta.bucket or "alur-datalake"

        # Infer layer from class type if not provided
        if layer is None:
            if isinstance(cls, type) and issubclass(cls, BronzeTable):
                layer = "bronze"
            elif isinstance(cls, type) and issubclass(cls, SilverTable):
                layer = "silver"
            elif isinstance(cls, type) and issubclass(cls, GoldTable):
                layer = "gold"
            else:
                layer = "unknown"

        return f"s3://{bucket}/{layer}/{cls._table_name}"

    @classmethod
    def get_local_path(cls, base_path: str = "/tmp/alur", layer: Optional[str] = None) -> str:
        """
        Generate the local filesystem path for this table.

        Args:
            base_path: Base directory for local storage
            layer: Override layer name

        Returns:
            str: Local path in format {base_path}/{layer}/{table_name}
        """
        # Infer layer from class type if not provided
        if layer is None:
            if isinstance(cls, type) and issubclass(cls, BronzeTable):
                layer = "bronze"
            elif isinstance(cls, type) and issubclass(cls, SilverTable):
                layer = "silver"
            elif isinstance(cls, type) and issubclass(cls, GoldTable):
                layer = "gold"
            else:
                layer = "unknown"

        return f"{base_path}/{layer}/{cls._table_name}"


class BronzeTable(BaseTable):
    """
    Bronze layer table (raw data, append-only).
    - Format: Parquet
    - Write mode: Append
    """

    _format = "parquet"
    _write_mode = "append"

    @classmethod
    def get_format(cls) -> str:
        """Get the storage format for Bronze tables."""
        return cls._format

    @classmethod
    def get_write_mode(cls) -> str:
        """Get the write mode for Bronze tables."""
        return cls._write_mode


class SilverTable(BaseTable):
    """
    Silver layer table (cleaned, deduplicated data).
    - Format: Parquet
    - Write mode: Merge (Upsert)
    - Requires: primary_key in Meta
    """

    _format = "parquet"
    _write_mode = "merge"

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        # Validate that primary_key is defined
        if hasattr(cls, "_meta") and cls._meta.primary_key is None:
            raise ValueError(
                f"SilverTable '{cls.__name__}' must define 'primary_key' in its Meta class"
            )

    @classmethod
    def get_format(cls) -> str:
        """Get the storage format for Silver tables."""
        return cls._format

    @classmethod
    def get_write_mode(cls) -> str:
        """Get the write mode for Silver tables."""
        return cls._write_mode


class GoldTable(BaseTable):
    """
    Gold layer table (business-level aggregates).
    - Format: Parquet (can be configured to Iceberg when available)
    - Write mode: Overwrite or Merge (configurable)
    """

    _format = "parquet"
    _write_mode = "overwrite"

    @classmethod
    def get_format(cls) -> str:
        """Get the storage format for Gold tables."""
        return cls._format

    @classmethod
    def get_write_mode(cls) -> str:
        """Get the write mode for Gold tables."""
        return cls._write_mode


__all__ = [
    "BaseTable",
    "BronzeTable",
    "SilverTable",
    "GoldTable",
    "TableMeta",
]
