# CloudPulse — demonstration guide (macOS)

Everything below runs on the Mac with Docker provided by Colima. Commands are given with the
directory they must be executed in. Nothing here touches AWS.

## 0. One-time setup

```bash
# anywhere
colima start --cpu 2 --memory 3            # Docker engine (skip if already running)
# in cloudpulse-scheduler/
uv venv --python 3.11 .venv
uv pip install --python .venv -r requirements.txt -r requirements-live.txt -r requirements-dashboard.txt
```

## 1. Prove the code is tested

```bash
# in cloudpulse-scheduler/
.venv/bin/python -m pytest -q -p no:warnings       # expected: 266 passed
```

## 1b. Main demo: the dashboard drives the website

```bash
# in cloudpulse-store/
docker compose --profile monitoring up -d --build   # website, 3 replicas, gateway, loadgen, Prometheus, Grafana
# in cloudpulse-scheduler/
docker compose -f compose.yaml -f compose.monitoring.yaml up -d --build   # coordinator, workers, Streamlit
open http://localhost              # the website
open http://localhost:8501         # Streamlit, page "Website workload" (default page)
open http://localhost:3000/d/cloudpulse-gateway   # Grafana (admin / password from cloudpulse-store/.env)
```

1. Sidebar: algorithm **Round Robin** → *Apply algorithm*. Keep the defaults (3000 requests,
   200 req/s, mix `mixed`, seed 42) → **Start**. Watch progress, p95 latency, the *Backends* tab
   (share per replica, CPU % of limit) and Grafana's *Website workload* section.
2. Repeat with **Weighted Round Robin** and **Least Loaded**, same settings. The *Algorithm
   comparison* tab lists the three runs; expected: Least Loaded lowest p95
   (see `cloudpulse-store/docs/SCHEDULING.md` §6).
3. Failure: set *Requests* to 6000, start a run, then *Failure demo* → **Real crash**, backend
   **B1**, 15 s → *Crash backend*. B1's process is killed: the *Backends* tab shows
   `DOWN (crashed)`, the error line under the metrics counts the few requests that were cut off
   and the ones the gateway retried, latency rises while B2/B3 carry the load, and after ~15 s
   Docker restarts B1 and it shows `healthy` again. *Failures & events* lists
   crash → unavailable → retried → recovered.
   **Graceful outage** instead takes B1 out of rotation without killing it: 0 errors.

The second page, **Compute cluster**, is the live scheduler with computational tasks (sections
2–4 below).

## 2. Start the live cluster

```bash
# in cloudpulse-scheduler/
docker compose up -d --build
docker compose ps                                  # coordinator, worker-1/2/3 "healthy", dashboard up
open http://localhost:8501                         # Streamlit dashboard
open http://localhost:8100/docs                    # coordinator REST API (Swagger)
```

What to show on the dashboard:
- *Workers* table: W1/W2/W3 **active**, heartbeat age ≈ 0–2 s, CPU limit 0.75/0.45/0.30 cores,
  live CPU % and memory from psutil.
- Sidebar: scheduling algorithm selector (RR, WRR, LL, SJF, FCFS control).

## 3. Submit a workload and compare algorithms (same workload each time)

In the dashboard sidebar: pick an algorithm → *Submit workload* with `num_tasks = 60`,
`seed = 1`, `load = 0.85` → watch *System overview* (submitted / completed / pending, average
execution time, throughput), *Task distribution across workers* and *Task execution history*.
Repeat with another algorithm and the **same seed**; the *Runs* table at the bottom then compares
the archived runs side by side (identical workload fingerprint).

Same thing from the terminal:

```bash
# in cloudpulse-scheduler/
for alg in round_robin weighted_round_robin least_loaded shortest_job_first; do
  curl -s -X POST localhost:8100/scheduler/algorithm -H 'content-type: application/json' -d "{\"algorithm\":\"$alg\"}"
  curl -s -X POST localhost:8100/workloads/start -H 'content-type: application/json' -d '{"num_tasks":60,"seed":1,"load":0.85}'
  sleep 45
  curl -s localhost:8100/scheduler/stats | python3 -c "import sys,json; r=json.load(sys.stdin)['run']; print(r['algorithm'], 'completed', r['completed'], 'avg_turnaround', round(r['avg_turnaround_seconds'],2), 'thr', round(r['throughput_tasks_per_second'],2), r['completed_per_worker'])"
done
curl -s localhost:8100/scheduler/runs | python3 -m json.tool | head -60
```

Expected (from `docs/live_results.md`): RR much slower (W3 overloaded), WRR better, LL and SJF
best; distribution ≈ 33/33/33 % for RR vs ≈ 50/30/20 % for the others.

## 4. Worker failure and recovery

```bash
# in cloudpulse-scheduler/ — start a workload first (step 3), then within ~5 s:
docker compose kill worker-2          # SIGKILL, no goodbye
# watch the dashboard: W2 -> "unavailable" after 5 s, "failed" after 10 s; its running task is
# retried on W1/W3; queued tasks are reassigned; no new task goes to W2.
docker compose start worker-2         # ~15 s later
# W2 reappears as "active" with a new boot id; the event log shows the whole sequence:
curl -s 'localhost:8100/events?limit=30' | python3 -m json.tool
```

The dashboard sidebar *Failure demo* is the browser alternative: it tells a worker to stop
heartbeating for N seconds (`/admin/simulate-outage`, enabled by `ENABLE_CHAOS`), so the
coordinator sees the same unavailable → failed → recovered sequence without a real container kill.
Expected: `lost = 0`, one retry, detection times ≈ 4–5 s / 9–10 s, rejoin ≈ 17 s.

## 5. Monitoring in Prometheus and Grafana (optional)

```bash
# in cloudpulse-store/
docker compose --profile monitoring up -d
# in cloudpulse-scheduler/
docker compose -f compose.yaml -f compose.monitoring.yaml up -d
open http://localhost:9090/targets      # job cloudpulse-scheduler-coordinator must be UP
open http://localhost:3000              # Grafana -> CloudPulse -> "CloudPulse Scheduler - Live Cluster"
```

## 6. Recorded experiments and charts

- Simulator (450 runs, **simulated** seconds): `results/stage4-grid/`, `charts/stage4-grid/`,
  `docs/stage4_results.md`.
- Live cluster (**real** execution): `results/live-mac-20261112/`, `charts/live-mac-20261112/`,
  `docs/live_results.md`.

Re-run the live experiments (about 45 min in total, stack running):

```bash
# in cloudpulse-scheduler/
.venv/bin/python -m live.experiments.run_live grid    --experiment-id demo --sizes 30 60 120 --seeds 1 2 3
.venv/bin/python -m live.experiments.run_live failure --experiment-id demo --size 60 --seeds 1 2 3
.venv/bin/python -m live.experiments.run_live scaling --experiment-id demo --size 60 --seeds 1 2 3
.venv/bin/python -m live.experiments.live_charts demo
open charts/demo
```

Do not run two experiment runners at the same time: both control the worker containers.

## 7. Stop

```bash
# in cloudpulse-scheduler/
docker compose down
# in cloudpulse-store/ (if started)
docker compose --profile monitoring down
```

## 8. Honest statements for the viva

- Three workers = three **containers with CPU quotas on one host**, not three machines.
- Simulator numbers are simulated; live numbers are real and are reported separately.
- EC2 deployment of the live cluster and the multi-machine run are prepared
  (`deployment/README.md`, `live/README.md`) and not yet executed.
