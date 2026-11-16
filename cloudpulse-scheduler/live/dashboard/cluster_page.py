from __future__ import annotations

import os
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # so "live" imports when run by streamlit

from live.dashboard.api import CoordinatorClient, find_live_results, load_csv_rows, task_distribution  # noqa: E402

COORDINATOR_URL = os.environ.get("COORDINATOR_URL", "http://localhost:8100")
RESULTS_DIR = Path(os.environ.get("RESULTS_DIR", Path(__file__).resolve().parents[2] / "results"))
REFRESH = float(os.environ.get("DASHBOARD_REFRESH_SECONDS", 2))

@st.cache_resource
def coordinator_client() -> CoordinatorClient:
    return CoordinatorClient(COORDINATOR_URL)


api = coordinator_client()
st.title("CloudPulse — Compute Cluster (live scheduler)")
st.caption(f"Coordinator: `{COORDINATOR_URL}` · live data, refreshed every {REFRESH:g}s · "
           "CPU/memory are real psutil/cgroup measurements from each worker container")

with st.sidebar:
    st.header("Controls")
    try:
        algos = api.get("/scheduler/algorithms")
    except Exception as e:
        st.error(f"Coordinator unreachable: {e}")
        st.stop()
    names = [a["name"] for a in algos["algorithms"]]
    labels = {a["name"]: f'{a["display_name"]} ({a["dispatch_mode"].replace("_", " ")})' for a in algos["algorithms"]}
    choice = st.selectbox("Scheduling algorithm", names, index=names.index(algos["active"]),
                          format_func=lambda n: labels[n])
    if st.button("Apply algorithm", width="stretch"):
        try:
            api.set_algorithm(choice)
            st.success(f"Active: {choice}")
        except RuntimeError as e:
            st.error(str(e))

    st.subheader("Submit workload")
    n = st.number_input("Tasks", 1, 1000, 40)
    seed = st.number_input("Seed", 0, 10_000, 42)
    load = st.slider("Offered load (ρ)", 0.2, 2.0, 0.85, 0.05)
    if st.button("Start workload", width="stretch"):
        try:
            info = api.start_workload(int(n), int(seed), float(load))
            st.success(f"Submitting {info['num_tasks']} tasks over ~{info['duration_seconds']:.0f}s")
        except RuntimeError as e:
            st.error(str(e))
    if st.button("Reset run (archive summary)", width="stretch"):
        try:
            api.reset()
            st.success("Run archived")
        except RuntimeError as e:
            st.error(str(e))

    st.subheader("Failure demo")
    st.caption("Simulated outage = worker stops heartbeats/polling (network partition). "
               "For a real crash use `docker compose stop worker-2`.")
    try:
        wl = api.get("/workers")["workers"]
    except Exception:
        wl = []
    with_url = {w["worker_id"]: w["info"].get("url") for w in wl if w.get("info", {}).get("url")}
    if with_url:
        target = st.selectbox("Worker", sorted(with_url))
        secs = st.number_input("Outage seconds", 5, 300, 20)
        if st.button("Simulate outage", width="stretch"):
            try:
                api.simulate_outage(with_url[target], float(secs))
                st.warning(f"{target} partitioned for {secs}s")
            except Exception as e:
                st.error(str(e))


