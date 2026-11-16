# `provisioning/dashboards/` — Dashboards

| File | Purpose |
|---|---|
| `dashboards.yml` | File provider `cloudpulse`: loads JSON dashboards from this folder into the Grafana folder **CloudPulse** |
| `cloudpulse-store.json` | Dashboard **CloudPulse Store - Application Overview** (uid `cloudpulse-store`) |
| `cloudpulse-gateway.json` | Dashboard **CloudPulse Store - Request Scheduling Gateway** (uid `cloudpulse-gateway`), see below |
| `cloudpulse-scheduler.json` | Dashboard **CloudPulse Scheduler - Live Cluster** (uid `cloudpulse-scheduler-live`): workers up, tasks completed/s, retries, worker failures, worker availability, worker CPU (% of container limit, psutil), worker memory (cgroup), tasks by status, execution-time p95 by worker, turnaround p95 by algorithm. Data comes from the live coordinator's `/metrics` (see `../../prometheus/README.md`) |

Store panels: Requests / s · Error rate · p95 latency · Uptime · Requests / s by endpoint ·
Latency p50 / p95 / p99 · Errors / s by status · In-flight requests & orders/min.

UI edits are allowed (`allowUiUpdates: true`) but are stored in Grafana's volume; export the JSON
back into this folder to keep a change.

## cloudpulse-gateway.json — "CloudPulse Store - Request Scheduling Gateway"

Active algorithm, requests/s and share per backend replica, backlog, in-flight requests, queue-wait
and service-time p95 per replica, replica health, retries/queue timeouts, and CPU per replica (from
the replicas' own `/api/metrics`). Source: `gateway:8090/gateway/metrics` (job
`cloudpulse-scheduler-gateway`).

Row **Website workload (sent from the Streamlit dashboard)**: workload running, run progress,
shopper requests/s, client-side error rate, end-to-end latency p50/p95 and requests/s by request
type. Source: `loadgen:8095/metrics` (job `cloudpulse-store-loadgen`).
