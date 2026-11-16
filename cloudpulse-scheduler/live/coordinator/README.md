# live/coordinator

FastAPI coordinator of the live cluster.

| File | Purpose |
|---|---|
| `app.py` | REST API (tasks, workers, heartbeats, long-poll, algorithm switch, workload generator, Prometheus `/metrics`) and the background health monitor |
| `cluster.py` | Cluster state: task queue, mirror workers for the shared `src/schedulers` classes, heartbeat-based failure detection, retries and recovery |
