from alur.batch_ingestion import validate_csv_bytes
from alur.core import BronzeTable, IntegerField, StringField, TimestampField
import unittest


class OrdersBronze(BronzeTable):
    order_id = StringField(nullable=False)
    quantity = IntegerField(nullable=False)
    created_at = TimestampField(nullable=False)

class TestCsvSchemaValidation(unittest.TestCase):
    def test_validate_csv_bytes_missing_required_column(self):
        csv_bytes = b"order_id,created_at\n1,2024-01-01T00:00:00\n"
        result = validate_csv_bytes(csv_bytes, OrdersBronze, sample_rows=10)
        self.assertFalse(result.ok)
        self.assertTrue(any("missing required columns" in e for e in result.errors))

    def test_validate_csv_bytes_rejects_bad_integer_value(self):
        csv_bytes = b"order_id,quantity,created_at\n1,not_an_int,2024-01-01T00:00:00\n"
        result = validate_csv_bytes(csv_bytes, OrdersBronze, sample_rows=10)
        self.assertFalse(result.ok)
        self.assertTrue(any("column 'quantity'" in e for e in result.errors))
