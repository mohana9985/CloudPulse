# CloudPulse Scheduler — Simulation Design

How the simulator is built and why. For the experiment plan see `methodology.md`; for results see
`stage4_results.md`; for an overview and run commands see the top-level `README.md`.

## Fairness guarantees
| Held identical across all five configurations (4 primaries + FCFS control) | How |
|---|---|
| Task list (arrivals, actual + estimated durations, types) | Generated once from one seed; `Task` is a frozen dataclass |
| Worker capacities, weights, availability | Same `WorkerSpec` list; fresh `Worker` objects built per run |
| Simulated clock | Starts at 0; same event engine and ordering rules |
| Metric definitions | One `compute_metrics()` for every algorithm |

## Two dispatch models
| | Per-worker FIFO queues (RR, WRR, LL) | Central queue (SJF; FCFS control) |
|---|---|---|
| When the decision is made | On task **arrival** | When a worker becomes **idle** |
| What is decided | Which worker gets the task | Which waiting task runs next (+ which idle worker) |
| Where tasks wait | That worker's own FIFO queue (never moved) | One shared queue. SJF: min-heap on `(estimated_duration, arrival_time, task_id)`. FCFS: FIFO on `(arrival_time, task_id)` |
| Order inside the queue | First come, first served | SJF: shortest estimated job first. FCFS: arrival order |
| Uses task size? | RR/WRR: no. LL: yes (estimates, via load) | SJF: yes (estimates). FCFS: no |

Why: LL can only "see" load if each worker owns a backlog. SJF can only pick "the shortest available task"
if tasks wait centrally. With a central queue for all algorithms, LL would collapse to "any idle worker".

Backlog: if every worker is unavailable or at `max_queue_length`, RR/WRR/LL tasks wait in an engine FIFO
backlog and are retried after every event batch. Default config has no queue limit.

## FCFS control baseline
`src/schedulers/fcfs_baseline.py` has `role = "control"`. It is registered in `CONTROL_BASELINES`, not in
`ALGORITHMS`, which holds exactly the four primary algorithms. Rankings skip it.

FCFS inherits `CentralQueueScheduler.select_idle_worker` (fastest idle worker, ties to the lowest config
index). SJF uses the same method, so the two differ only in queue order. A test checks that their schedules
are identical when all estimates are equal. The reasoning is in `docs/methodology.md` §2.

## Event rules
1. Events: `ARRIVAL`, `COMPLETION`, in a heap by `(time, kind, seq)`; at equal times completions go first.
2. All events at one timestamp are applied, then one dispatch step runs.
3. Simultaneous arrivals are processed in `task_id` order.
4. Execution time = `actual_duration / capacity`; non-preemptive.
5. Engine raises if a task starts or completes twice, or if any task is unfinished.

## Tie-breaking (deterministic)
| Algorithm | Rule |
|---|---|
| RR | Pointer order; skips unavailable/full workers |
| WRR | Highest smooth current weight; tie → lowest config index |
| LL | Lowest load (rounded to 1e-9); tie → lowest config index |
| SJF task | `(estimated_duration, arrival_time, task_id)` |
| SJF worker | Highest capacity; tie → lowest config index |
| FCFS task | Arrival order; simultaneous arrivals in `task_id` order |
| FCFS worker | Same method as SJF (`select_idle_worker`) |

## Assumptions
- Durations are simulated seconds on a capacity-1.0 reference worker.
- Schedulers see `estimated_duration` = actual × U(0.8, 1.2) by default; the engine runs `actual_duration`.
- Arrivals: Poisson, rate = `target_utilisation × total_capacity / mean_duration` (default 0.85).
- Response time = waiting time (non-preemptive: first run is the only run).
- Worker utilisation = simulated busy time / makespan. **Not** EC2 CPU or memory.
- Worker availability is static for a run.

## Limitations of the hybrid design (for academic comparison)
Validated in Stage 3; see `docs/stage3_validation_report.md`.

1. **Early vs late binding is confounded with the ordering policy.** RR/WRR/LL commit a task to a worker
   on arrival; SJF decides when a worker is free and therefore sees more information. Part of any SJF
   advantage comes from *late binding*, not from *shortest-first ordering*. Measured diagnostic:
   `idle_while_waiting_time` (worker-seconds an available worker sat idle while a task waited elsewhere)
   is 0 for SJF by construction, but 14.7–27.7 % of capacity-time for RR and 15.3–18.7 % for WRR on the
   Stage 3 seed-42 workloads (LL 0.0–0.5 %). Over the Stage 4 grid (mean per cell): RR 22.0–29.9 %,
   WRR 7.7–18.1 %, LL 0.2–0.3 %, SJF and FCFS 0.
   **Resolved in Stage 4** with the FCFS control. In the experiment grid, FCFS and LL give almost the same
   results (e.g. 500 tasks, ρ = 0.85: average wait 42.55 vs 42.41 s), so for LL the late-binding effect
   is small. For RR and WRR it is large. SJF − FCFS isolates the ordering effect.
2. **No work stealing / rebalancing.** A task queued on a slow worker stays there even if a fast worker
   becomes idle. This is realistic for push-based dispatch, but it penalises RR and WRR.
3. **SJF worker choice is capacity-aware but not size-aware.** The shortest task goes to the fastest idle
   worker. SJF is non-delay greedy: it never waits for a faster worker, even when waiting would finish
   sooner (test `test_sjf_is_non_delay_greedy_on_heterogeneous_workers`). RR, WRR and LL do not use
   capacity when ordering tasks inside a queue.
4. **Information asymmetry.** RR/WRR use no task-size information. LL and SJF use estimates (±20 %
   uniform, unbiased noise). Real estimates are often biased; the results depend on this noise model.
5. **Starvation.** SJF can delay large tasks indefinitely under sustained load (no ageing), so max waiting
   time and large-task turnaround must be reported next to the averages.
6. **Single-seed results are one sample.** The Stage 3 validation used seeds 1, 7, 42 and 2024 for
   integrity checks only. The Stage 4 grid uses 10 seeds (42–51) and reports mean ± SD, win counts and
   paired differences; 10 seeds still give only moderate confidence and no formal tests are run.
7. **Model simplifications.** Availability is static; there is no dispatch, network or context-switch
   overhead; arrivals are Poisson; worker speed is constant; a worker runs exactly one task at a time.
8. **Floating-point timestamps.** Events are batched by exact float equality. Two completions that are
   mathematically simultaneous but differ by rounding are handled in separate, consecutive batches.
   This is deterministic and has negligible effect.
9. **WRR with queue limits.** The smooth-WRR counter of a full worker is frozen while that worker is
   skipped, so it may get a short burst when it becomes eligible again. This only applies when
   `max_queue_length` is set (it is off by default).
10. **Queue-length sampling.** `peak_queue_length` and `avg_queue_length` are measured after each
    dispatch step, so tasks that arrive and start at the same instant count as zero waiting.
