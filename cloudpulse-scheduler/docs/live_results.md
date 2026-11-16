# Live cluster results — REAL execution (single Docker host)

Source: `results/live-mac-20261112/` (CSV + JSONL) and `charts/live-mac-20261112/` (PNG).
Every file is labelled `measurement_type = "REAL execution on live workers (not simulated)"` and
`setup = single-host-docker`. The simulator results in `results/stage4-grid/` are **simulated**
and are never mixed with these numbers.

## Setup

| Item | Value |
|---|---|
| Host | one Apple M1 Mac (8 GB), Docker via Colima VM (2 vCPU, 3 GB) |
| Coordinator | FastAPI, `live/coordinator/`, uses the unchanged `src/schedulers` classes |
| Workers | 3 FastAPI containers W1/W2/W3, CPU quotas **0.75 / 0.45 / 0.30** cores (capacity 1.0/0.6/0.4, WRR weights 5:3:2), 128 MB memory limit each |
| Tasks | real computations from `live/tasks.py`: `prime_count`, `data_aggregation`, `sha256_chain`; sizes small/medium/large 60/30/10 % |
| Arrivals | Poisson, load ρ = 0.85 of total capacity, replayed by the coordinator from a seed; identical workload (same SHA-256 fingerprint) for every algorithm |
| Measurements | execution time and CPU seconds measured by the worker; CPU %/memory sampled with psutil + cgroup v2 every heartbeat (2 s); wait/turnaround/overhead measured by the coordinator |
| Heartbeat / failure config | heartbeat 2 s, unavailable after 5 s, failed after 10 s, max 3 attempts |
| Statistics | mean ± sample SD over seeds 1, 2, 3 (3 runs per cell) |

**This is a single-machine experiment.** The three workers are three containers (processes with
separate CPU quotas) on one host, not three machines. Coordinator↔worker traffic crosses only the
Docker bridge network, so the recorded network overhead is a lower bound for a real network.

## 1. Algorithm comparison (grid: 3 sizes × 3 seeds × 5 configurations = 45 runs)

Average turnaround (s), mean ± SD over 3 seeds. Lower is better.

| Algorithm | 30 tasks | 60 tasks | 120 tasks |
|---|---|---|---|
| Round Robin | 3.26 ± 2.44 | 5.43 ± 3.39 | 10.74 ± 3.86 |
| Weighted Round Robin | 1.98 ± 0.86 | 2.39 ± 0.77 | 3.35 ± 1.37 |
| Least Loaded | 1.43 ± 0.61 | 1.97 ± 0.55 | 2.71 ± 1.66 |
| Shortest Job First | **1.24 ± 0.42** | **1.38 ± 0.48** | **1.70 ± 0.63** |
| FCFS (control) | 1.33 ± 0.59 | 2.02 ± 0.73 | 2.49 ± 1.17 |

Other metrics, 120 tasks (means over 3 seeds):

| Algorithm | Avg wait (s) | Max wait (s) | Throughput (tasks/s) | Makespan (s) | Overhead / task (ms) | Tasks lost |
|---|---|---|---|---|---|---|
| Round Robin | 9.48 | 65.19 | 1.19 | 101.3 | 5.5 | 0 |
| Weighted Round Robin | 2.53 | 8.33 | 3.01 | 39.8 | 4.5 | 0 |
| Least Loaded | 1.88 | 4.47 | 3.23 | 37.2 | 3.4 | 0 |
| Shortest Job First | 0.85 | **11.49** | 3.05 | 40.0 | 4.2 | 0 |
| FCFS (control) | 1.67 | 4.35 | 3.27 | 36.8 | 4.3 | 0 |

Task distribution and measured resource use (all grid runs, per worker):

| Algorithm | Share W1/W2/W3 (%) | Mean CPU, % of container limit W1/W2/W3 | Mean memory (MB) |
|---|---|---|---|
| Round Robin | 33 / 33 / 33 | 25 / 40 / 84 | ≈ 43 each |
| Weighted Round Robin | 50 / 30 / 20 | 78 / 70 / 70 | ≈ 43 each |
| Least Loaded | 48 / 33 / 19 | 80 / 76 / 77 | ≈ 43 each |
| Shortest Job First | 51 / 31 / 18 | 79 / 75 / 79 | ≈ 43 each |
| FCFS (control) | 51 / 30 / 19 | 85 / 81 / 79 | ≈ 43 each |

