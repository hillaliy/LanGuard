#!/bin/sh
set -e

LOCK_DIR="${MIGRATION_LOCK_DIR:-/data/.startup-lock}"
mkdir -p "$(dirname "$LOCK_DIR")"

cleanup_lock() {
    rmdir "$LOCK_DIR" 2>/dev/null || true
}

while ! mkdir "$LOCK_DIR" 2>/dev/null; do
    echo "Waiting for another LanGuard container to finish startup migrations..."
    sleep 2
done

trap cleanup_lock EXIT INT TERM

python manage.py migrate --fake-initial --no-input
python manage.py collectstatic --no-input
python manage.py createcachetable || true

cleanup_lock
trap - EXIT INT TERM

if [ "$#" -gt 0 ]; then
    echo "Starting command: $*"
    exec "$@"
fi

echo "Starting backend web server..."
exec granian \
    --interface wsgi \
    --host 0.0.0.0 \
    --port "${BACKEND_LISTEN_PORT:-8000}" \
    --workers "${GRANIAN_WORKERS:-1}" \
    --blocking-threads "${GRANIAN_BLOCKING_THREADS:-4}" \
    --backpressure "${GRANIAN_BACKPRESSURE:-32}" \
    --no-ws \
    backend.wsgi:application
