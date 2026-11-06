# DATABASE_URL must point at a temporary database before the app is imported.

import os
import tempfile
from pathlib import Path

import pytest

_TMP_DIR = tempfile.mkdtemp(prefix="cloudpulse-test-")
os.environ["DATABASE_URL"] = f"sqlite:///{Path(_TMP_DIR) / 'test.db'}"
os.environ["SEED_ON_STARTUP"] = "true"

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def valid_order(client):
    product = client.get("/api/products").json()["items"][0]
    return {
        "customer_name": "Test Customer",
        "email": "test.customer@example.com",
        "address": "42 Demo Street, Pilani, Rajasthan",
        "items": [{"product_id": product["id"], "quantity": 2}],
    }
