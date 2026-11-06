from datetime import datetime


def test_health_returns_ok(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "cloudpulse-store-backend"
    datetime.fromisoformat(body["timestamp"])


def test_ready_checks_database(client):
    response = client.get("/api/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["checks"]["database"] == "ok"
    assert body["checks"]["products_seeded"] == "ok"
    assert body["product_count"] >= 20


def test_openapi_docs_available(client):
    assert client.get("/api/docs").status_code == 200
    assert client.get("/api/openapi.json").json()["info"]["title"] == "CloudPulse Store API"
