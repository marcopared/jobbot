#!/usr/bin/env bash
# EPIC 2 verification: migrations, job_sources, job_analyses.
# Requires: Docker running (docker compose up -d), .env with DATABASE_URL_SYNC.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

echo "=== EPIC 2 Verification ==="

# Ensure Docker services are up
if ! docker info >/dev/null 2>&1; then
  echo "Docker is not running. Start Docker Desktop, then run: docker compose up -d"
  exit 1
fi

echo "Starting Docker services..."
docker compose up -d

echo "Waiting for PostgreSQL..."
for i in {1..30}; do
  if docker compose exec -T postgres pg_isready -U postgres 2>/dev/null; then
    break
  fi
  sleep 1
  if [[ $i -eq 30 ]]; then
    echo "PostgreSQL did not become ready."
    exit 1
  fi
done
echo "PostgreSQL ready."

echo "Running migrations..."
# Existing unversioned DBs (from create_all): stamp baseline first, then upgrade
if PYTHONPATH=. alembic current 2>/dev/null | grep -q "001_baseline\|002_reconciliation"; then
  PYTHONPATH=. alembic upgrade head
elif PYTHONPATH=. python3 -c "
from sqlalchemy import create_engine, text
from apps.api.settings import Settings
eng = create_engine(Settings().database_url_sync)
with eng.connect() as c:
    r = c.execute(text(\"SELECT 1 FROM information_schema.tables WHERE table_name='companies'\"))
    if r.fetchone():
        r2 = c.execute(text(\"SELECT 1 FROM alembic_version\"))
        if not r2.fetchone():
            exit(0)  # existing unversioned
exit(1)
" 2>/dev/null; then
  echo "Existing unversioned DB detected. Stamping baseline..."
  PYTHONPATH=. alembic stamp 001_baseline
  PYTHONPATH=. alembic upgrade head
else
  PYTHONPATH=. alembic upgrade head
fi
echo "Migrations OK."

echo "Verifying schema (job_sources, job_analyses)..."
PYTHONPATH=. python3 -c "
from sqlalchemy import create_engine, text
from apps.api.settings import Settings
s = Settings()
eng = create_engine(s.database_url_sync)
with eng.connect() as c:
    r = c.execute(text(\"SELECT column_name FROM information_schema.columns WHERE table_name='job_sources' ORDER BY ordinal_position\"))
    cols = [row[0] for row in r]
    assert 'job_id' in cols and 'source_name' in cols and 'external_id' in cols
    r2 = c.execute(text(\"SELECT column_name FROM information_schema.columns WHERE table_name='job_analyses' ORDER BY ordinal_position\"))
    cols2 = [row[0] for row in r2]
    assert 'job_id' in cols2 and 'total_score' in cols2
    print('Schema OK: job_sources and job_analyses have expected columns.')
"
echo ""
echo "=== EPIC 2 verification complete ==="
echo "To fully verify: start API and worker (scripts/dev.sh), trigger a scrape,"
echo "then check that job_sources and job_analyses get rows."
