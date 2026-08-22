import pytest
import httpx
import os

GATEWAY_URL = os.getenv("GATEWAY_URL", "http://localhost:8000")

@pytest.mark.integration
def test_chinook_regression():
    """
    Test standard LLM queries on the Chinook database to ensure no regression in SQL generation.
    """
    # 1. Register chinook_test.db
    # 2. Sync and set allowlist for required tables (Customer, Invoice, etc.)
    # 3. Ask "Quels sont les meilleurs clients ?"
    # 4. Verify SQL is generated and results are returned correctly
    pass
