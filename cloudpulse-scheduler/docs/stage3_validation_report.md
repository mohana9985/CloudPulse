# Stage 3 — Fairness and Reliability Validation Report

> **Historical record.** This report describes the project at the end of Stage 3, before the FCFS
> control baseline existed. Its test counts (194) and "4 algorithms" refer to that point. In Stage 4
> FCFS was added and included in the fairness, no-leak and hand-calculated tests; the current suite
> has **220** tests. The open decision at the end of this report was resolved by adding FCFS as a
> control (see `methodology.md` §2). The validation script still runs unchanged:
> `.venv/bin/python -m scripts.validate_stage3`.

Environment: macOS (Apple Silicon M1), Python 3.11.13 (`.venv`), pytest 9.2.0.
Commands:
```
.venv/bin/python -m pytest                       # 194 passed
.venv/bin/python -m scripts.validate_stage3      # output: docs/stage3_validation_output.txt
```
Default config: workers W1/W2/W3, capacity 1.0/0.6/0.4, WRR weights 5:3:2, seed 42,
target utilisation 0.85, estimate error ±20 %.

## Results by requirement
| # | Requirement | How verified | Actual result |
|---|---|---|---|
| 1 | Identical inputs | `run_comparison()` hashes the workload and worker config (SHA-256) up front and checks every run's own hash. Tests: fingerprint changes if any field changes; records match the input exactly | One workload hash per size (n=100 `7bf341a7668e`, 250 `e803772e9c3e`, 500 `174fca9bf17e`) and one worker hash `c053575c54b4` across all 4 algorithms |
| 2 | Determinism | 10 repeats per algorithm; 3 separate Python processes with `PYTHONHASHSEED` 0 / 1 / 12345 | 1 distinct result digest per algorithm; identical across processes |
| 3 | Sizes 100/250/500 | Every invariant and metric check × 4 algorithms × 3 sizes, plus 4 extra seeds at n=250 | All pass |
| 4 | Exactly-once | Independent checker `tests/invariants.py` (duplicates, missing, unknown tasks) plus the engine's own guards | 0 violations in all 12 combinations |
| 5 | No overlap per worker | Checker sorts each worker's intervals and checks start ≥ previous end | 0 violations |
| 6 | Metric correctness | (a) 4 full traces calculated by hand (`test_hand_calculated.py`); (b) reference metrics recomputed from raw records with separate code | (a) match exactly; (b) max abs difference 0.00e+00 in all 12 combinations |
| 7 | Hybrid design | Added `idle_while_waiting_time` diagnostic; limitations written in `docs/design.md` | SJF 0.0; LL ≤ 0.5 %; WRR 15.3–18.7 %; RR 14.7–27.7 % of capacity-time |
| 8 | SJF, heterogeneous workers and estimates | Hand traces with capacity 1.0/0.5 and a deliberately wrong estimate | Orders by estimate; shortest task goes to fastest idle worker; non-preemptive; non-delay greedy behaviour confirmed |
| 9 | Edge cases | Unavailable W2, 100-task burst at t=10, 150 % overload, overload + `max_queue_length=2`, empty | All tasks complete, 0 violations; W2 gets 0 tasks; empty gives 0 records and makespan 0 |
| 10 | No use of actual duration | (a) Runtime spy: instrumented `Task`/`Worker` flag any read of `actual_duration`, `execution_time()` or `current_end` inside scheduler methods; (b) a deliberately cheating scheduler is caught; (c) static scan of `src/schedulers/`; (d) counterfactual: scramble actual durations, decisions unchanged | 0 violations for all 4 algorithms; cheat detected; static scan clean; RR/WRR assignments, all t=0 decisions and single-worker SJF order unchanged |

Item 9 details (from the script output):
- W2 unavailable, n=250, tasks per worker [W1, W2, W3]:

  | Algorithm | W1 | W2 | W3 |
  |---|---|---|---|
  | RR | 125 | 0 | 125 |
  | WRR | 179 | 0 | 71 |
  | LL | 182 | 0 | 68 |
  | SJF | 190 | 0 | 60 |

  WRR's 179:71 matches the 5:2 weights of the remaining workers.
- 150 % overload, n=500: all 500 tasks complete for every algorithm. Peak queue (task count) is RR 153, WRR 141, LL 145, SJF 34.

## Issues discovered and fixes
| # | Issue | Type | Fix |
|---|---|---|---|
| 1 | No proof that each algorithm received identical inputs; it relied on code structure only | Gap | Added `workload_fingerprint`, `specs_fingerprint`, fingerprints stored in `SimulationResult`, and `src/experiment.run_comparison()`, which raises on any mismatch |
| 2 | The bias from the hybrid design could not be measured | Gap | Added the `idle_while_waiting_time` diagnostic to the engine, plus tests calculated by hand (RR = 9.0 worker-seconds, SJF = 0) |
| 3 | Overload test failed for SJF: `assert 34 > 50` on peak queue length | Wrong assumption in the test, **not an engine bug** | Investigated: at the last arrival, about 1,320 work units are waiting under every algorithm (RR 1324.1, WRR 1246.6, LL 1303.0, SJF 1321.9). SJF holds fewer but larger tasks. The test now measures waiting *work* |
| 4 | The first draft of the SJF limitation test used a scenario that did not show the limitation | Test-design error, caught before running | Replaced with a correct non-delay greedy scenario |

No engine or algorithm defects were found. All 117 Stage 2 tests still pass unchanged.

## New files and changes in Stage 3
- `src/experiment.py` — `run_comparison()` (one shared workload, fingerprint check)
- `src/workload_generator.py` — added `workload_fingerprint()`
- `src/worker.py` — added `specs_fingerprint()`
- `src/simulation_engine.py` — `SimulationResult` gains `idle_while_waiting_time`, `workload_fingerprint`, `worker_config_fingerprint`
- `tests/invariants.py` — independent schedule checker and reference metrics
- `tests/test_fairness.py` (55), `tests/test_hand_calculated.py` (9), `tests/test_no_actual_duration_leak.py` (13)
- `scripts/validate_stage3.py` and `docs/stage3_validation_output.txt`
- `docs/design.md` — limitations section

## Test totals (actual run)
| File | Tests |
|---|---|
| test_fairness | 55 |
| test_simulation | 44 |
| test_workload_generator | 23 |
| test_weighted_round_robin | 16 |
| test_no_actual_duration_leak | 13 |
| test_metrics | 10 |
| test_hand_calculated | 9 |
| test_least_loaded | 9 |
| test_shortest_job_first | 9 |
| test_round_robin | 6 |
| **Total** | **194 passed, 0 failed (0.86 s)** |

## Open decision for Stage 4
Whether to add a **central-queue FCFS control baseline** (not one of the 4 algorithms, labelled as a control).
It would separate the effect of SJF's shortest-first ordering from its late-binding advantage.
