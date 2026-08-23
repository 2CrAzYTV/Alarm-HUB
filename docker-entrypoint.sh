#!/usr/bin/env bash
set -Eeuo pipefail

# Backward compatibility:
# Existing Alarm-HUB installations from before embedded PostgreSQL already have
# DATABASE_URL configured but no DATABASE_MODE. Keep those on their external DB
# until the administrator explicitly switches them to embedded mode.
if [[ -n "${DATABASE_MODE:-}" ]]; then
  DATABASE_MODE="${DATABASE_MODE}"
elif [[ -n "${DATABASE_URL:-}" ]]; then
  DATABASE_MODE="external"
else
  DATABASE_MODE="embedded"
fi

PGDATA="${PGDATA:-/config/postgres}"
PGSOCKET="/var/run/postgresql"
APP_PID=""
POSTGRES_STARTED="false"

log() {
  printf '[Alarm-HUB] %s\n' "$*"
}

stop_services() {
  local rc=$?
  trap - EXIT INT TERM

  if [[ -n "${APP_PID}" ]] && kill -0 "${APP_PID}" 2>/dev/null; then
    kill -TERM "${APP_PID}" 2>/dev/null || true
    wait "${APP_PID}" 2>/dev/null || true
  fi

  if [[ "${POSTGRES_STARTED}" == "true" ]]; then
    local pg_bindir
    pg_bindir="$(pg_config --bindir)"
    log "Stopping embedded PostgreSQL..."
    runuser -u postgres -- "${pg_bindir}/pg_ctl" -D "${PGDATA}" -m fast -w stop >/dev/null 2>&1 || true
  fi

  exit "${rc}"
}

start_embedded_postgres() {
  local pg_bindir
  pg_bindir="$(pg_config --bindir)"

  mkdir -p "${PGDATA}" "${PGSOCKET}"
  chown -R postgres:postgres "${PGDATA}" "${PGSOCKET}"
  chmod 700 "${PGDATA}"
  chmod 775 "${PGSOCKET}"

  if [[ ! -s "${PGDATA}/PG_VERSION" ]]; then
    log "Initializing embedded PostgreSQL in ${PGDATA}..."
    runuser -u postgres -- "${pg_bindir}/initdb" \
      -D "${PGDATA}" \
      --username=alarmhub \
      --auth-local=trust \
      --auth-host=scram-sha-256 \
      --encoding=UTF8 \
      --locale=C.UTF-8

    cat >> "${PGDATA}/postgresql.conf" <<'EOF'
# Alarm-HUB embedded database: socket-only, not exposed on the network.
listen_addresses = ''
unix_socket_directories = '/var/run/postgresql'
EOF
  fi

  log "Starting embedded PostgreSQL..."
  runuser -u postgres -- "${pg_bindir}/pg_ctl" -D "${PGDATA}" -w start >/dev/null
  POSTGRES_STARTED="true"

  if ! runuser -u postgres -- "${pg_bindir}/psql" \
      -h "${PGSOCKET}" -U alarmhub -d postgres -tAc \
      "SELECT 1 FROM pg_database WHERE datname='alarmhub'" | grep -q 1; then
    log "Creating Alarm-HUB database..."
    runuser -u postgres -- "${pg_bindir}/createdb" \
      -h "${PGSOCKET}" -U alarmhub -O alarmhub alarmhub
  fi

  export DATABASE_URL="postgresql+psycopg://alarmhub@/alarmhub?host=${PGSOCKET}"
  log "Embedded PostgreSQL is ready."
}

case "${DATABASE_MODE,,}" in
  embedded|internal)
    start_embedded_postgres
    ;;
  external)
    if [[ -z "${DATABASE_URL:-}" ]]; then
      log "ERROR: DATABASE_MODE=external requires DATABASE_URL."
      exit 2
    fi
    log "Using external PostgreSQL database."
    ;;
  *)
    log "ERROR: Unknown DATABASE_MODE='${DATABASE_MODE}'. Use embedded or external."
    exit 2
    ;;
esac

trap stop_services EXIT INT TERM

log "Starting Alarm-HUB on port 8080..."
uvicorn app.entry:app \
  --host 0.0.0.0 \
  --port 8080 \
  --proxy-headers \
  --forwarded-allow-ips '*' &
APP_PID=$!
wait "${APP_PID}"
