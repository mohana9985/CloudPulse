# CloudPulse scheduling gateway

The gateway is the piece that **applies the CloudPulse scheduling algorithms to the website**.
It sits between Nginx and the CloudPulse Store backend and routes every `/api/*` request to one
of three backend replicas using the algorithm selected at runtime:

| Algorithm | Dispatch mode | How a request is placed |
|---|---|---|
| `round_robin` (RR) | per-backend queue | next replica in turn that has a free slot |
| `weighted_round_robin` (WRR) | per-backend queue | smooth WRR with weights 5 / 3 / 2 (B1 / B2 / B3) |
| `least_loaded` (LL) | per-backend queue | replica with the least *estimated work in flight / capacity* |
| `shortest_job_first` (SJF) | central queue | waiting requests ordered by estimated service time; released to the fastest free replica |
| `fcfs_baseline` (FCFS) | central queue | control baseline: same as SJF but in arrival order |

The algorithm classes are imported **unchanged** from
[`../../cloudpulse-scheduler/src/schedulers`](../../cloudpulse-scheduler/src/schedulers/README.md).
The gateway only provides the bridge between HTTP requests and the scheduler's `Task` / `Worker`
model (see `gateway/dispatcher.py`):

* one backend replica = one mirror `Worker` (capacity, weight, `max_queue_length` = concurrency slots);
* one HTTP request = one `Task`; its `estimated_duration` is the gateway's running estimate of the
  service time of that route (EWMA of real observations, started from `DEFAULT_ESTIMATES`);
* the mirror's queue holds the requests currently in flight on that replica, so `can_accept()`,
  `estimated_load()` and `weight` behave exactly as in the simulator and the live cluster;
* when every slot of every replica is busy, requests wait in the gateway (per-backend backlog or
  the SJF/FCFS central queue) and are released as soon as a slot frees; a request that waits
  longer than `QUEUE_TIMEOUT` (10 s) receives `503`.

Backend health is probed every 2 s (`/api/health`). A replica that fails two probes, or refuses a
connection, is marked unavailable, its in-flight request is re-dispatched to another replica
(only when the request never reached the backend, so nothing is executed twice) and it rejoins
automatically when the probe succeeds again.

## Endpoints (served by the gateway, not proxied)

| Method | Path | Purpose |
|---|---|---|
| GET | `/gateway/health` | liveness, active algorithm, healthy replicas |
| GET | `/gateway/stats` | live statistics: run summary, per-replica counters, backlog, learned estimates |
| GET | `/gateway/recent?limit=60` | last routed requests (route, replica, estimated / wait / service ms, status) |
| GET | `/gateway/events` | backend unavailable/recovered, retries, algorithm changes, run starts |
| GET | `/gateway/runs` | archived runs (one per algorithm comparison) |
| POST | `/gateway/algorithm` | `{"algorithm": "least_loaded"}` switch at runtime (409 while requests are queued) |
| POST | `/gateway/reset` | archive the current run and start a fresh one |
| POST | `/gateway/backends/{id}/crash` | `{"down_seconds": 15}` REAL crash: calls the replica's `/admin/crash` (private network only, needs `ENABLE_CHAOS=true`), which kills its process and keeps its port closed for N seconds; Docker restarts it. The gateway is not told anything else: it detects the failure from refused connections and health probes |
| POST | `/gateway/backends/{id}/outage` | `{"seconds": 20}` simulated outage: the replica leaves the rotation and its health probes are ignored until the time is up (failure demo; refuses to take down the last healthy replica) |
| GET | `/gateway/metrics` | Prometheus metrics (`gateway_requests_total{backend,route,status_class}`, `gateway_queue_wait_seconds`, `gateway_service_seconds`, `gateway_inflight_requests`, `gateway_backend_up`, `gateway_backlog_requests`, `gateway_algorithm_active`) |
| GET | `/gateway/docs` | Swagger UI |

Every proxied response carries trace headers: `x-cloudpulse-backend`, `x-cloudpulse-algorithm`,
`x-cloudpulse-task-id`, `x-cloudpulse-attempts`, `x-cloudpulse-wait-ms`, `x-cloudpulse-service-ms`.

## Where to look at it

The gateway has **no UI of its own**. The project's scheduling dashboard is the Streamlit
dashboard of the live task cluster (`cloudpulse-scheduler/live/dashboard`, port 8501). The
gateway publishes its API on `127.0.0.1:8090` (two-EC2 setup: `GATEWAY_BIND=0.0.0.0` in `.env`, and
the security group allows only the dashboard instance, because this API has no authentication —
see [`../docs/AWS_TWO_EC2.md`](../docs/AWS_TWO_EC2.md)): read `/gateway/stats` (JSON), switch algorithms
with `POST /gateway/algorithm`, scrape `/gateway/metrics` (Grafana dashboard *Request Scheduling
Gateway* in the store's monitoring profile), or run `load-testing/compare_algorithms.sh`. The
store website at <http://localhost> stays a plain shop; its API traffic is scheduled invisibly.

## Configuration (environment)

| Variable | Default | Meaning |
|---|---|---|
| `ALGORITHM` | `least_loaded` | algorithm at start-up (set in `cloudpulse-store/.env`) |
| `BACKENDS_JSON` | B1/B2/B3 (see `gateway/config.py`) | list of `{id, url, capacity, weight, slots}` |
| `QUEUE_TIMEOUT` | `10` | seconds a request may wait for a slot |
| `UPSTREAM_TIMEOUT` | `30` | backend read timeout |
| `HEALTH_INTERVAL` / `UNHEALTHY_AFTER` | `2` / `2` | probe period and failed probes before marking a replica down |
| `MAX_ATTEMPTS` | `3` | re-dispatch attempts after connection failures |
| `EWMA_ALPHA` | `0.2` | smoothing of the per-route service-time estimate |

In `compose.yaml` the three replicas get CPU quotas proportional to their scheduler capacity
(0.75 / 0.45 / 0.30 CPU) and concurrency slots 4 / 2 / 2, so the heterogeneity the algorithms
reason about is real.

## Run the tests

```bash
# in cloudpulse-store/scheduler-gateway/
uv venv --python 3.11 .venv
uv pip install --python .venv -r requirements-dev.txt
.venv/bin/python -m pytest            # 24 tests: scheduling behaviour + HTTP proxying with fake backends, outage, crash trigger
```

Windows (PowerShell) — see the [translation table](../../README.md#windows-powershell):

```powershell
cd cloudpulse-store\scheduler-gateway
uv venv --python 3.11 .venv
uv pip install --python .venv -r requirements-dev.txt
.venv\Scripts\python -m pytest         # 24 tests
```

## Compare the algorithms under load

```bash
# in cloudpulse-store/load-testing/  (site running: docker compose up --build -d)
source .venv/bin/activate
./compare_algorithms.sh http://localhost 150 30 45s MixedWorkloadUser
```

On Windows run the script in **Git Bash** (`source .venv/Scripts/activate`, then the same
`./compare_algorithms.sh ...` line), or in WSL; see [`../load-testing/README.md`](../load-testing/README.md).

The script runs the same Locust workload once per algorithm, archives a gateway run after each
one and prints a Markdown table (Locust latency/throughput + gateway queue wait + per-replica
share). The archived runs are also returned by `GET /gateway/runs`.
