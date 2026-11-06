# `scripts/` — Validation scripts

| File | Purpose |
|---|---|
| `validate_stage3.py` | Prints Stage 3 integrity and fairness evidence: workload/worker fingerprints, determinism digests, exactly-once and no-overlap checks, reference-metric comparison, edge cases, idle-while-waiting. It does not rank algorithms |
| `__init__.py` | Makes the folder importable so the script runs as a module |

```bash
cd cloudpulse-scheduler
.venv/bin/python -m scripts.validate_stage3
```

Recorded output: [`docs/stage3_validation_output.txt`](../docs/stage3_validation_output.txt);
explanation: [`docs/stage3_validation_report.md`](../docs/stage3_validation_report.md).
