# `cloudpulse-store/monitoring/` — Prometheus and Grafana configuration

Configuration for the **optional** `monitoring` Docker Compose profile. It is mounted read-only
into the official `prom/prometheus` and `grafana/grafana` containers defined in
[`../compose.yaml`](../compose.yaml).

```bash
cd cloudpulse-store
docker compose --profile monitoring up --build -d
# Prometheus: http://localhost:9090   Grafana: http://localhost:3000
```

Both ports are bound to `127.0.0.1` only. On EC2, reach them through an SSH tunnel. The Grafana
admin user and password come from `GRAFANA_ADMIN_USER` / `GRAFANA_ADMIN_PASSWORD` in `.env`
(see [`../.env.example`](../.env.example)); never commit a real `.env`.

| Path | Contents |
|---|---|
| [`prometheus/`](prometheus/README.md) | Scrape configuration |
| [`grafana/`](grafana/README.md) | Grafana provisioning: datasource and dashboard |

Data flow: backend `/api/metrics` → Prometheus (every 15 s, 7-day retention) → Grafana dashboard.
Metric definitions: [`backend/app/core/`](../backend/app/core/README.md).
