# live/dashboard

Streamlit dashboard (port 8501), two pages.

| File | Purpose |
|---|---|
| `app.py` | Entry point and page navigation |
| `website_page.py` | **Website workload** (default): sends shopper traffic to the CloudPulse Store through `loadgen`, shows gateway scheduling, per-replica load, failures (graceful outage / real crash) and run comparison |
| `cluster_page.py` | **Compute cluster**: the live scheduler's workers, tasks, events and algorithm comparison |
| `api.py` | HTTP clients for the coordinator, gateway, loadgen and Prometheus (no Streamlit imports, unit-tested) |

Settings come from environment variables set by compose (from `../../.env`): `COORDINATOR_URL`,
`GATEWAY_URL`, `LOADGEN_URL`, `PROMETHEUS_URL`, `GRAFANA_PUBLIC_URL`, `BACKEND_CPU_LIMITS`. Same host:
`compose.monitoring.yaml` points them at the store's containers; two EC2s: `compose.two-host.yaml`
points them at `STORE_HOST`.
