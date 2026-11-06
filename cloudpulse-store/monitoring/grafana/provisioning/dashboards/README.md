# `provisioning/dashboards/` — Dashboards

| File | Purpose |
|---|---|
| `dashboards.yml` | File provider `cloudpulse`: loads JSON dashboards from this folder into the Grafana folder **CloudPulse** |
| `cloudpulse-store.json` | Dashboard **CloudPulse Store - Application Overview** (uid `cloudpulse-store`) |

Panels: Requests / s · Error rate · p95 latency · Uptime · Requests / s by endpoint ·
Latency p50 / p95 / p99 · Errors / s by status · In-flight requests & orders/min.

UI edits are allowed (`allowUiUpdates: true`) but are stored in Grafana's volume; export the JSON
back into this folder to keep a change.
