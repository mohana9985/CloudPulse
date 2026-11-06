# `src/schedulers/` — Scheduling algorithms

Four primary algorithms and one control baseline behind a common interface. Schedulers see only
`estimated_duration`; the engine executes the hidden `actual_duration` (enforced by
`tests/test_no_actual_duration_leak.py`).

| File | Algorithm | Dispatch model | Uses task size? |
|---|---|---|---|
| `base.py` | Abstract `Scheduler`; `PerWorkerQueueScheduler` (`select_worker` on arrival); `CentralQueueScheduler` (`add_task`, `pop_next_task` when a worker is idle, shared `select_idle_worker`) | — | — |
| `round_robin.py` | **Round Robin (RR)** — strict rotation W1, W2, W3, …; skips unavailable/full workers | Per-worker FIFO queues | No |
| `weighted_round_robin.py` | **Weighted Round Robin (WRR)** — smooth (Nginx-style) WRR, default weights 5:3:2 | Per-worker FIFO queues | No |
| `least_loaded.py` | **Least Loaded (LL)** — lowest estimated remaining work ÷ capacity | Per-worker FIFO queues | Estimates |
| `shortest_job_first.py` | **Shortest Job First (SJF)** — non-preemptive, min-heap on `(estimated_duration, arrival_time, task_id)`, fastest idle worker first | Central queue | Estimates |
| `fcfs_baseline.py` | **FCFS — control baseline**, not a fifth algorithm: same central queue and worker selection as SJF, arrival order | Central queue | No |
| `__init__.py` | Registry: `ALGORITHMS` (the four primaries), the control, `create_scheduler()` | — | — |

**SJF − FCFS** isolates the effect of shortest-first ordering; **FCFS − RR/WRR/LL** isolates the
central queue and worker choice. FCFS is reported as "FCFS (control)" and excluded from every
ranking.

Details and tie-breaking rules: [`docs/design.md`](../../docs/design.md) and the
[scheduler README §3](../../README.md#3-scheduling-algorithms).
