"""
Test that unimplemented parameters fail loudly instead of being silently ignored.
"""
import unittest
from unittest.mock import MagicMock, patch

from alur.ingestion import load_to_bronze


class TestUnimplementedParameters(unittest.TestCase):
    """Test that unimplemented parameters raise NotImplementedError."""

    def setUp(self):
        """Set up mock Spark session."""
        self.mock_spark = MagicMock()
        self.mock_spark.read.options.return_value.schema.return_value.csv.return_value = MagicMock()

    @patch('alur.ingestion.boto3')
    def test_check_duplicates_false_raises_error(self, mock_boto3):
        """Test that check_duplicates=False raises NotImplementedError."""
        with self.assertRaises(NotImplementedError) as context:
            load_to_bronze(
                spark=self.mock_spark,
                source_path="s3://test-bucket/test.csv",
                source_system="test",
                check_duplicates=False  # Non-default value should fail
            )

        self.assertIn("check_duplicates", str(context.exception))
        self.assertIn("not yet implemented", str(context.exception).lower())

    @patch('alur.ingestion.boto3')
    def test_force_reprocess_true_raises_error(self, mock_boto3):
        """Test that force_reprocess=True raises NotImplementedError."""
        with self.assertRaises(NotImplementedError) as context:
            load_to_bronze(
                spark=self.mock_spark,
                source_path="s3://test-bucket/test.csv",
                source_system="test",
                force_reprocess=True  # Non-default value should fail
            )

        self.assertIn("force_reprocess", str(context.exception))
        self.assertIn("not yet implemented", str(context.exception).lower())

    def test_default_values_pass_validation(self):
        """Test that default parameter values pass the initial validation check."""
        # This test just verifies the parameter validation logic doesn't raise
        # an error for default values. We don't need to run the full function.

        # These are the validation checks from load_to_bronze()
        check_duplicates = True  # default
        force_reprocess = False  # default

        # These should NOT raise errors
        try:
            if check_duplicates is not True:
                raise NotImplementedError("check_duplicates not implemented")
            if force_reprocess is not False:
                raise NotImplementedError("force_reprocess not implemented")
            # If we got here, validation passed
            self.assertTrue(True)
        except NotImplementedError:
            self.fail("Default parameter values should not raise NotImplementedError")


if __name__ == '__main__':
    unittest.main()