@st.fragment(run_every=REFRESH)
def live_panels() -> None:
    try:
        snap = api.snapshot()
    except Exception as e:
        st.error(f"Coordinator unreachable: {e}")
        return
    stats, workers, tasks = snap["stats"], snap["workers"], snap["tasks"]
    run = stats["run"]
    by = stats["tasks_by_status"]

    st.subheader(f"System overview — algorithm: {stats['algorithm']} · run #{run['run_id']}")
    c = st.columns(7)
    c[0].metric("Submitted", run["submitted"])
    c[1].metric("Completed", run["completed"])
    c[2].metric("Failed", run["failed"])
    c[3].metric("Pending/running", by["pending"] + by["queued"] + by["running"])
    c[4].metric("Avg exec (s)", "—" if run["avg_exec_seconds"] is None else f'{run["avg_exec_seconds"]:.3f}')
    c[5].metric("Throughput (tasks/s)", "—" if run["throughput_tasks_per_second"] is None
                else f'{run["throughput_tasks_per_second"]:.2f}')
    c[6].metric("Retries", run["retries"])

    tab_w, tab_t, tab_e, tab_c = st.tabs(["Workers", "Tasks", "Failures & events", "Algorithm comparison"])

    with tab_w:
        rows = []
        for w in workers:
            m = w.get("metrics") or {}
            rows.append({
                "worker": w["worker_id"], "status": w["status"], "busy": w["busy"], "host": w["host"],
                "capacity": w["capacity"], "cpu limit (cores)": m.get("cpu_limit_cores"),
                "CPU % of limit": m.get("cpu_percent_of_limit"), "memory MB": m.get("container_memory_mb")
                or m.get("process_rss_mb"), "assigned": w["assigned_tasks"], "completed": w["completed_tasks"],
                "queue": w["queue_length"], "heartbeat age (s)": w["last_heartbeat_age_seconds"],
                "failures": w["failures"], "recoveries": w["recoveries"],
            })
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
        hist = pd.DataFrame(api.metrics_history([w["worker_id"] for w in workers],
                                                since=max(0.0, stats["uptime_seconds"] - 300)))
        col1, col2 = st.columns(2)
        if not hist.empty:
            hist["time (s)"] = hist["t"].round(0)
            col1.markdown("**CPU utilisation over time** (% of each container's CPU limit)")
            col1.line_chart(hist.pivot_table(index="time (s)", columns="worker_id",
                                             values="cpu_percent_of_limit", aggfunc="mean"))
            memcol = "container_memory_mb" if hist["container_memory_mb"].notna().any() else "process_rss_mb"
            col2.markdown(f"**Memory over time** ({memcol.replace('_', ' ')})")
            col2.line_chart(hist.pivot_table(index="time (s)", columns="worker_id", values=memcol, aggfunc="mean"))
        st.markdown("**Worker workload distribution (current run)**")
        dist = pd.DataFrame(task_distribution(workers))
        if not dist.empty:
            st.bar_chart(dist.set_index("worker_id"), stack=False)

    with tab_t:
        df = pd.DataFrame(tasks)
        if df.empty:
            st.info("No tasks in the current run.")
        else:
            show = df[["task_id", "task_type", "size_class", "status", "worker_id", "attempts", "estimated_seconds",
                       "exec_seconds", "waiting_seconds", "turnaround_seconds", "network_overhead_seconds"]]
            st.dataframe(show.sort_values("task_id", ascending=False), hide_index=True, width="stretch",
                         height=320)
            done = df[df["status"] == "completed"]
            if not done.empty:
                st.markdown("**Task execution history** (completion time vs execution time, by worker)")
                st.scatter_chart(done, x="completed_at", y="exec_seconds", color="worker_id")

    with tab_e:
        ev = pd.DataFrame([e for e in snap["events"] if e["type"] not in ("run_started",)])
        if ev.empty:
            st.info("No events yet.")
        else:
            st.dataframe(ev.iloc[::-1], hide_index=True, width="stretch", height=360)

    with tab_c:
        st.markdown("**Runs in this coordinator session** (live measurements; reset a run to archive it)")
        runs = snap["runs"]["runs"] + ([snap["runs"]["current"]] if snap["runs"]["current"] else [])
        if runs:
            rdf = pd.DataFrame(runs).drop(columns=["completed_per_worker"])
            st.dataframe(rdf, hide_index=True, width="stretch")
            agg = rdf.groupby("algorithm")[["avg_turnaround_seconds", "avg_waiting_seconds"]].mean()
            st.bar_chart(agg, stack=False)
        files = find_live_results(RESULTS_DIR)
        if files:
            st.markdown(f"**Recorded live experiment** — `{files[0].parent.name}` (REAL execution)")
            sdf = pd.DataFrame(load_csv_rows(files[0]))
            st.dataframe(sdf, hide_index=True, width="stretch")
        st.caption("Offline simulator results (SIMULATED seconds) are in results/stage4-grid and are not mixed "
                   "into these live numbers.")


live_panels()
