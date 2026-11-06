import csv
import json
import statistics
import subprocess
import sys
from pathlib import Path

import pytest

from src.analysis import METRICS, aggregate, fcfs_vs_sjf
from src.experiment import GridSpec, run_grid
from src.main import main
from src.results_exporter import write_experiment
from src.schedulers import ALL_CONFIGURATIONS
from src.workload_generator import WorkloadConfig

ROOT = Path(__file__).resolve().parent.parent
SMALL_GRID = GridSpec(sizes=(60, 120), seeds=(1, 2, 3), loads=(("under", 0.5), ("over", 1.2)))


@pytest.fixture(scope="module")
def grid_rows():
    from tests.conftest import DEFAULT_SPECS
    return run_grid(WorkloadConfig(total_capacity=2.0), DEFAULT_SPECS, SMALL_GRID)


def test_grid_row_count_and_completion(grid_rows):
    assert len(grid_rows) == 2 * 2 * 3 * len(ALL_CONFIGURATIONS)
    for r in grid_rows:
        assert r["tasks_completed"] == r["workload_size"]


def test_every_cell_shares_one_workload_and_worker_config(grid_rows):
    cells = {}
    for r in grid_rows:
        cells.setdefault((r["workload_size"], r["load_condition"], r["seed"]), set()).add(r["workload_fingerprint"])
    assert all(len(fps) == 1 for fps in cells.values())
    assert len({next(iter(f)) for f in cells.values()}) == len(cells)
    assert len({r["worker_config_fingerprint"] for r in grid_rows}) == 1


def test_grid_is_deterministic(grid_rows):
    from tests.conftest import DEFAULT_SPECS
    again = run_grid(WorkloadConfig(total_capacity=2.0), DEFAULT_SPECS, SMALL_GRID)
    assert [r["avg_waiting_time"] for r in again] == [r["avg_waiting_time"] for r in grid_rows]


def test_aggregate_mean_std_match_manual(grid_rows):
    agg = aggregate(grid_rows)
    assert len(agg) == 2 * 2 * len(ALL_CONFIGURATIONS)
    e = next(a for a in agg if a["workload_size"] == 120 and a["load_condition"] == "over" and a["algorithm"] == "least_loaded")
    vals = [r["avg_waiting_time"] for r in grid_rows
            if r["workload_size"] == 120 and r["load_condition"] == "over" and r["algorithm"] == "least_loaded"]
    assert e["avg_waiting_time_mean"] == pytest.approx(statistics.fmean(vals))
    assert e["avg_waiting_time_std"] == pytest.approx(statistics.stdev(vals))
    assert e["n_seeds"] == 3


def test_ranks_primary_only_and_direction(grid_rows):
    agg = aggregate(grid_rows)
    assert all("avg_waiting_time_rank" not in a for a in agg if a["algorithm"] == "fcfs_baseline")
    for size in (60, 120):
        for load in ("under", "over"):
            cell = [a for a in agg if a["workload_size"] == size and a["load_condition"] == load and a["role"] == "primary"]
            for key, (_, _, direction) in METRICS.items():
                best = (min if direction == "lower" else max)(cell, key=lambda a: a[f"{key}_mean"])
                assert best[f"{key}_rank"] == 1
                assert sorted(a[f"{key}_rank"] for a in cell)[0] == 1
                assert sum(a[f"{key}_wins"] for a in cell) >= 3


def test_fcfs_vs_sjf_paired_deltas(grid_rows):
    rows = fcfs_vs_sjf(grid_rows)
    r = next(x for x in rows if x["workload_size"] == 60 and x["load_condition"] == "over" and x["metric"] == "avg_waiting_time")
    pairs = {}
    for g in grid_rows:
        if g["workload_size"] == 60 and g["load_condition"] == "over":
            pairs.setdefault(g["seed"], {})[g["algorithm"]] = g["avg_waiting_time"]
    deltas = [p["shortest_job_first"] - p["fcfs_baseline"] for p in pairs.values()]
    assert r["delta_mean"] == pytest.approx(statistics.fmean(deltas))
    assert r["seeds_sjf_lower"] + r["seeds_sjf_higher"] <= 3


def test_fcfs_vs_sjf_rejects_mismatched_workloads(grid_rows):
    tampered = [dict(r) for r in grid_rows]
    for r in tampered:
        if r["algorithm"] == "fcfs_baseline":
            r["workload_fingerprint"] = "x"
            break
    with pytest.raises(RuntimeError, match="mismatch"):
        fcfs_vs_sjf(tampered)


