# `src/` — Simulator source

Python package for the discrete-event scheduling simulator. Run it as a module from
`cloudpulse-scheduler/`: `.venv/bin/python -m src.main --help`.

| File | Responsibility |
|---|---|
| `main.py` | Command-line interface: single algorithm, `--algorithm all`, `--grid`, workload save/load, overrides |
| `config.py` | Loads `config/scheduler_config.yaml` into typed, validated objects |
| `workload_generator.py` | Frozen `Task`, `WorkloadConfig`, seeded Poisson arrivals and task sizes, estimated vs actual duration, CSV/JSON save/load, SHA-256 fingerprint |
| `worker.py` | Frozen `WorkerSpec` and runtime `Worker` (FIFO queue, busy time, estimated load) |
| `simulation_engine.py` | Event heap (`ARRIVAL`, `COMPLETION`), dispatch, exactly-once guards, idle-while-waiting diagnostic |
| [`schedulers/`](schedulers/README.md) | RR, WRR, LL, SJF and the FCFS control |
| `experiment.py` | `run_comparison` (all configurations on one frozen workload, fingerprint check) and `run_grid` |
| `metrics.py` | Per-run metrics: waiting, turnaround, response, p95/max wait, makespan, throughput, utilisation, load distribution, per class and per worker |
| `analysis.py` | Mean ± sample SD over seeds, ranks and wins (primaries only), paired SJF − FCFS deltas |
| `results_exporter.py` | Writes `results/<id>/` CSV, JSON and Markdown |
| `charts.py` | Writes `charts/<id>/` PNG charts |

Design: [`docs/design.md`](../docs/design.md) · Metrics: [`docs/methodology.md`](../docs/methodology.md)
