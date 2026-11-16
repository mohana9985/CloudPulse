# `cloudpulse-store/monitoring/` — Prometheus and Grafana configuration

Configuration for the **optional** `monitoring` Docker Compose profile. It is mounted read-only
into the official `prom/prometheus` and `grafana/grafana` containers defined in
[`../compose.yaml`](../compose.yaml).

```bash
cd cloudpulse-store
docker compose --profile monitoring up --build -d
# Prometheus: http://localhost:9090   Grafana: http://localhost:3000
```

Both ports are bound to `127.0.0.1` only. On EC2, reach Grafana through an SSH tunnel. In the
two-EC2 setup ([`docs/AWS_TWO_EC2.md`](../docs/AWS_TWO_EC2.md)) Prometheus also listens on the
instance (`PROMETHEUS_BIND=0.0.0.0` in `.env`) so the dashboard instance can query it; the security
group allows only that instance. The Grafana admin user and password come **only** from
`GRAFANA_ADMIN_USER` / `GRAFANA_ADMIN_PASSWORD` in `.env` (template:
[`../.env.example`](../.env.example)); compose refuses to start without a password, and
`deploy.sh` replaces the template placeholder with a random one. Never commit a real `.env`.

| Path | Contents |
|---|---|
| [`prometheus/`](prometheus/README.md) | Scrape configuration |
| [`grafana/`](grafana/README.md) | Grafana provisioning: datasource and dashboard |

Data flow: backend replicas, scheduling gateway, website loadgen and the live coordinator → Prometheus
(every 5 s, 7-day retention) → three Grafana dashboards.

The `cloudpulse-scheduler-coordinator` job targets the live scheduler coordinator (same host:
attached with `cloudpulse-scheduler/compose.monitoring.yaml`; two EC2s: reached through
`SCHEDULER_HOST`); the provisioned dashboard
**CloudPulse Scheduler - Live Cluster** shows its worker availability, CPU/memory and task
metrics. The target simply shows as "down" when the scheduler stack is not running.
Metric definitions: [`backend/app/core/`](../backend/app/core/README.md).
