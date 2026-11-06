# `config/` — Scheduler configuration

| File | Purpose |
|---|---|
| `scheduler_config.yaml` | Default settings for every run, loaded and validated by `src/config.py` |

Sections:

| Section | Settings |
|---|---|
| `experiment` | Default `seed` (42) and `num_tasks` (100); `grid` = sizes `[100, 250, 500]`, seeds 42–51, loads underloaded 0.50 / nominal 0.85 / overloaded 1.20 |
| `workload` | `target_utilisation` 0.85, `estimate_error` 0.20 (±20 %), size mix small/medium/large 0.6/0.3/0.1, size ranges [1, 5] / [5, 20] / [20, 60] simulated seconds |
| `workers` | W1/W2/W3 with capacity 1.0/0.6/0.4 and WRR weights 5:3:2; optional `available` and `max_queue_length`. List order is the tie-break order |

Most values can be overridden on the command line (`--seed`, `--tasks`, `--load`, `--workers`,
`--capacities`, `--weights`, `--size-mix`, `--estimate-error`); run
`.venv/bin/python -m src.main --help` from `cloudpulse-scheduler/`.

Changing this file changes future runs only; the reported results in
[`results/stage4-grid/`](../results/stage4-grid/README.md) were produced with the values above.
