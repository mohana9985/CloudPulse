from __future__ import annotations

import os
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from live.dashboard.api import (  # noqa: E402
    BACKEND_CPU_QUERY, BACKEND_MEM_QUERY, WebsiteClient, backend_rows, comparison_rows, parse_cpu_limits,
)

GATEWAY_URL = os.environ.get("GATEWAY_URL", "http://localhost:8090")
LOADGEN_URL = os.environ.get("LOADGEN_URL", "http://localhost:8095")
PROMETHEUS_URL = os.environ.get("PROMETHEUS_URL", "http://localhost:9090")
GRAFANA_URL = os.environ.get("GRAFANA_PUBLIC_URL", "http://localhost:3000")
CPU_LIMITS = parse_cpu_limits(os.environ.get("BACKEND_CPU_LIMITS", "B1=0.75,B2=0.45,B3=0.30"))
REFRESH = float(os.environ.get("DASHBOARD_REFRESH_SECONDS", 2))

ALGO_LABELS = {
    "round_robin": "Round Robin",
    "weighted_round_robin": "Weighted Round Robin",
    "least_loaded": "Least Loaded",
    "shortest_job_first": "Shortest Job First",
    "fcfs_baseline": "FCFS (control baseline)",
}
MIX_HELP = {
    "mixed": "home, listing, filters, product pages, search + 5% orders",
    "browse": "read-only browsing: home, listing, filters, product pages",
    "search": "search-heavy: search, filters, product pages",
    "shopping": "browsing + search + 10% orders (writes to the database)",
}


@st.cache_resource
def website_client() -> WebsiteClient:
    return WebsiteClient(GATEWAY_URL, LOADGEN_URL, PROMETHEUS_URL)


api = website_client()
st.title("CloudPulse — Website Workload & Scheduling")
st.caption("Workload path: **Streamlit → workload generator → website (Nginx) → scheduling gateway → "
           "backend replica B1 / B2 / B3**. The replicas have different CPU limits "
           f"({', '.join(f'{k} {v:g} cores' for k, v in CPU_LIMITS.items())}). "
           f"Refreshed every {REFRESH:g}s.")

try:
    gw = api.gateway.get("/gateway/stats")
    mixes = api.mixes()
except Exception as e:
    st.error(f"Website stack unreachable ({e}). Start it with `docker compose up -d` in cloudpulse-store and "
             "the dashboard with `docker compose -f compose.yaml -f compose.monitoring.yaml up -d` in "
             "cloudpulse-scheduler.")
    st.stop()

