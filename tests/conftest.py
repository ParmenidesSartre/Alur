"""Pytest configuration and fixtures."""

import pytest


@pytest.fixture
def sample_orders_data():
    """Sample orders data for testing."""
    return [
        {"order_id": "ORD-001", "customer_id": "CUST-123", "amount": 100},
        {"order_id": "ORD-002", "customer_id": "CUST-456", "amount": 200},
    ]
