# `charts/` — Comparison charts

Every run writes PNG charts to `charts/<experiment-id>/` (produced by `src/charts.py` with
matplotlib). Only the reported grid charts are tracked in Git; other generated folders are ignored
by `../.gitignore`.

| Path | Contents |
|---|---|
| [`stage4-grid/`](stage4-grid/README.md) | The 10 charts for the verified Stage 4 grid (**SIMULATED**) |
| `live-mac-20261112/` | 12 charts from the **REAL execution** results (`live/experiments/live_charts.py`): 01–06 turnaround/wait/throughput/makespan/max-wait/overhead by workload size, 07 task share per worker, 08 measured CPU, 09 measured memory, 10 failure vs normal, 11–12 scaling on 1/2/3 workers |

Underlying numbers: [`../results/`](../results/README.md).
