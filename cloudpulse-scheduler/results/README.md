# `results/` — Experiment outputs

Every run writes to `results/<experiment-id>/` (produced by `src/results_exporter.py`). Without
`--experiment-id` the folder name is a UTC timestamp. Only the reported grid is tracked in Git;
other generated folders are ignored by `../.gitignore`.

| Path | Contents |
|---|---|
| [`stage4-grid/`](stage4-grid/README.md) | The verified Stage 4 grid: 450 runs (3 sizes × 3 loads × 10 seeds × 5 configurations) |

Matching charts are in [`../charts/`](../charts/README.md).
