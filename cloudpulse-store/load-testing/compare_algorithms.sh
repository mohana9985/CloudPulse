#!/usr/bin/env bash
# Runs the SAME Locust workload once per CloudPulse scheduling algorithm against the store and
# reports, per algorithm: Locust latency/throughput (client view) and the gateway's run summary
# (queue wait, per-replica distribution). The gateway run is archived after each algorithm, so
# the results are also returned by GET /gateway/runs.
#
# Usage:  ./compare_algorithms.sh [HOST] [USERS] [SPAWN_RATE] [DURATION] [SCENARIO]
# Example: ./compare_algorithms.sh http://localhost 40 10 45s MixedWorkloadUser
# GATEWAY (env) = scheduling dashboard/gateway URL, default http://localhost:8090
set -euo pipefail
# Inside a virtual environment (any OS) use its "python"; Windows venvs have no python3.
if [ -n "${VIRTUAL_ENV:-}" ]; then PY=python; else PY=python3; fi

HOST="${1:-http://localhost}"
USERS="${2:-40}"
SPAWN_RATE="${3:-10}"
DURATION="${4:-45s}"
SCENARIO="${5:-MixedWorkloadUser}"
GATEWAY="${GATEWAY:-http://localhost:8090}"
ALGORITHMS="${ALGORITHMS:-round_robin weighted_round_robin least_loaded shortest_job_first fcfs_baseline}"

cd "$(dirname "$0")"
OUT="results/compare-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$OUT"

if ! curl -fsS "$GATEWAY/gateway/health" > /dev/null; then
  echo "ERROR: $GATEWAY/gateway/health is not reachable. Start the site first (docker compose up --build -d)." >&2
  exit 1
fi

for ALG in $ALGORITHMS; do
  echo "==> $ALG  (scenario=$SCENARIO users=$USERS spawn=$SPAWN_RATE/s duration=$DURATION)"
  # wait until the gateway is idle, then switch algorithm and start a clean run
  for _ in $(seq 1 30); do
    idle=$(curl -fsS "$GATEWAY/gateway/stats" | "$PY" -c "import sys,json; d=json.load(sys.stdin); print(int(d['backlog']+d['inflight']==0))")
    [ "$idle" = "1" ] && break; sleep 1
  done
  curl -fsS -X POST "$GATEWAY/gateway/algorithm" -H 'content-type: application/json' -d "{\"algorithm\":\"$ALG\"}" > /dev/null
  curl -fsS -X POST "$GATEWAY/gateway/reset" -H 'content-type: application/json' -d "{\"label\":\"warm-up\"}" > /dev/null
  locust -f locustfile.py "$SCENARIO" --host "$HOST" --headless \
    -u "$USERS" -r "$SPAWN_RATE" -t "$DURATION" \
    --csv "$OUT/$ALG" --html "$OUT/$ALG.html" --only-summary > "$OUT/$ALG.locust.log" 2>&1 || true
  sleep 2
  curl -fsS -X POST "$GATEWAY/gateway/reset" -H 'content-type: application/json' -d "{\"label\":\"locust $SCENARIO u=$USERS\"}" \
    | "$PY" -c "import sys,json; json.dump(json.load(sys.stdin)['archived_run'], open('$OUT/$ALG.gateway.json','w'), indent=2)"
done

echo
echo "Reports saved in load-testing/$OUT"
"$PY" summarize_compare.py "$OUT" | tee "$OUT/summary.md"
