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
    exec "$@"
fi

exec granian --interface wsgi --host 0.0.0.0 --port 8000 backend.wsgi:application
