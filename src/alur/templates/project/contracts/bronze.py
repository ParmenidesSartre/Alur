"""
Bronze layer table definitions.

Bronze tables store raw, unprocessed data in append-only mode.
Bronze philosophy: Raw data as-is + metadata. NO transformations.
"""

from alur.core import BronzeTable, StringField, IntegerField, TimestampField


class OrdersBronze(BronzeTable):
    """Raw orders data from source system."""

    # Source data fields (as-is from source)
    order_id = StringField(nullable=False, description="Unique order identifier")
    customer_id = StringField(nullable=False, description="Customer identifier")
    product_id = StringField(nullable=False, description="Product identifier")
    quantity = IntegerField(nullable=False, description="Order quantity")
    amount = IntegerField(nullable=False, description="Order amount in cents")
    status = StringField(nullable=True, description="Order status")
    created_at = TimestampField(nullable=False, description="Order creation timestamp")

    # Bronze metadata fields (added by ingestion helpers)
    _ingested_at = TimestampField(nullable=True, description="When data was ingested")
    _source_system = StringField(nullable=True, description="Source system name")
    _source_file = StringField(nullable=True, description="Original source file name")

    class Meta:
        partition_by = ["created_at"]
        description = "Raw orders data from source system"
