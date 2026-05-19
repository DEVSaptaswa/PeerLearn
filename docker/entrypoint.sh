#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════════
# PeerLearn — Docker Entrypoint
# 1. Wait for MySQL, MongoDB, Redis to be ready
# 2. Run migrations — handles pre-existing tables with --fake-initial
# 3. Collect static files
# 4. Optionally seed sample data
# 5. Exec CMD (Gunicorn or runserver)
# ═══════════════════════════════════════════════════════════════════════════════

set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
log()  { echo -e "${CYAN}[PeerLearn]${NC} $*"; }
ok()   { echo -e "${GREEN}[PeerLearn ✔]${NC} $*"; }
warn() { echo -e "${YELLOW}[PeerLearn ⚠]${NC} $*"; }
die()  { echo -e "${RED}[PeerLearn ✘]${NC} $*"; exit 1; }

# ── TCP port probe ─────────────────────────────────────────────────────────────
wait_for() {
    local label="$1" host="$2" port="$3" timeout="${4:-60}" elapsed=0
    log "Waiting for ${label} at ${host}:${port} (timeout: ${timeout}s)..."
    until nc -z -w 3 "$host" "$port" 2>/dev/null; do
        if [[ $elapsed -ge $timeout ]]; then
            die "${label} not ready after ${timeout}s."
        fi
        echo -n "."
        sleep 2
        elapsed=$((elapsed + 2))
    done
    echo ""
    ok "${label} port is open."
}

# ── Wait until MySQL actually accepts queries (port-open ≠ ready) ─────────────
wait_for_mysql_queries() {
    local host="${MYSQL_HOST:-mysql}"
    local port="${MYSQL_PORT:-3306}"
    local user="${MYSQL_USER:-peerlearn}"
    local pass="${MYSQL_PASSWORD:-}"
    local db="${MYSQL_DB:-peer_learning}"
    local timeout=90 elapsed=0

    log "Waiting for MySQL to accept queries..."
    until python - << PYEOF 2>/dev/null
import sys
try:
    import MySQLdb as driver
except ImportError:
    import pymysql as driver
try:
    c = driver.connect(host="$host", port=$port, user="$user",
                       passwd="$pass", db="$db", connect_timeout=3)
    c.close()
    sys.exit(0)
except Exception:
    sys.exit(1)
PYEOF
    do
        if [[ $elapsed -ge $timeout ]]; then
            die "MySQL never became queryable after ${timeout}s."
        fi
        echo -n "."
        sleep 2
        elapsed=$((elapsed + 2))
    done
    echo ""
    ok "MySQL is accepting queries."
}

# ── 1. Wait for services ───────────────────────────────────────────────────────
wait_for "MySQL"   "${MYSQL_HOST:-mysql}"  "${MYSQL_PORT:-3306}"  90
wait_for_mysql_queries
wait_for "MongoDB" "${MONGO_HOST:-mongo}"  "27017"                60
wait_for "Redis"   "${REDIS_HOST:-redis}"  "${REDIS_PORT:-6379}"  30

# ── 2. Detect existing tables → choose migration strategy ─────────────────────
log "Checking database state..."
DB_HAS_MIGRATIONS=$(python - << PYEOF 2>/dev/null
import sys
try:
    import MySQLdb as driver
except ImportError:
    import pymysql as driver
try:
    c = driver.connect(
        host="${MYSQL_HOST:-mysql}", port=int("${MYSQL_PORT:-3306}"),
        user="${MYSQL_USER:-peerlearn}", passwd="${MYSQL_PASSWORD:-}",
        db="${MYSQL_DB:-peer_learning}", connect_timeout=5
    )
    cur = c.cursor()
    cur.execute("SHOW TABLES LIKE 'django_migrations'")
    print("yes" if cur.fetchone() else "no")
    c.close()
except Exception:
    print("no")
PYEOF
)

# ── 3. Run migrations ──────────────────────────────────────────────────────────
if [[ "$DB_HAS_MIGRATIONS" == "yes" ]]; then
    warn "Tables already exist — running migrate --fake-initial to sync..."
    python manage.py migrate --noinput --fake-initial
    ok "Migrations synced (fake-initial)."
else
    log "Fresh database — running full migrations..."
    python manage.py migrate --noinput
    ok "Migrations complete."
fi

# ── 4. Collect static files ────────────────────────────────────────────────────
log "Collecting static files..."
python manage.py collectstatic --noinput --clear 2>&1 | tail -5
ok "Static files collected."

# ── 5. Seed data (optional) ────────────────────────────────────────────────────
if [[ "${SEED_DATA:-false}" == "true" ]]; then
    log "Seeding sample data..."
    python manage.py seed_data && ok "Sample data seeded."
fi

# ── 6. Start app ───────────────────────────────────────────────────────────────
echo ""
log "Starting: $*"
echo ""
exec "$@"