with st.sidebar:
    st.header("Website controls")
    algos = gw["algorithms"]
    choice = st.selectbox("Scheduling algorithm", algos, index=algos.index(gw["algorithm"]),
                          format_func=lambda a: ALGO_LABELS.get(a, a))
    if st.button("Apply algorithm", width="stretch"):
        try:
            api.set_algorithm(choice)
            st.success(f"Gateway now uses {ALGO_LABELS.get(choice, choice)}")
        except RuntimeError as e:
            st.error(str(e))

    st.subheader("Send workload to the website")
    n = st.number_input("Requests", 1, 100_000, 3000, step=500)
    rate = st.slider("Arrival rate (requests / second)", 1, 300, 200,
                     help="Above ~150 req/s the slow replicas saturate and the algorithms differ clearly")
    mix = st.selectbox("Shopper behaviour", list(mixes), index=list(mixes).index("mixed"),
                       format_func=lambda m: f"{m} — {MIX_HELP.get(m, '')}")
    seed = st.number_input("Seed (same seed = same requests)", 0, 1_000_000, 42)
    conc = st.number_input("Max requests in flight", 1, 500, 200)
    fresh = st.checkbox("Start a fresh gateway run (reset per-backend counters)", value=True)
    st.caption(f"≈ {n / rate:.0f} s of traffic")
    c1, c2 = st.columns(2)
    if c1.button("Start", type="primary", width="stretch"):
        try:
            info = api.start(int(n), float(rate), mix, int(seed), int(conc), fresh)
            st.success(f"Run #{info['run_id']}: {info['planned']} requests over ~{info['duration_seconds']:.0f}s")
        except RuntimeError as e:
            st.error(str(e))
    if c2.button("Stop", width="stretch"):
        try:
            api.stop()
            st.warning("Stopping (in-flight requests finish)")
        except RuntimeError as e:
            st.error(str(e))

    st.subheader("Failure demo")
    kind = st.radio("Failure type", ["Real crash", "Graceful outage"], horizontal=True,
                    help="Real crash: the replica's process is killed (requests it is serving are cut off) "
                         "and it refuses connections for N seconds; the gateway must detect it by itself. "
                         "Graceful outage: the gateway stops sending new requests to the replica, which "
                         "finishes what it is doing; nothing is killed, so errors stay at 0.")
    if kind == "Real crash":
        st.caption("Kills the backend process. Requests in flight on it fail (5xx); requests that had not "
                   "reached it are retried on another replica. Docker restarts it after N seconds.")
    else:
        st.caption("Planned maintenance: no request is lost, the other replicas take the traffic.")
    target = st.selectbox("Backend", [b["backend_id"] for b in gw["backends"]])
    secs = st.number_input("Down for (seconds)", 1, 300, 15)
    if st.button("Crash backend" if kind == "Real crash" else "Take out of rotation", width="stretch"):
        try:
            if kind == "Real crash":
                api.crash_backend(target, float(secs))
                st.error(f"{target} crashed: process killed, down for ~{secs}s")
            else:
                api.simulate_outage(target, float(secs))
                st.warning(f"{target} out of rotation for {secs}s")
        except RuntimeError as e:
            st.error(str(e))

    st.divider()
    st.markdown(f"**Metrics in Grafana** ({GRAFANA_URL})")
    st.markdown(f"- [Request Scheduling Gateway]({GRAFANA_URL}/d/cloudpulse-gateway)\n"
                f"- [Store Application Overview]({GRAFANA_URL}/d/cloudpulse-store)")


def fmt(v, unit="", digits=1):
    return "—" if v is None else f"{v:.{digits}f}{unit}"


