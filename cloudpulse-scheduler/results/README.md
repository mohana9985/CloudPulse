# `results/` — Experiment outputs

Every run writes to `results/<experiment-id>/` (produced by `src/results_exporter.py`). Without
`--experiment-id` the folder name is a UTC timestamp. Only the reported grid is tracked in Git;
other generated folders are ignored by `../.gitignore`.

| Path | Contents |
|---|---|
| [`stage4-grid/`](stage4-grid/README.md) | The verified Stage 4 grid: 450 runs (3 sizes × 3 loads × 10 seeds × 5 configurations) — **SIMULATED** seconds |
| `live-mac-20261112/` | **REAL execution** on the live cluster (one Docker host, Mac/Colima, 2026-11-12), produced by `live/experiments/run_live.py`: `runs_*.csv` (one row per run), `per_worker_*.csv`, `tasks_*.csv` (one row per task), `events_*.jsonl`, `*_summary.csv` (mean ± SD), `metadata*.json` (setup, worker quotas, git commit). Scenarios: `grid` (3 sizes × 3 seeds × 5 configs), `normal`/`failure` (W2 killed and restarted), `scaling` (1/2/3 workers). Findings: [`../docs/live_results.md`](../docs/live_results.md) |
| `live-mac-20261112.log` | Terminal log of the live runs (includes the restarts of interrupted stages) |

Matching charts are in [`../charts/`](../charts/README.md).
