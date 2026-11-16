# `tests/` — Scheduler test suite

**266 pytest tests** (parametrised), all passing on Python 3.11: 220 for the simulator and 46
for the live cluster (`live/`).

```bash
cd cloudpulse-scheduler
.venv/bin/python -m pytest          # expected: 266 passed
```

Windows (PowerShell) — see the [translation table](../../README.md#windows-powershell):

```powershell
cd cloudpulse-scheduler
.venv\Scripts\python -m pytest       # expected: 266 passed
```

| File | Tests | Covers |
|---|---|---|
| `test_round_robin.py` | 6 | Rotation order, skipping unavailable/full workers |
| `test_weighted_round_robin.py` | 16 | Smooth 5:3:2 sequence, weight proportions, weight overrides and validation, unavailable/full workers |
| `test_least_loaded.py` | 9 | Estimated-load choice, capacity adjustment, tie-breaking |
| `test_shortest_job_first.py` | 9 | Ordering by estimate, fastest idle worker, non-preemption |
| `test_fcfs_baseline.py` | 10 | Arrival order; identical to SJF when all estimates are equal |
| `test_simulation.py` | 44 | Event engine: exactly-once completion, timing invariants, one task at a time per worker, determinism, no state leak, same-instant event order, input validation |
| `test_fairness.py` | 55 | Identical inputs and fingerprints, fresh workers per run, determinism across processes, invariants and reference metrics at scale, overload, queue limits, unavailable worker, bursts |
| `test_hand_calculated.py` | 10 | Full traces checked against hand calculations |
| `test_metrics.py` | 10 | Hand-computed metrics, utilisation with idle gaps and capacity, per-worker shares, imbalance, empty workload |
| `test_no_actual_duration_leak.py` | 15 | Runtime spy, cheating-scheduler detection, static scan, counterfactual |
| `test_workload_generator.py` | 23 | Seeded generation, size mix, estimates, save/load, fingerprints |
| `test_experiment_runner.py` | 13 | Grid size and determinism, shared workloads, mean/SD aggregation, primary-only ranks, paired FCFS vs SJF, exporter files, CLI (incl. grid with charts) |
| `test_live_tasks.py` | 12 | Real task functions: determinism, validation, calibrated estimate model |
| `test_live_cluster.py` | 15 | Coordinator core: submission/status, each algorithm genuinely called, heartbeat registration, configurable unavailable/failed timeouts, recovery, interrupted-task retry and reassignment, retry limit (task marked failed, never lost), stale results, counters/metrics |
| `test_live_services.py` | 19 | FastAPI coordinator + worker apps in-process (TestClient): REST API, Prometheus `/metrics`, worker heartbeat/poll/result cycle with real execution, dashboard API client, end-to-end runs for all five configurations including a worker outage |
| `conftest.py` | — | Shared fixtures |
| `invariants.py` | — | Independent schedule checker and reference metric calculator (also used by `scripts/validate_stage3.py`) |

Validation write-up: [`docs/stage3_validation_report.md`](../docs/stage3_validation_report.md).