@st.fragment(run_every=REFRESH)
def live_panels() -> None:
    try:
        snap = api.snapshot()
    except Exception as e:
        st.error(f"Website stack unreachable: {e}")
        return
    gw, lg = snap["gateway"], snap["loadgen"]
    run = lg["run"]

    if run is None:
        st.info("No website workload yet. Set the requests and rate in the sidebar and press **Start**.")
    else:
        done = run["completed"] / max(run["planned"], 1)
        state = "RUNNING" if lg["running"] else run["state"].upper()
        st.subheader(f"Workload run #{run['run_id']} — {state} · {run['mix']} · seed {run['seed']} · "
                     f"target {run['target_rate_rps']:g} req/s")
        st.progress(min(done, 1.0), text=f"{run['completed']} / {run['planned']} requests completed")
        c = st.columns(7)
        c[0].metric("Sent", run["sent"])
        c[1].metric("Completed", run["completed"])
        c[2].metric("OK", run["ok"])
        c[3].metric("Errors", run["completed"] - run["ok"], help="5xx, network errors and unexpected 4xx")
        c[4].metric("Achieved req/s", fmt(run["achieved_rps"], digits=1))
        c[5].metric("p50 latency", fmt(run["p50_ms"], " ms", 0))
        c[6].metric("p95 latency", fmt(run["p95_ms"], " ms", 0))
        st.caption(f"Errors: **{run['server_errors']}** server (5xx) · **{run['network_errors']}** network · "
                   f"**{run['client_errors']}** unexpected 4xx · error rate {run['error_rate_pct']:.2f} % — "
                   f"**{gw['counters']['retries']}** requests were retried on another replica by the gateway "
                   f"(those count as OK). Slowest request: {fmt(run['max_ms'], ' ms', 0)}.")

    st.subheader(f"Scheduling gateway — {ALGO_LABELS.get(gw['algorithm'], gw['algorithm'])} · "
                 f"gateway run #{gw['run_id']}")
    healthy = sum(1 for b in gw["backends"] if b["healthy"])
    c = st.columns(6)
    c[0].metric("Healthy replicas", f"{healthy} / {len(gw['backends'])}")
    c[1].metric("Requests / s (30 s)", fmt(gw["throughput_rps_30s"], digits=1))
    c[2].metric("In flight", gw["inflight"])
    c[3].metric("Waiting in queue", gw["backlog"])
    c[4].metric("Retries", gw["counters"]["retries"])
    c[5].metric("Queue timeouts", gw["counters"]["queue_timeouts"])

    tab_b, tab_r, tab_k, tab_e, tab_c = st.tabs(
        ["Backends", "Live requests", "Request types", "Failures & events", "Algorithm comparison"])

    with tab_b:
        cpu = api.prom_instant(BACKEND_CPU_QUERY)
        mem = api.prom_instant(BACKEND_MEM_QUERY)
        rows = backend_rows(gw["backends"], cpu, mem, CPU_LIMITS)
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
        if not cpu:
            st.caption("CPU / memory need Prometheus (`docker compose --profile monitoring up -d` in "
                       "cloudpulse-store).")
        col1, col2 = st.columns(2)
        dist = pd.DataFrame([{"backend": r["backend"], "assigned": r["assigned"], "completed": r["completed"]}
                             for r in rows]).set_index("backend")
        col1.markdown("**Requests per backend (this gateway run)**")
        col1.bar_chart(dist, stack=False)
        hist = pd.DataFrame(api.prom_range(BACKEND_CPU_QUERY, minutes=10, step=5))
        col2.markdown("**Backend CPU over last 10 min** (% of each replica's CPU limit)")
        if hist.empty:
            col2.info("No Prometheus data yet.")
        else:
            hist["value"] = [100 * v / CPU_LIMITS.get(r, 1) for v, r in zip(hist["value"], hist["replica"])]
            hist["time"] = pd.to_datetime(hist["time"], unit="s")
            col2.line_chart(hist.pivot_table(index="time", columns="replica", values="value", aggfunc="mean"))

    with tab_r:
        df = pd.DataFrame(snap["recent"])
        if df.empty:
            st.info("No requests yet.")
        else:
            show = df[["seq", "started", "kind", "method", "path", "backend", "status", "outcome", "latency_ms",
                       "gateway_wait_ms", "gateway_service_ms"]].rename(columns={
                "seq": "#", "started": "t (s)", "latency_ms": "total ms", "gateway_wait_ms": "queue wait ms",
                "gateway_service_ms": "backend ms"})
            st.dataframe(show, hide_index=True, width="stretch", height=360)
            st.markdown("**Latency of recent requests, by backend**")
            st.scatter_chart(df, x="started", y="latency_ms", color="backend")

    with tab_k:
        if run is None or not run["by_kind"]:
            st.info("No requests yet.")
        else:
            kdf = pd.DataFrame([{"request type": k, **v} for k, v in run["by_kind"].items()])
            st.dataframe(kdf, hide_index=True, width="stretch")
            st.bar_chart(kdf.set_index("request type")[["avg_ms", "p95_ms"]], stack=False)

    with tab_e:
        ev = pd.DataFrame(snap["events"])
        if ev.empty:
            st.info("No events yet.")
        else:
            st.dataframe(ev, hide_index=True, width="stretch", height=360)

    with tab_c:
        st.markdown("**Finished website workload runs** — use the same seed, rate and behaviour with each "
                    "algorithm for a fair comparison")
        rows = comparison_rows(snap["loadgen_runs"])
        if not rows:
            st.info("No finished runs yet.")
        else:
            cdf = pd.DataFrame(rows)
            st.dataframe(cdf, hide_index=True, width="stretch")
            cdf["run label"] = cdf["run"].astype(str) + " · " + cdf["algorithm"]
            st.markdown("**Latency by run** (lower is better)")
            st.bar_chart(cdf.set_index("run label")[["avg ms", "p95 ms"]], stack=False)


live_panels()
