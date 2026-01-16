"""
Silver layer table definitions.
Silver tables store cleaned, deduplicated data with ACID guarantees.
"""

from alur.core import SilverTable, StringField, IntegerField, TimestampField


class OrdersSilver(SilverTable):
    """Cleaned and deduplicated orders data."""

    order_id = StringField(nullable=False, description="Unique order identifier")
    customer_id = StringField(nullable=False, description="Customer identifier")
    product_id = StringField(nullable=False, description="Product identifier")
    quantity = IntegerField(nullable=False, description="Order quantity")
    amount = IntegerField(nullable=False, description="Order amount in cents")
    status = StringField(nullable=False, description="Order status")
    created_at = TimestampField(nullable=False, description="Order creation timestamp")
    updated_at = TimestampField(nullable=False, description="Last update timestamp")

    class Meta:
        primary_key = ["order_id"]
        partition_by = ["created_at"]
        description = "Cleaned and deduplicated orders"
