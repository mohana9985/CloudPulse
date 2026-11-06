# `app/core/` — Configuration and metrics

| File | Responsibility |
|---|---|
| `config.py` | Frozen `Settings` dataclass read from environment variables (`DATABASE_URL`, `ENVIRONMENT`, `LOG_LEVEL`, `APP_VERSION`, `SEED_ON_STARTUP`, `CORS_ORIGINS`, …). Nothing secret is stored here |
| `metrics.py` | Prometheus instrumentation: a pure ASGI `PrometheusMiddleware` plus the metric objects |

## Metrics exported at `/api/metrics`

| Metric | Type | Meaning |
|---|---|---|
| `cloudpulse_http_requests_total` | Counter | Requests by method, endpoint, status |
| `cloudpulse_http_request_duration_seconds` | Histogram | Latency by method, endpoint |
| `cloudpulse_http_errors_total` | Counter | Responses with status ≥ 400 |
| `cloudpulse_http_requests_in_progress` | Gauge | Requests currently being handled |
| `cloudpulse_app_uptime_seconds`, `cloudpulse_app_start_time_seconds` | Gauge | Process uptime / start time |
| `cloudpulse_orders_created_total`, `cloudpulse_contact_messages_total` | Counter | Business events |

Endpoint labels use route templates (e.g. `/api/products/{product_id}`) or `unmatched`, which
keeps label cardinality low. These metrics feed the Prometheus/Grafana stack in
[`monitoring/`](../../../monitoring/README.md).
