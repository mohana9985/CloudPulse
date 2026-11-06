# Stage 4 — Experiment Results and Findings

The complete findings of the experiment grid, cell by cell. The README gives a shorter summary;
`methodology.md` explains the design and the metrics.

Source of every number: `results/stage4-grid/` (`algorithm_comparison.csv`, `fcfs_vs_sjf.csv`, `results.csv`).
Full tables are in `results/stage4-grid/comparison_tables.md` and charts in `charts/stage4-grid/`.

**Setup:** 450 runs = 3 sizes × 3 loads × 10 seeds (42–51) × 5 configurations.
- Workers W1 / W2 / W3 with capacity 1.0 / 0.6 / 0.4 and WRR weights 5:3:2.
- 90 distinct workload fingerprints, one per (size, load, seed); worker fingerprint `c053575c54b4` for all runs.
- Wall-clock time 1.64 s, informational only.

Values are given as mean ± sample SD over 10 seeds, in simulated seconds. "Wins" = number of seeds (out of 10) in which an algorithm was best among the four primaries.

## 1. Headline table — 500 tasks (average waiting time / maximum waiting time, seconds)
| | Underloaded ρ=0.50 | Nominal ρ=0.85 | Overloaded ρ=1.20 |
|---|---|---|---|
| RR | 54.25 ± 33.67 / 435.04 | 266.74 ± 83.89 / 1389.33 | 477.06 ± 79.86 / 2110.92 |
| WRR | 12.62 ± 2.78 / 166.69 | 72.03 ± 33.15 / 359.71 | 270.93 ± 58.35 / 731.08 |
| LL | 3.69 ± 1.88 / 53.11 | 42.41 ± 35.97 / 150.99 | 246.43 ± 57.01 / 543.97 |
| SJF | 2.46 ± 0.88 / 74.71 | 15.15 ± 7.89 / 502.67 | 58.44 ± 11.67 / 1952.46 |
| FCFS (control) | 3.61 ± 1.98 / 47.92 | 42.55 ± 36.16 / 143.60 | 245.74 ± 56.96 / 531.07 |

## 2. Best primary algorithm per metric (rank 1 on the mean)
| Metric | Result across the 9 (size × load) cells |
|---|---|
| Average waiting time | **SJF** in 9/9 cells; wins 10/10 seeds in 8 cells and 9/10 in the 100-task underloaded cell |
| Average turnaround time | **SJF** in 9/9 cells (8–10 wins per cell) |
| Average response time | Same as waiting time (non-preemptive): **SJF** in 9/9 |
| 95th-percentile waiting time | **SJF** in 9/9 cells |
| Maximum waiting time | **LL** in 9/9 cells. SJF is 2nd when underloaded but 3rd (behind WRR) at nominal 500 and in every overloaded cell |
| Makespan / throughput | **LL** in most cells, but the differences between LL, SJF and WRR are much smaller than the seed SD (e.g. 500 nominal: LL 2876 ± 120, SJF 2901 ± 118, WRR 2979 ± 127). When underloaded, makespan is set by the last arrival, so LL, SJF and FCFS are almost identical. **RR is clearly worst** at nominal and overloaded (500 nominal: 4154 ± 479) |
| Utilisation imbalance (CV) | **WRR** in all 3 underloaded cells; **LL** in 5 of the 6 nominal/overloaded cells (SJF at 100 tasks / nominal) |
| Mean worker utilisation | **LL** in all 6 nominal/overloaded cells; **RR** in all 3 underloaded cells, which is misleading (see §7) |
| Idle-while-waiting | SJF and FCFS are 0 by design. Among the push-dispatch algorithms: LL 0.2–0.3 %, WRR 7.7–18.1 %, RR 22.0–29.9 % |

No algorithm is best on every metric. SJF wins every *average* time metric but loses the *worst-case* metric. LL wins the worst case and is nearly tied for makespan.

## 3. Worker-selection policies (RR vs WRR vs LL)
- **RR is worst on every time metric in every cell.** It gives each worker one third of the tasks (task share 33 / 34 / 33 %), but W3 has only 20 % of the capacity. At ρ = 0.85, W3 therefore receives about 0.85 × (1/3) ÷ 0.2 ≈ 1.42 times the work it can process, so its queue grows throughout the arrival period. At 500 tasks / nominal, W3 is 97.7 % busy while W1 is 39.8 % busy. This shows up as the highest maximum waits (1389 s) and the longest makespan.
- **WRR splits work in proportion to capacity** (work share 50 / 31 / 19 % against capacity 50 / 30 / 20 %). That makes each worker's utilisation nearly equal and gives the lowest imbalance when underloaded. But it is static: it ignores how much work is actually queued. With random task sizes, one worker's queue can grow while another worker is idle (idle-while-waiting 7.7–18.1 %). So WRR ranks 3rd on average waiting time in all 9 cells.
- **LL uses estimated queued work** and almost never leaves a worker idle while tasks wait (≤ 0.3 %). It is 2nd on average wait (behind SJF) and 1st on maximum wait in every cell. Its advantage over WRR is largest when underloaded or at nominal load (500 nominal: 42.41 vs 72.03 s average wait) and shrinks under overload (246.43 vs 270.93 s), when every worker is busy most of the time anyway.

