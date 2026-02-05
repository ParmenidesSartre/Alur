"""
Silver layer table definitions.

Silver tables store cleaned, validated, deduplicated data with ACID guarantees.
Silver philosophy: Clean data + business rules + deduplication.
"""

from alur.core import SilverTable, StringField, IntegerField, TimestampField


class OrdersSilver(SilverTable):
    """Cleaned and validated orders."""

    # Business fields (cleaned from bronze)
    order_id = StringField(nullable=False, description="Unique order identifier")
    customer_id = StringField(nullable=False, description="Customer identifier")
    product_id = StringField(nullable=False, description="Product identifier")
    quantity = IntegerField(nullable=False, description="Order quantity")
    amount = IntegerField(nullable=False, description="Order amount in cents")
    status = StringField(nullable=False, description="Order status (cleaned)")
    created_at = TimestampField(nullable=False, description="Order creation timestamp")

    # Silver metadata (added by transformation helpers)
    _transformed_at = TimestampField(nullable=True, description="When transformation ran")
    _source_bronze_table = StringField(nullable=True, description="Source bronze table")
    _transformation_name = StringField(nullable=True, description="Transformation pipeline")

    class Meta:
        primary_key = ["order_id"]  # Required for merge/upsert
        partition_by = ["created_at"]
        description = "Cleaned and validated orders (deduplicated)"
