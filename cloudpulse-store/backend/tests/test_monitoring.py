import os


def test_metrics_exposed_in_prometheus_format(client):
    client.get("/api/products")
    response = client.get("/api/metrics")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    text = response.text
    for metric in (
        "cloudpulse_http_requests_total",
        "cloudpulse_http_request_duration_seconds_bucket",
        "cloudpulse_http_requests_in_progress",
        "cloudpulse_app_uptime_seconds",
        "cloudpulse_orders_created_total",
    ):
        assert metric in text


def test_metrics_use_route_templates_not_raw_ids(client):
    client.get("/api/products/1")
    client.get("/api/products/2")
    text = client.get("/api/metrics").text
    assert 'endpoint="/api/products/{product_id}"' in text
    assert 'endpoint="/api/products/1"' not in text


def test_unknown_urls_grouped_as_unmatched(client):
    assert client.get("/api/does-not-exist-123").status_code == 404
    text = client.get("/api/metrics").text
    assert 'endpoint="unmatched"' in text
    assert "does-not-exist-123" not in text


def test_errors_are_counted(client):
    client.get("/api/products/999999")
    text = client.get("/api/metrics").text
    assert (
        'cloudpulse_http_errors_total{endpoint="/api/products/{product_id}",method="GET",status_code="404"}'
        in text
    )


def test_stats_endpoint(client):
    response = client.get("/api/stats")
    assert response.status_code == 200
    body = response.json()
    assert body["total_products"] >= 20
    assert body["total_api_requests"] > 0
    assert body["uptime_seconds"] >= 0
    for key in ("total_orders", "total_contact_messages", "started_at"):
        assert key in body


def test_stats_and_metrics_do_not_leak_configuration(client):
    database_url = os.environ["DATABASE_URL"]
    assert database_url not in client.get("/api/stats").text
    assert database_url not in client.get("/api/metrics").text
    assert "DATABASE_URL" not in client.get("/api/stats").text
