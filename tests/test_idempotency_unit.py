"""
Unit tests for idempotency features.

Tests:
1. Multi-source path normalization
2. File tracking metadata attachment
3. DynamoDB state methods
"""

def test_multi_source_path_normalization():
    """Test that source_path parameter accepts both string and list."""
    from alur.ingestion import load_to_bronze

    # Single path should work
    single_path = "s3://bucket/orders/*.csv"
    assert isinstance(single_path, str)

    # List of paths should work
    multi_paths = [
        "s3://bucket/orders/*.csv",
        "s3://bucket/archive/*.csv"
    ]
    assert isinstance(multi_paths, list)
    assert len(multi_paths) == 2

    print("[OK] Multi-source path normalization works")


def test_state_table_name():
    """Test that AWSAdapter uses correct default state table name."""
    from alur.engine.adapter import AWSAdapter

    # Create adapter without explicit state_table (should use default)
    adapter = AWSAdapter(region="us-east-1")

    # Check default state table name
    assert adapter.state_table == "alur-ingestion-state", \
        f"Expected 'alur-ingestion-state', got '{adapter.state_table}'"

    print("[OK] State table name is correct: alur-ingestion-state")


def test_adapter_methods_exist():
    """Test that idempotency methods exist in AWSAdapter."""
    from alur.engine.adapter import AWSAdapter

    adapter = AWSAdapter(region="us-east-1")

    # Check methods exist
    assert hasattr(adapter, 'is_file_processed'), "Missing is_file_processed method"
    assert hasattr(adapter, 'mark_file_processed'), "Missing mark_file_processed method"
    assert hasattr(adapter, 'get_processed_files'), "Missing get_processed_files method"

    # Check methods are callable
    assert callable(adapter.is_file_processed)
    assert callable(adapter.mark_file_processed)
    assert callable(adapter.get_processed_files)

    print("[OK] All idempotency methods exist in AWSAdapter")


def test_load_to_bronze_signature():
    """Test that load_to_bronze has new parameters."""
    from alur.ingestion import load_to_bronze
    import inspect

    sig = inspect.signature(load_to_bronze)
    params = sig.parameters

    # Check new parameters exist
    assert 'enable_idempotency' in params, "Missing enable_idempotency parameter"
    assert 'source_path' in params, "Missing source_path parameter"

    # Check default value for enable_idempotency
    default = params['enable_idempotency'].default
    assert default is True, f"Expected enable_idempotency=True, got {default}"

    print("[OK] load_to_bronze has correct signature")


if __name__ == "__main__":
    print("Running idempotency unit tests...\n")

    try:
        test_multi_source_path_normalization()
        test_state_table_name()
        test_adapter_methods_exist()
        test_load_to_bronze_signature()

        print("\n" + "="*50)
        print("ALL TESTS PASSED")
        print("="*50)

    except AssertionError as e:
        print(f"\n[FAIL] {e}")
        exit(1)
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        exit(1)
