#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

RESET_DATA=false
for arg in "$@"; do
  case "$arg" in
    --reset-data|--wipe-data)
      RESET_DATA=true
      ;;
    --help|-h)
      cat <<'EOF'
Usage: bash scripts/dev.local.sh [--reset-data]

Options:
  --reset-data, --wipe-data   Clear runtime DB + artifacts before starting services.
EOF
      exit 0
      ;;
    *)
      echo "Unknown option: $arg"
      echo "Run with --help for usage."
      exit 1
      ;;
  esac
done

export LOG_LEVEL=DEBUG
LOG_DIR="$ROOT_DIR/storage/logs"
mkdir -p "$LOG_DIR"

API_LOG="$LOG_DIR/jobbot-api.log"
WORKER_LOG="$LOG_DIR/jobbot-worker.log"
UI_LOG="$LOG_DIR/jobbot-ui.log"

# Start each run with clean log files for easier debugging.
: > "$API_LOG"
: > "$WORKER_LOG"
: > "$UI_LOG"

echo "Starting Docker services..."
docker compose up -d

if [ "$RESET_DATA" = true ]; then
  echo "Reset flag enabled. Waiting for Postgres..."
  for i in {1..30}; do
    if docker compose exec -T postgres pg_isready -U postgres -d jobbot >/dev/null 2>&1; then
      break
    fi
    if [ "$i" -eq 30 ]; then
      echo "Postgres did not become ready in time."
      exit 1
    fi
    sleep 1
  done

  echo "Clearing runtime database records..."
  docker compose exec -T postgres psql -U postgres -d jobbot -v ON_ERROR_STOP=1 -c \
    "TRUNCATE TABLE interventions, artifacts, applications, jobs, companies, scrape_runs RESTART IDENTITY CASCADE;"

  echo "Clearing artifact/profile files..."
  rm -rf "$ROOT_DIR/storage/artifacts" "$ROOT_DIR/storage/profiles"
  mkdir -p "$ROOT_DIR/storage/artifacts" "$ROOT_DIR/storage/profiles"
  touch "$ROOT_DIR/storage/artifacts/.gitkeep" "$ROOT_DIR/storage/profiles/.gitkeep"
fi

echo "Starting API, worker, and UI dev server..."

PYTHONPATH=. uvicorn apps.api.main:app --reload --log-level debug --port 8000 > "$API_LOG" 2>&1 &
API_PID=$!

PYTHONPATH=. celery -A apps.worker.celery_app worker -P solo -l debug -Q default,scrape,apply > "$WORKER_LOG" 2>&1 &
WORKER_PID=$!

(
  cd ui
  npm run dev -- --host 127.0.0.1 --port 5173 --debug
) > "$UI_LOG" 2>&1 &
UI_PID=$!

cleanup() {
  echo "Stopping background processes..."
  kill "$API_PID" "$WORKER_PID" "$UI_PID" 2>/dev/null || true
}

trap cleanup EXIT INT TERM

echo "JobBot local dev started:"
echo "  API:    http://127.0.0.1:8000"
echo "  UI:     http://127.0.0.1:5173"
echo "  LOG_LEVEL: $LOG_LEVEL"
if [ "$RESET_DATA" = true ]; then
  echo "  DATA RESET: enabled"
fi
echo "Logs:"
echo "  $API_LOG"
echo "  $WORKER_LOG"
echo "  $UI_LOG"
echo ""
echo "Press Ctrl+C to stop."

wait
