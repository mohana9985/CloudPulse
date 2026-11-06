# `cloudpulse-scheduler/docs/` — Scheduler documentation

| Document | Contents |
|---|---|
| [`design.md`](design.md) | Simulation design: fairness guarantees, dispatch models, event ordering, tie-breaking, assumptions, limitations of the hybrid design |
| [`methodology.md`](methodology.md) | Research questions, the five configurations, why FCFS is a control, experimental grid, fairness, metric definitions |
| [`stage3_validation_report.md`](stage3_validation_report.md) | Stage 3 fairness and reliability validation (historical record, 194 tests at that point) |
| [`stage3_validation_output.txt`](stage3_validation_output.txt) | Raw output of `python -m scripts.validate_stage3` |
| [`stage4_results.md`](stage4_results.md) | Complete Stage 4 findings for all 9 (size × load) cells |
| [`stage4_grid_terminal_output.txt`](stage4_grid_terminal_output.txt) | Raw terminal output of the 450-run grid (local absolute paths redacted to `<repo>/`) |

All times in these documents are **simulated seconds**, and utilisation is simulated worker busy
time — not EC2 CPU measurements.

Overview and commands: [scheduler README](../README.md).