Findings (real execution):

1. **Round Robin is the worst by a wide margin** on heterogeneous workers: it gives the slowest
   worker (W3, 0.30 CPU) one third of the tasks, so W3 runs at ~84 % of its limit while W1 idles
   at ~25 %, and the backlog on W3 grows with workload size (max wait 65 s at 120 tasks).
   Same qualitative result as the simulator.
2. **Weighted Round Robin fixes most of this** by matching shares to capacity (50/30/20 %), but
   cannot react to task-size variance, so its waiting times are 2–3× those of LL/SJF.
3. **Least Loaded and SJF are the best primaries.** SJF has the lowest average turnaround at all
   sizes; LL has the lowest *maximum* wait at 120 tasks (4.5 s vs 11.5 s for SJF), the same
   long-task penalty of SJF seen in the simulation (no ageing).
4. **FCFS control** (central queue, first idle worker) performs close to LL here because tasks
   are short relative to the arrival rate and the central queue never leaves a fast worker idle
   while another worker holds a backlog. This is why FCFS is kept as a control, not ranked.
5. **Network/dispatch overhead is 3–7 ms per task** (coordinator round trip minus worker-measured
   execution time), < 1 % of the mean task time on the Docker bridge.
6. **No task was lost or retried** in any of the 45 normal runs.

Charts: `01_avg_turnaround.png` … `09_memory.png`.

## 2. Worker failure and recovery (60 tasks, 3 seeds, 5 configurations = 15 normal + 15 failure runs)

Procedure: 5 s after the run starts, worker W2 is killed with `docker compose kill` (SIGKILL,
no goodbye message); 15 s later it is started again. Heartbeat monitoring in the coordinator does
all detection; nothing tells it about the kill.

| Algorithm | Avg turnaround normal → failure (s) | Makespan normal → failure (s) | Unavailable detected after kill (s) | Failed detected (s) | Interrupted tasks | Queued tasks reassigned | All affected tasks done after kill (s) | W2 rejoined after kill (s) | Retries | Lost |
|---|---|---|---|---|---|---|---|---|---|---|
| Round Robin | 5.61 → 11.30 | 43.6 → 59.3 | 4.7 | 9.7 | 1.0 | 6.3 | 37.2 | 16.8 | 1.0 | 0 |
| Weighted Round Robin | 2.27 → 4.69 | 20.6 → 29.1 | 4.5 | 9.5 | 0.7 | 6.0 | 11.3 | 17.0 | 0.7 | 0 |
| Least Loaded | 1.70 → 4.05 | 21.7 → 26.9 | 4.5 | 9.5 | 1.0 | 2.7 | 8.5 | 16.7 | 1.0 | 0 |
| Shortest Job First | 1.31 → 2.43 | 21.3 → 28.1 | 4.8 | 9.8 | 1.0 | 0 (central queue) | 10.2 | 16.9 | 1.0 | 0 |
| FCFS (control) | 1.76 → 3.94 | 21.1 → 25.2 | 4.2 | 9.0 | 1.0 | 0 (central queue) | 7.7 | 16.8 | 1.0 | 0 |

Findings:

1. Detection times match the configuration: *unavailable* after ≈ 4.2–4.8 s (timeout 5 s minus
   the age of the last heartbeat) and *failed* after ≈ 9.0–9.8 s (timeout 10 s). The failed
   worker receives no new task from then on.
2. The task running on W2 at the kill is **interrupted and retried** (1 retry, attempt 2) on a
   healthy worker; tasks queued at W2 under RR/WRR/LL are **reassigned through the active
   algorithm**. SJF and FCFS keep a central queue, so nothing is queued at a worker and nothing
   needs reassignment.
3. **No task was lost in any run** (`lost = 0`, 60/60 completed every time); the retry limit
   (3 attempts) was never reached.
4. W2 rejoins ≈ 16.7–17.0 s after the kill (15 s down + container start + first heartbeat),
   is recognised by its new `boot_id` and receives tasks again.
5. Cost of the failure: average turnaround roughly doubles for every algorithm; RR suffers most
   because it had queued the most tasks at W2 (6.3) and keeps sending 1/3 of new tasks to the
   slow W3.

Chart: `10_failure_vs_normal.png`. Events: `events_failure.jsonl`.

## 3. Scalability: same workload on 1, 2 and 3 workers (60 tasks, 3 seeds, 5 configurations = 45 runs)

