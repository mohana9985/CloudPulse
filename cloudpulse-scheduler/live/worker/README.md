# live/worker

Worker service of the live cluster: registers, sends heartbeats, long-polls the coordinator, runs real tasks and reports results.

| File | Purpose |
|---|---|
| `app.py` | FastAPI app (`/health`, `/status`, Prometheus `/metrics`, `POST /admin/simulate-outage`) and background loops |
| `agent.py` | Heartbeat and pull/execute loops (outbound HTTP only, so a worker can run on another machine) |
| `metrics.py` | CPU and memory from psutil and Linux cgroup v2 files |
