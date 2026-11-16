# Cost, reliability and performance trade-offs

The abstract asks for "the trade-offs between system performance, reliability, and
infrastructure costs". Performance and reliability are measured in
[`live_results.md`](live_results.md); this note adds the cost side. The figures below are list
prices used for estimation. Status (2026-11-16): the earlier single store instance was deleted;
the planned deployment is configuration **B′** below (two new instances), not yet launched.

## Price assumptions

| Item | Assumed price | Note |
|---|---|---|
| EC2 `t4g.small` (2 vCPU Graviton, 2 GB), on-demand | **USD 0.0168 / hour** (≈ USD 12.3 / month if never stopped) | us-east-1 list price as reported by public price trackers in Nov 2026; verify for your region on the [EC2 pricing page](https://aws.amazon.com/ec2/pricing/on-demand/) |
| EBS gp3 root volume, 8–20 GB | USD 0.08 / GB-month → USD 0.64–1.60 / month | billed even when the instance is stopped |
| Public IPv4 address | USD 0.005 / hour (≈ USD 3.6 / month) | billed for every public IPv4 since Feb 2024 |
| Traffic between instances in one VPC/AZ | USD 0 | coordinator↔worker traffic |
| Data transfer out to the Internet | first 100 GB / month free, then per GB | dashboard/SSH traffic is negligible |

Free Tier is not assumed. All figures exclude tax.

## Configurations

| Configuration | Instances | Hourly cost | Monthly (24×7) | What it buys |
|---|---|---|---|---|
| **A. Single host** (earlier layout; store + monitoring + coordinator + 3 workers + dashboard on one `t4g.small`) | 1 | USD 0.022 | ≈ USD 16 | 3 worker *processes* sharing 2 vCPU: parallelism limited to the host; one failure domain (host down ⇒ everything down) |
| **B′. Two hosts — planned deployment** (EC2 #1: store + gateway + monitoring; EC2 #2: coordinator + 3 workers + Streamlit dashboard; [`../../cloudpulse-store/docs/AWS_TWO_EC2.md`](../../cloudpulse-store/docs/AWS_TWO_EC2.md)) | 2 | USD 0.044 | ≈ USD 32 | website and scheduler no longer compete for one host's 2 vCPU; dashboard↔store and Prometheus↔coordinator traffic crosses the VPC network. One extra worker on EC2 #1 (`compose.remote-worker.yaml`) gives a real multi-machine run at no extra cost |
| **B. Two hosts** (A + one `t4g.small` running one or more remote workers) | 2 | USD 0.044 | ≈ USD 32 | +2 vCPU of real capacity, worker traffic crosses a real network; workers on host 2 survive a crash of host 1's workers (coordinator is still a single point of failure) |
| **C. Three hosts** (coordinator host + 2 worker hosts) | 3 | USD 0.066 | ≈ USD 48 | abstract's "multi-machine" picture; two independent worker failure domains |
| **Zero-cost multi-machine substitute** (coordinator on an EC2 host, one worker on the student's laptop through an SSH tunnel) | 1 (+ laptop) | USD 0.022 | ≈ USD 16 | real cross-machine network path (Internet + tunnel) for the overhead measurement without a second paid instance |

Hourly cost = instance + IPv4 + EBS (20 GB) pro-rated.

## Cost of the experiments actually run

Measured wall-clock time of the recorded live runs (sum of makespans, `results/live-mac-20261112/`):

| Experiment | Runs | Busy time | Cost if run on configuration A | On B | On C |
|---|---|---|---|---|---|
| Algorithm grid (3 sizes × 3 seeds × 5 configs) | 45 | 1 375 s ≈ 23 min | USD 0.008 | 0.017 | 0.025 |
| Normal vs failure (60 tasks × 3 seeds × 5 configs) | 30 | 890 s ≈ 15 min | USD 0.006 | 0.011 | 0.017 |
| Scaling 1/2/3 workers (60 tasks × 3 seeds × 5 configs) | 45 | 1 268 s ≈ 21 min | USD 0.008 | 0.015 | 0.023 |
| **Whole suite incl. restarts and waits (≈ 1.5 h)** | 120 | ≈ 1.5 h | **≈ USD 0.03** | 0.07 | 0.10 |

Compute cost of the experiments is negligible; the dominant cost is **instance-hours left
running between sessions** (USD 0.53 / day for A). Stopping the instance after each session is the
only cost control that matters at this scale.

## Trade-offs observed

| Dimension | Evidence (real execution, single host) | Trade-off |
|---|---|---|
| Performance vs cost | Same workload on 1 → 2 → 3 workers (`scaling_summary.csv`, charts 11–12): makespan 34 → 22 → 20 s for LL (quota 0.75 → 1.20 → 1.50 cores). The second worker (+60 % capacity) bought −33 % makespan; the third (+40 %) only a further −8 % because the arrival rate, not capacity, became the limit. Under RR the third worker made things *worse* (31 → 45 s) | Capacity added without a capacity-aware scheduler can be wasted money; and once the system is no longer saturated, extra workers add cost without speed. On one host the extra containers are free; on separate hosts each is another instance (+USD 0.022 / h) |
| Reliability vs cost | Killing one of three workers (W2) roughly doubled average turnaround and lengthened the makespan by 15–35 % (algorithm-dependent); detection 4–5 s / 9–10 s, 1 retry, **0 tasks lost**, rejoin ≈ 17 s | Redundant capacity (3 workers instead of 1) is what makes zero loss possible: the price of fault tolerance is idle headroom (~20 % under ρ = 0.85). On one host the whole cluster still shares one failure domain; independent failure domains cost 2–3× (configurations B/C) |
| Scheduling policy vs cost | Round Robin wasted the fastest worker (W1 at ~25 % of its quota while W3 ran at ~84 %), giving 3–6× the turnaround of LL/SJF on identical hardware | A better scheduler is the cheapest upgrade: LL/SJF deliver the throughput of RR on fewer/cheaper workers; equivalently, RR needs more instances to match them |
| Network overhead vs distribution | Coordinator↔worker overhead 3–7 ms per task on the Docker bridge (< 1 % of mean task time) | On real networks the overhead grows (to be measured in the multi-host run); it matters only when tasks are short relative to the round trip |

## Not measured

- Multi-host runs (configurations B/B′/C) were not executed, so no measured network overhead across
  machines exists yet; the options (worker on EC2 #1, or on a laptop) are described in
  [`../live/README.md`](../live/README.md).
- Actual billing for the student account is not reproduced here.
