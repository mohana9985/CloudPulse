# `monitoring/prometheus/` — Prometheus configuration

| File | Purpose |
|---|---|
| `prometheus.yml` | Global scrape/evaluation interval 15 s. Jobs: `cloudpulse-store-backend` scrapes `backend:8000/api/metrics` on the internal Docker network (label `service=cloudpulse-store`); `prometheus` scrapes itself |

Mounted at `/etc/prometheus/prometheus.yml`. Check targets at <http://localhost:9090/targets>
when the `monitoring` profile is running. Retention (7 days) is set in `../../compose.yaml`.
