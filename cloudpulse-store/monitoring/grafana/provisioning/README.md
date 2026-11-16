# `grafana/provisioning/` — Grafana provisioning files

| Path | Purpose |
|---|---|
| [`datasources/`](datasources/README.md) | Registers Prometheus as the default datasource |
| [`dashboards/`](dashboards/README.md) | Dashboard provider and three dashboards: Store application, Request Scheduling Gateway (+ Website workload), Scheduler Live Cluster |

Grafana reads these files at start-up; no manual setup in the UI is needed.
