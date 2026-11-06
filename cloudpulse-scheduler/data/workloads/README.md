# `data/workloads/` — Saved workloads

Empty by default (only `.gitkeep` and this README are tracked). Use it to save a generated
workload and replay the identical task list with any algorithm.

```bash
cd cloudpulse-scheduler
.venv/bin/python -m src.main --generate-workload data/workloads/w100_s42.csv --tasks 100 --seed 42
.venv/bin/python -m src.main --algorithm all --workload data/workloads/w100_s42.csv
```

Each task stores its arrival time, task class, actual duration (hidden from schedulers) and
estimated duration. Saving and loading are implemented in `src/workload_generator.py`.
