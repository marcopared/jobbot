#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"
export LOG_LEVEL=DEBUG

echo "Starting Docker services..."
docker compose up -d

echo "Waiting for Postgres..."
for i in $(seq 1 30); do
  if docker compose exec -T postgres pg_isready -U postgres -d jobbot >/dev/null 2>&1; then
    break
  fi
  if [ "$i" -eq 30 ]; then
    echo "Postgres did not become ready in time."
    exit 1
  fi
  sleep 1
done

echo "Running migrations..."
alembic upgrade head

echo "Starting API, worker, and UI dev server..."
PYTHONPATH=. uvicorn apps.api.main:app --reload --log-level debug --port 8000 > /tmp/jobbot-api.log 2>&1 &
API_PID=$!

PYTHONPATH=. celery -A apps.worker.celery_app worker -P solo -l debug -Q default,scrape,ingestion > /tmp/jobbot-worker.log 2>&1 &
WORKER_PID=$!

(
  cd ui
  npm run dev -- --host 127.0.0.1 --port 5173 --debug
) > /tmp/jobbot-ui.log 2>&1 &
UI_PID=$!

cleanup() {
  echo "Stopping background processes..."
  kill "$API_PID" "$WORKER_PID" "$UI_PID" 2>/dev/null || true
}

trap cleanup EXIT INT TERM

echo "JobBot started:"
echo "  API:    http://127.0.0.1:8000"
echo "  UI:     http://127.0.0.1:5173"
echo "  LOG_LEVEL: $LOG_LEVEL"
echo "Logs:"
echo "  /tmp/jobbot-api.log"
echo "  /tmp/jobbot-worker.log"
echo "  /tmp/jobbot-ui.log"
echo ""
echo "Press Ctrl+C to stop."

wait
