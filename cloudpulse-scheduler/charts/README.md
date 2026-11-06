# `charts/` — Comparison charts

Every run writes PNG charts to `charts/<experiment-id>/` (produced by `src/charts.py` with
matplotlib). Only the reported grid charts are tracked in Git; other generated folders are ignored
by `../.gitignore`.

| Path | Contents |
|---|---|
| [`stage4-grid/`](stage4-grid/README.md) | The 10 charts for the verified Stage 4 grid |

Underlying numbers: [`../results/`](../results/README.md).
