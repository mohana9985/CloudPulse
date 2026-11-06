# `results/stage4-grid/` — Verified Stage 4 results

Output of the complete experiment grid:

```bash
cd cloudpulse-scheduler
.venv/bin/python -m src.main --grid --experiment-id stage4-grid   # overwrites this folder and charts/stage4-grid/
```

**450 runs** = sizes 100/250/500 × loads 0.50/0.85/1.20 × seeds 42–51 × 5 configurations
(RR, WRR, LL, SJF + FCFS control). Re-running reproduces every metric value exactly; only the
timestamp changes.

| File | Contents |
|---|---|
| `results.csv` | One row per run (450 rows), flat |
| `results.json` | Same runs, nested, with experiment settings |
| `algorithm_comparison.csv` | Mean, sample SD, rank and wins per (size, load, configuration) |
| `fcfs_vs_sjf.csv` | Paired per-seed SJF − FCFS differences |
| `per_worker.csv` | One row per run × worker (task, work and busy-time share, utilisation) |
| `experiment_summary.json` | Settings, worker configuration, all 90 workload fingerprints, metric definitions, best per metric |
| `comparison_tables.md` | Human-readable tables generated from the CSVs |

All times are **simulated seconds**; utilisation is simulated worker busy time, **not** EC2 CPU.
FCFS is a control baseline and is never ranked.

Discussion: [`docs/stage4_results.md`](../../docs/stage4_results.md) · Charts:
[`charts/stage4-grid/`](../../charts/stage4-grid/README.md)