def test_exporter_writes_all_files(tmp_path, grid_rows):
    from tests.conftest import DEFAULT_SPECS
    meta = {"experiment_id": "t", "timestamp": "2026-01-01T00:00:00+00:00", "n_seeds": 3}
    agg = aggregate(grid_rows)
    files = write_experiment(tmp_path, meta, grid_rows, agg, fcfs_vs_sjf(grid_rows), DEFAULT_SPECS)
    for name in ("results.csv", "results.json", "algorithm_comparison.csv", "fcfs_vs_sjf.csv",
                 "per_worker.csv", "experiment_summary.json", "comparison_tables.md"):
        assert files[name].exists() and files[name].stat().st_size > 0, name
    rows = list(csv.DictReader(files["results.csv"].open()))
    assert len(rows) == len(grid_rows)
    assert {"experiment_id", "timestamp", "seed", "workload_size", "algorithm", "workload_fingerprint",
            "W1_utilisation_pct", "large_avg_waiting_time"} <= set(rows[0])
    summary = json.loads(files["experiment_summary.json"].read_text())
    assert summary["worker_config"][0]["worker_id"] == "W1"
    assert len(summary["workload_fingerprints"]) == 2 * 2 * 3
    assert all(b["best_algorithm"] != "fcfs_baseline" for b in summary["best_per_metric"])
    assert len(list(csv.DictReader(files["per_worker.csv"].open()))) == len(grid_rows) * 3


def test_cli_single_all(tmp_path, capsys):
    rc = main(["--algorithm", "all", "--tasks", "40", "--seed", "3", "--experiment-id", "cli",
               "--results-dir", str(tmp_path / "r"), "--charts-dir", str(tmp_path / "c"), "--no-charts"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "FCFS (control)" in out and "SJF" in out
    rows = list(csv.DictReader((tmp_path / "r" / "cli" / "results.csv").open()))
    assert {r["algorithm"] for r in rows} == set(ALL_CONFIGURATIONS)
    assert len({r["workload_fingerprint"] for r in rows}) == 1
    assert (tmp_path / "r" / "cli" / "task_records.csv").exists()


def test_cli_single_algorithm_and_custom_workers(tmp_path):
    rc = main(["--algorithm", "weighted_round_robin", "--tasks", "30", "--workers", "2", "--capacities", "1,0.5",
               "--weights", "2,1", "--experiment-id", "w", "--results-dir", str(tmp_path), "--no-charts"])
    assert rc == 0
    rows = list(csv.DictReader((tmp_path / "w" / "results.csv").open()))
    assert [r["algorithm"] for r in rows] == ["weighted_round_robin"]
    assert "W3_tasks_completed" not in rows[0]


def test_cli_workload_round_trip(tmp_path):
    wl = tmp_path / "w.csv"
    assert main(["--generate-workload", str(wl), "--tasks", "25", "--seed", "9"]) == 0
    assert main(["--algorithm", "all", "--workload", str(wl), "--experiment-id", "x",
                 "--results-dir", str(tmp_path), "--no-charts"]) == 0
    rows = list(csv.DictReader((tmp_path / "x" / "results.csv").open()))
    assert all(r["tasks_completed"] == "25" for r in rows)


def test_cli_rejects_mismatched_capacities(tmp_path):
    with pytest.raises(SystemExit):
        main(["--workers", "3", "--capacities", "1,1", "--results-dir", str(tmp_path), "--no-charts"])


def test_cli_grid_with_charts_subprocess(tmp_path):
    proc = subprocess.run(
        [sys.executable, "-m", "src.main", "--grid", "--sizes", "50", "--seeds", "1,2", "--experiment-id", "g",
         "--results-dir", str(tmp_path / "r"), "--charts-dir", str(tmp_path / "c")],
        cwd=ROOT, capture_output=True, text=True, check=True)
    assert "30 runs" in proc.stdout
    pngs = sorted(p.name for p in (tmp_path / "c" / "g").glob("*.png"))
    assert len(pngs) == 10 and "08_fcfs_vs_sjf.png" in pngs
    assert all((tmp_path / "c" / "g" / p).stat().st_size > 10_000 for p in pngs)
