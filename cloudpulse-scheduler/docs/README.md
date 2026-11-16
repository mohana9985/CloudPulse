# `cloudpulse-scheduler/docs/` — Scheduler documentation

| Document | Contents |
|---|---|
| [`design.md`](design.md) | Simulation design: fairness guarantees, dispatch models, event ordering, tie-breaking, assumptions, limitations of the hybrid design |
| [`methodology.md`](methodology.md) | Research questions, the five configurations, why FCFS is a control, experimental grid, fairness, metric definitions |
| [`stage3_validation_report.md`](stage3_validation_report.md) | Stage 3 fairness and reliability validation (historical record, 194 tests at that point) |
| [`stage3_validation_output.txt`](stage3_validation_output.txt) | Raw output of `python -m scripts.validate_stage3` |
| [`stage4_results.md`](stage4_results.md) | Complete Stage 4 findings for all 9 (size × load) cells |
| [`stage4_grid_terminal_output.txt`](stage4_grid_terminal_output.txt) | Raw terminal output of the 450-run grid (local absolute paths redacted to `<repo>/`) |
| [`cost_analysis.md`](cost_analysis.md) | Infrastructure cost per configuration (1/2/3 hosts), cost of the recorded experiments, performance/reliability/cost trade-offs |
| [`demo_guide.md`](demo_guide.md) | Step-by-step demonstration script for macOS: tests, start the cluster, compare algorithms, kill/restart a worker, Prometheus/Grafana, recorded results |
| [`live_results.md`](live_results.md) | **REAL execution** results of the live cluster (`../live/`): algorithm grid, worker failure/recovery, 1/2/3-worker scaling, measured CPU/memory and overhead on one Docker host |

Times in the Stage 3/4 documents are **simulated seconds** and utilisation is simulated worker
busy time. `live_results.md` reports **real wall-clock measurements** from Docker worker
containers; the two are never mixed. Live architecture and API: [`../live/README.md`](../live/README.md).

Overview and commands: [scheduler README](../README.md).
