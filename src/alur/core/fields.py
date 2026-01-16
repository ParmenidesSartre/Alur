"""
Field definitions for Alur table schemas.
These fields map to Spark SQL data types.
"""

from typing import Any, Optional
from pyspark.sql.types import (
    StringType,
    IntegerType,
    LongType,
    DoubleType,
    BooleanType,
    TimestampType,
    DateType,
    DecimalType,
    ArrayType,
    StructType,
    StructField as SparkStructField,
)


class Field:
    """Base field class for all data types."""

    def __init__(self, nullable: bool = True, description: Optional[str] = None):
        self.nullable = nullable
        self.description = description
        self.name: Optional[str] = None  # Set by the metaclass

    def to_spark_type(self):
        """Convert this field to a Spark DataType."""
        raise NotImplementedError("Subclasses must implement to_spark_type()")

    def to_spark_field(self) -> SparkStructField:
        """Convert this field to a Spark StructField."""
        if self.name is None:
            raise ValueError("Field name has not been set")
        return SparkStructField(
            name=self.name,
            dataType=self.to_spark_type(),
            nullable=self.nullable,
            metadata={"description": self.description} if self.description else {}
        )


class StringField(Field):
    """String/Text field."""

    def to_spark_type(self):
        return StringType()


class IntegerField(Field):
    """32-bit integer field."""

    def to_spark_type(self):
        return IntegerType()


class LongField(Field):
    """64-bit long integer field."""

    def to_spark_type(self):
        return LongType()


class DoubleField(Field):
    """Double precision float field."""

    def to_spark_type(self):
        return DoubleType()


class BooleanField(Field):
    """Boolean field."""

    def to_spark_type(self):
        return BooleanType()


class TimestampField(Field):
    """Timestamp field with timezone."""

    def to_spark_type(self):
        return TimestampType()


class DateField(Field):
    """Date field (without time)."""

    def to_spark_type(self):
        return DateType()


class DecimalField(Field):
    """Decimal field with precision and scale."""

    def __init__(self, precision: int = 10, scale: int = 0, nullable: bool = True,
                 description: Optional[str] = None):
        super().__init__(nullable=nullable, description=description)
        self.precision = precision
        self.scale = scale

    def to_spark_type(self):
        return DecimalType(precision=self.precision, scale=self.scale)


class ArrayField(Field):
    """Array field containing elements of a specific type."""

    def __init__(self, element_field: Field, nullable: bool = True,
                 description: Optional[str] = None):
        super().__init__(nullable=nullable, description=description)
        self.element_field = element_field

    def to_spark_type(self):
        return ArrayType(
            elementType=self.element_field.to_spark_type(),
            containsNull=self.element_field.nullable
        )


class StructField(Field):
    """Nested struct field."""

    def __init__(self, fields: dict[str, Field], nullable: bool = True,
                 description: Optional[str] = None):
        super().__init__(nullable=nullable, description=description)
        self.fields = fields
        # Set the name for nested fields
        for name, field in self.fields.items():
            field.name = name

    def to_spark_type(self):
        spark_fields = [field.to_spark_field() for field in self.fields.values()]
        return StructType(spark_fields)


__all__ = [
    "Field",
    "StringField",
    "IntegerField",
    "LongField",
    "DoubleField",
    "BooleanField",
    "TimestampField",
    "DateField",
    "DecimalField",
    "ArrayField",
    "StructField",
]
