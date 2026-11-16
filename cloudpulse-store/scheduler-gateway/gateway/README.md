# scheduler-gateway/gateway

| File | Purpose |
|---|---|
| `app.py` | FastAPI proxy: every `/api/*` request becomes a scheduling task; control API (`/gateway/*`), simulated outage, real-crash trigger, Prometheus metrics |
| `dispatcher.py` | Bridge to the shared `src/schedulers` classes: mirror workers per replica, slots, backlog, health, runs |
| `config.py` | Settings from environment variables and initial per-route service-time estimates |

See [`../README.md`](../README.md).
