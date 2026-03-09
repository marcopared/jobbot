#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

echo "Triggering scrape..."
RESPONSE="$(curl -sS -X POST http://127.0.0.1:8000/api/jobs/run-scrape)"
RUN_ID="$(python3 -c 'import json,sys; print(json.loads(sys.stdin.read()).get("run_id",""))' <<< "$RESPONSE")"

if [[ -z "$RUN_ID" ]]; then
  echo "Failed to start scrape: $RESPONSE"
  exit 1
fi

echo "Waiting for run $RUN_ID to finish..."
for _ in $(seq 1 90); do
  RUN_JSON="$(curl -sS "http://127.0.0.1:8000/api/runs/$RUN_ID")"
  STATUS="$(python3 -c 'import json,sys; print(json.loads(sys.stdin.read()).get("status",""))' <<< "$RUN_JSON")"
  if [[ "$STATUS" == "SUCCESS" ]]; then
    echo "Seed complete."
    echo "$RUN_JSON"
    exit 0
  fi
  if [[ "$STATUS" == "FAILED" ]]; then
    echo "Seed failed."
    echo "$RUN_JSON"
    exit 1
  fi
  sleep 2
done

echo "Timed out waiting for scrape run."
exit 1
