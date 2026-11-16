# CloudPulse website workload generator (`loadgen`)

Small FastAPI service that sends **real shopper API requests** to the CloudPulse Store. It is
driven from the Streamlit dashboard's **Website workload** page.

```
Streamlit ──REST──▶ loadgen ──HTTP──▶ frontend (Nginx) ──/api/*──▶ scheduling gateway ──▶ backend-1 / 2 / 3
```

Requests enter through the website's public entry point, so each one is scheduled by the gateway
exactly like a browser click. The gateway's trace headers (`x-cloudpulse-backend`,
`x-cloudpulse-algorithm`, wait and service time) are recorded per request.

## Workload model

- `num_requests` requests, Poisson arrivals at `rate` requests/second (open loop), at most
  `max_concurrency` in flight.
- Seeded: the same `seed`, `rate`, `mix` and catalogue give exactly the same requests at the
  same offsets, so runs with different algorithms are comparable.
- Mixes (request types are real store API calls):

| Mix | home | categories | list | filter | detail | search | order |
|---|---|---|---|---|---|---|---|
| `mixed` (default) | 15 | 5 | 15 | 15 | 30 | 15 | 5 |
| `browse` | 25 | 10 | 20 | 10 | 35 | – | – |
| `search` | – | – | – | 25 | 25 | 50 | – |
| `shopping` | 15 | – | 15 | 10 | 30 | 20 | 10 |

`order` = `POST /api/orders` (writes to the shared SQLite database; a `409` out-of-stock answer
counts as OK). Product ids and categories are read from the live store at the start of each run.

## API (port 8095, published on 127.0.0.1 only)

In the two-EC2 setup (`LOADGEN_BIND=0.0.0.0` in `.env`, [`../docs/AWS_TWO_EC2.md`](../docs/AWS_TWO_EC2.md))
the dashboard instance reaches it over the private network; the security group allows only that
instance. The API has no authentication, so never open 8095 to the internet.

| Method | Path | Purpose |
|---|---|---|
| GET | `/loadgen/health` | liveness |
| GET | `/loadgen/config` | mixes and limits |
| POST | `/loadgen/start` | `{"num_requests":3000,"rate":200,"mix":"mixed","seed":42,"max_concurrency":200}` |
| POST | `/loadgen/stop` | stop the running workload (in-flight requests finish) |
| GET | `/loadgen/status` | current/last run: progress, OK/errors, req/s, p50/p95/p99, share per backend |
| GET | `/loadgen/recent` | last requests: type, path, backend, status, latency, gateway wait/service |
| GET | `/loadgen/runs` | finished runs (algorithm comparison) |
| GET | `/metrics` | Prometheus: `loadgen_requests_total{kind,outcome,backend}`, `loadgen_request_latency_seconds`, `loadgen_run_active`, `loadgen_run_progress_ratio`, `loadgen_inflight_requests` |

Only one run at a time (`409` otherwise).

## Tests

```bash
cd cloudpulse-store/loadgen
uv venv -p 3.11 .venv && uv pip install -p .venv/bin/python -r requirements-dev.txt
.venv/bin/python -m pytest          # 17 tests, no Docker needed
```

Windows (PowerShell) — see the [translation table](../../README.md#windows-powershell):

```powershell
cd cloudpulse-store\loadgen
uv venv --python 3.11 .venv
uv pip install --python .venv -r requirements-dev.txt
.venv\Scripts\python -m pytest       # 17 tests, no Docker needed
```
