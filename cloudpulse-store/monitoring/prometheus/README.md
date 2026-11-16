# `monitoring/prometheus/` — Prometheus configuration

| File | Purpose |
|---|---|
| `prometheus.yml` | Scrape interval 5 s (dashboards follow a workload within seconds), evaluation 15 s |

| Job | Target | What |
|---|---|---|
| `cloudpulse-store-backend` | `backend-1/2/3:8000/api/metrics` (label `replica` = B1/B2/B3) | Each replica's own request counters, latency, CPU |
| `cloudpulse-scheduler-gateway` | `gateway:8090/gateway/metrics` | Which replica served each request, queue wait, replica health, retries |
| `cloudpulse-store-loadgen` | `loadgen:8095/metrics` | Website workload as seen by the shoppers (client-side latency, errors) |
| `cloudpulse-scheduler-coordinator` | `cloudpulse-coordinator:8100/metrics` | Live scheduler cluster. Same host: the scheduler's `compose.monitoring.yaml` gives the coordinator this name on the store network. Two EC2s: `compose.two-host.yaml` maps the name to `SCHEDULER_HOST` from `.env`. Shows "down" when the scheduler is not running |
| `prometheus` | `localhost:9090` | Itself |

Mounted at `/etc/prometheus/prometheus.yml`. Check targets at <http://localhost:9090/targets>
when the `monitoring` profile is running. Retention (7 days) and the bind address (`PROMETHEUS_BIND`, default `127.0.0.1`; `0.0.0.0` only in the two-EC2 setup, where the security group allows the dashboard instance alone) are set in `../../compose.yaml` / `.env`.
