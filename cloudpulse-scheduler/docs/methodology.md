# Experiment Methodology

What was measured and how the comparison is kept fair. Implementation details are in `design.md`;
the findings are in `stage4_results.md`.

## 1. Research questions
1. **Worker selection.** On identical workloads, how do Round Robin (RR), Weighted Round Robin (WRR) and Least Loaded (LL) compare when each task is bound to a worker on arrival?
2. **Task ordering.** What does Shortest Job First (SJF) change, and at what cost to large tasks?
3. **Sensitivity.** How do these effects change with offered load (under, near and over capacity) and workload size?

## 2. Configurations
| Name | Role | Dispatch model | Uses task-size information? | Worker choice |
|---|---|---|---|---|
| RR | primary | per-worker FIFO queue (bind on arrival) | no | rotation |
| WRR | primary | per-worker FIFO queue | no (static weights 5:3:2) | smooth weighted rotation |
| LL | primary | per-worker FIFO queue | estimates (queued + running work ÷ capacity) | least estimated load |
| SJF | primary | central priority queue (bind when idle) | estimates | fastest idle worker |
| **FCFS** | **control baseline** | central FIFO queue (bind when idle) | no | fastest idle worker (same code as SJF) |

### Why FCFS is included as a control
Stage 3 found that SJF differs from RR, WRR and LL in **two** ways at once:
- it orders tasks by estimated size;
- it binds tasks to workers *late* (only when a worker is free).

So a raw SJF-vs-LL difference cannot say which of these caused it. FCFS shares SJF's central queue, late binding and worker-selection code (`CentralQueueScheduler.select_idle_worker`). It differs **only** in queue order: arrival order instead of estimated size. Therefore:
- **SJF − FCFS** = the effect of shortest-job ordering alone;
- **FCFS − {RR, WRR, LL}** = the effect of late binding plus worker choice, with no task-size ordering.

FCFS is not a fifth algorithm under study. It is excluded from every ranking and is labelled "FCFS (control)" with grey hatched bars in every chart.

### Why FCFS vs SJF is a useful comparison
The comparison is **paired**: on every seed, both run the identical workload on identical workers. So the per-seed difference removes workload-to-workload variance, which is large here (see the SDs). For each cell the report gives the mean ± SD of the paired difference and the number of seeds in which SJF was lower or higher. It also compares waiting time **per task class** (small, medium, large), because SJF's average gain comes from making large tasks wait. The per-class view exposes that trade-off; a single average would hide it.

## 3. Experimental design
| Factor | Levels |
|---|---|
| Workload size | 100, 250, 500 tasks |
| Load condition (target utilisation ρ of total capacity) | underloaded 0.50, nominal 0.85, overloaded 1.20 |
| Seeds | 42–51 (10 seeds) |
| Configurations | RR, WRR, LL, SJF + FCFS control |
| **Total runs** | 3 × 3 × 10 × 5 = **450** |

- **Workers (fixed):** W1, W2, W3 with capacity 1.0 / 0.6 / 0.4 and WRR weights 5 / 3 / 2.
- **Task mix:** 60 % small U(1, 5) s, 30 % medium U(5, 20) s, 10 % large U(20, 60) s, in reference-worker seconds.
- **Estimates:** actual × U(0.8, 1.2). Only LL and SJF read them; the engine executes the actual duration.
- **Arrivals:** Poisson, with rate = ρ × total capacity / mean task size (total capacity 2.0, mean task
  size 9.55 s, so ≈ 0.105 / 0.178 / 0.251 tasks per second for ρ = 0.50 / 0.85 / 1.20).
- **Overload:** with ρ = 1.2, arrivals outpace capacity, so a backlog builds up. The workload is finite, so the system drains after the last arrival and every task still completes. "Overloaded" therefore means a growing backlog during the arrival period, not an infinite queue.

Reproduce:
```
.venv/bin/python -m src.main --grid --experiment-id stage4-grid
```
Run from the `cloudpulse-scheduler/` folder. This overwrites the reported outputs: results go to `results/stage4-grid/` and charts to `charts/stage4-grid/`. A rerun reproduces every metric value exactly; only the timestamp changes.