## 4. Effect of shortest-job ordering (FCFS control vs SJF, paired per seed)
Both use the same central queue and the same worker choice, so the difference measures queue ordering only.

| 500 tasks | Underloaded | Nominal | Overloaded |
|---|---|---|---|
| Average wait, SJF − FCFS | −1.15 ± 1.16 s (−31.8 %), SJF lower in 10/10 | −27.40 ± 28.42 s (−64.4 %), 10/10 | −187.30 ± 45.86 s (−76.2 %), 10/10 |
| p95 wait | −35.8 %, 10/10 lower | −51.9 %, 10/10 lower | −46.6 %, 10/10 lower |
| Max wait | +55.9 %, SJF higher in 10/10 | +250.1 %, 10/10 higher | +267.6 %, 10/10 higher |
| Large-task average wait | +45.1 %, SJF higher in 8/10 | +76.9 %, 10/10 higher | +86.0 %, 10/10 higher |
| Makespan | −0.0 % | +1.0 % | +1.4 % |

- **Shortest-first ordering cuts average waiting time sharply, and more so as load rises:** −21 % to −32 % when underloaded and −63 % to −76 % when overloaded, across all sizes. This comes from moving small and medium tasks forward.
- **The cost falls on large tasks.** Their average wait rises by 62–86 % at nominal and overloaded load, and the maximum wait rises 1.7–3.7× (500 overloaded: 531 → 1952 s). This is SJF starvation: with no ageing, a large task can be overtaken repeatedly while short tasks keep arriving.
- **Makespan is essentially unchanged**: SJF's change is between −0.0 % and +3.1 % across all 9 cells, and the paired SD is about the same size as the change. Ordering changes *who* waits, not how much total work there is.
- When underloaded the effect is small in absolute terms (≈ 1 s), because queues are rarely long enough for ordering to matter.

## 5. Late binding vs worker selection (FCFS vs the push algorithms)
- **FCFS and LL are nearly identical.** The mean paired difference in average wait is under 1 s in every cell (500 nominal: −0.14 s; per-seed range −4.5 % to +4.6 %). This is consistent with the queueing result that least-work-left dispatch with accurate size information behaves like a central FCFS queue. The ±20 % estimate noise causes the small differences. So for LL, binding early costs very little.
- **For RR and WRR, early binding is costly.** FCFS beats WRR on average wait in every cell (e.g. 500 nominal 42.55 vs 72.03 s). Idle-while-waiting shows why: a worker sits idle while tasks wait in another worker's queue.
- **Consequence for interpreting SJF:** because FCFS ≈ LL, almost all of SJF's average-wait advantage over LL is due to shortest-job *ordering*, not to the central-queue architecture. This answers the confound identified in Stage 3.

## 6. Where each algorithm performs better or worse
| Algorithm | Performs well when … | Performs poorly when … |
|---|---|---|
| RR | Workers are homogeneous (not tested here) and simplicity matters | Worker capacities differ: the slowest worker becomes a bottleneck at any load (worst in all 9 cells) |
| WRR | Weights match capacities and you want an even, predictable, size-blind split (lowest imbalance when underloaded) | Task sizes vary: static rotation cannot react to queue build-up (idle-while-waiting up to 18 %) |
| LL | You need good average *and* worst-case behaviour from push dispatch; makespan is best or near-best | Estimates are poor (not tested beyond ±20 %); under heavy overload its advantage over WRR shrinks |
| SJF | Mean waiting and turnaround matter most, especially at high load (−64 to −76 % vs FCFS at 500 tasks) | Fairness and tail latency matter: large tasks wait far longer; worst max wait at nominal/overloaded load among SJF, LL and WRR |

## 7. Variability and caveats
- Seed-to-seed SD is large (e.g. LL 500 nominal average wait 42.41 ± 35.97 s). Single-seed comparisons would be unreliable, which is why we report means over 10 seeds, win counts and paired differences.
- Rank differences in makespan and throughput between WRR, LL and SJF are smaller than the SD, so they should not be presented as meaningful.
- **Utilisation:** RR ranks 1st on mean utilisation when underloaded (57.0 % against LL's 49.4 %) only because it overloads the slow W3 (82.2 % busy) while W1 sits at 33.1 %. Mean simulated utilisation is not a measure of "better" scheduling, and it is not EC2 CPU usage.
- These results hold for this model: three heterogeneous workers, unbiased ±20 % estimates, Poisson arrivals, static availability and no overhead. See `docs/methodology.md` §7 and `docs/design.md` §Limitations.
