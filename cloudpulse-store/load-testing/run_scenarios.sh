#!/usr/bin/env bash
# Usage:  ./run_scenarios.sh [HOST] [USERS] [SPAWN_RATE] [DURATION]
# Example: ./run_scenarios.sh http://localhost 20 5 1m
set -euo pipefail

HOST="${1:-http://localhost}"
USERS="${2:-20}"
SPAWN_RATE="${3:-5}"
DURATION="${4:-1m}"

cd "$(dirname "$0")"
OUT="results/$(date +%Y%m%d-%H%M%S)"
mkdir -p "$OUT"

if ! curl -fsS "$HOST/api/health" > /dev/null; then
  echo "ERROR: $HOST/api/health is not reachable. Start the site first (docker compose up --build -d)." >&2
  exit 1
fi

for SCENARIO in BrowsingUser SearchUser OrderUser MixedWorkloadUser; do
  echo "==> $SCENARIO  (users=$USERS spawn=$SPAWN_RATE/s duration=$DURATION)"
  locust -f locustfile.py "$SCENARIO" --host "$HOST" --headless \
    -u "$USERS" -r "$SPAWN_RATE" -t "$DURATION" \
    --csv "$OUT/$SCENARIO" --html "$OUT/$SCENARIO.html" --only-summary || true
done

echo
echo "Reports saved in load-testing/$OUT"
echo "Summary (Aggregated row of each *_stats.csv):"
python3 summarize_results.py "$OUT"