## 4. How workload fairness is maintained
1. **One workload per cell.** Each (size, load, seed) cell generates its workload once. `run_comparison()` freezes it into a tuple and passes the same object to all five configurations.
2. **Immutable inputs.** `Task` and `WorkerSpec` are frozen dataclasses. Each run builds fresh `Worker` objects, so no state carries over between algorithms.
3. **Fingerprints.** A SHA-256 hash of the full workload and of the worker configuration is computed before the runs and again inside each engine run. Any mismatch raises an error. Every row of `results.csv` carries both fingerprints, and `experiment_summary.json` lists all 90 workload fingerprints. The FCFS-vs-SJF pairing re-checks them.
4. **Same simulation model.** All five configurations use the same event engine, clock (starting at t = 0), tie-breaking rules and metric code.
5. **No foreknowledge.** Stage 3 tests (runtime spy, static scan, counterfactual) show that schedulers never read actual durations or future completion times. FCFS is included in those tests.
6. **Multiple seeds.** Results are reported as mean (`statistics.fmean`) ± sample SD (`statistics.stdev`, n − 1) over 10 seeds, together with "wins" (the number of seeds in which an algorithm was best). One random workload is never the basis of a conclusion.

## 5. Metrics
All metrics are in simulated seconds unless stated. Response time equals waiting time because execution is non-preemptive.

| Metric | Definition | Better |
|---|---|---|
| Average / max / p95 waiting time | start − arrival (p95 uses nearest rank) | lower |
| Average turnaround time | completion − arrival | lower |
| Average response time | first execution − arrival (= waiting time) | lower |
| Makespan | last completion − 0 | lower |
| Throughput | tasks ÷ makespan (simulated time, never wall-clock) | higher |
| Mean worker utilisation | mean over available workers of busy time ÷ makespan | context: see §6 |
| Utilisation imbalance (CV) | population SD ÷ mean of per-worker utilisation | lower (more even) |
| Idle-while-waiting | worker-seconds in which a free worker sat idle while some task waited, ÷ (makespan × available workers) | lower |
| Load distribution | per-worker shares of tasks, work and busy time | compare with capacity share |
| Per-class waiting | the waiting metrics above, per small / medium / large task class | — |

Ranking uses the primary algorithms only, with competition ranking on the means. "Wins" counts the seeds in which an algorithm had the best value; ties share the win. Where SDs overlap heavily (e.g. makespan when underloaded), a rank difference is not meaningful and the report says so.

## 6. Simulated worker utilisation is not EC2 CPU utilisation
- **What it measures.** A simulated worker is "busy" from task start to task end on the **simulated** clock. Utilisation is that busy time divided by the simulated makespan. It describes the scheduling model, not the computer running it.
- **What the hardware actually did.** The 450 runs together take about 1.6 s of real time on one CPU core of the M1 (under 2 s in the logs). The machine's CPU and memory usage during the experiment has no relationship to the simulated utilisation figures. On EC2, real CPU and memory come from Prometheus or node metrics and must be reported separately.
- **Higher is not automatically better.** The same work occupies a slow worker for longer. A policy that sends too much work to slow workers (RR) therefore shows high utilisation on those workers *and* the worst waiting times. Utilisation should be read alongside waiting time and the per-worker chart.

## 7. Limitations
See `docs/design.md` §Limitations for the full list. The main ones:
1. The hybrid queue architecture binds RR/WRR/LL early and SJF/FCFS late. The FCFS control quantifies this effect.
2. There is no work stealing between per-worker queues.
3. Estimate noise is assumed unbiased (±20 % uniform).
4. Worker speeds and availability are static, and there is no dispatch or network overhead.
5. SJF has no ageing, so it can starve large tasks.
6. Ten seeds give useful but not tight confidence. No formal hypothesis tests are run; the report uses paired differences and win counts instead.