Procedure: the arrival rate is fixed for a total capacity of 2.0 (ρ = 0.85), and the *same*
60-task workload (same seed and fingerprint) is replayed with only W1 running (0.75 CPU), then
W1+W2 (1.20 CPU), then W1+W2+W3 (1.50 CPU). Workers not in the subset are stopped with
`docker compose stop` and marked *failed* by the coordinator before the run starts.

Makespan (s) and average turnaround (s), mean ± SD over 3 seeds:

| Algorithm | W1 only | W1+W2 | W1+W2+W3 |
|---|---|---|---|
| Round Robin | 33.6 ± 4.3 / 9.06 | 30.8 ± 10.4 / 4.60 | **44.6 ± 7.8 / 5.37** |
| Weighted Round Robin | 33.7 ± 4.9 / 9.30 | 25.6 ± 1.4 / 3.97 | 20.7 ± 1.6 / 2.28 |
| Least Loaded | 33.6 ± 4.8 / 9.17 | 22.6 ± 2.5 / 3.36 | 20.7 ± 3.1 / 1.76 |
| Shortest Job First | 34.0 ± 5.0 / 3.75 | 23.9 ± 2.8 / 1.77 | 22.5 ± 4.2 / 1.43 |
| FCFS (control) | 34.1 ± 5.1 / 9.48 | 22.4 ± 1.3 / 3.42 | 19.7 ± 1.1 / 1.84 |

Throughput (tasks/s), max wait (s) and measured CPU (% of each container's quota):

| Workers | Total quota | Throughput LL / SJF / RR | Max wait LL / SJF / RR | Mean CPU per worker (all algorithms) |
|---|---|---|---|---|
| W1 | 0.75 | 1.81 / 1.79 / 1.81 | 17.3 / 25.5 / 17.2 | W1 96 % |
| W1+W2 | 1.20 | 2.68 / 2.54 / 2.12 | 5.7 / 12.0 / 14.1 | W1 80 %, W2 86 % |
| W1+W2+W3 | 1.50 | 2.94 / 2.72 / 1.37 | 2.4 / 3.1 / 27.2 | W1 68 %, W2 71 %, W3 80 % |

Findings:

1. **One worker is saturated** (96 % of its quota): all five configurations give the same
   makespan (≈ 34 s) because with one worker there is no placement decision; only the *order*
   differs, which is why SJF alone cuts average turnaround (3.75 s vs ≈ 9.2 s) at the price of the
   highest maximum wait (25.5 s).
2. **Adding W2 (capacity +60 %) shortens the makespan by ~33 %** for LL/SJF/FCFS/WRR
   (34 → 22–26 s) and raises throughput from 1.8 to 2.5–2.7 tasks/s — close to the +60 % capacity
   gain. Adding W3 (+40 % capacity, but only 0.30 CPU) gives a further 5–10 % only: the load
   (ρ = 0.85 of capacity 2.0) is no longer the bottleneck and the arrival rate is.
3. **Round Robin gets *worse* with the third worker** (makespan 30.8 → 44.6 s, max wait
   14 → 27 s): it sends one third of the tasks to a worker that has one fifth of the capacity.
   Scaling out helps only if the scheduler is capacity-aware — WRR, LL and SJF/FCFS all improve.
4. Dispatch overhead per task grows slightly with the number of workers (2.2–2.8 ms with one
   worker, 3.3–5.6 ms with three) because the coordinator polls and tracks more workers; it stays
   below 1 % of the mean task time.
5. No task was lost or retried in any of the 45 runs.

Charts: `11_scaling_makespan.png`, `12_scaling_turnaround.png`. Numbers: `scaling_summary.csv`,
`runs_scaling.csv`, `per_worker_scaling.csv`.

## 4. Totals

| Scenario | Runs | Tasks executed | Lost | Retries |
|---|---|---|---|---|
| grid | 45 | 3 150 | 0 | 0 |
| normal + failure | 15 + 15 | 1 800 | 0 | 14 (one per failure run, except one run where W2 was idle at the kill) |
| scaling | 45 | 2 700 | 0 | 0 |
| **all** | **120** | **7 650** | **0** | 14 |

Timestamps and setup for every stage are in `metadata.json` / `metadata_scaling.json`
and the terminal log `../results/live-mac-20261112.log` (which also records two interrupted
and restarted stages).
