#!/bin/sh
set -e

python manage.py migrate --fake-initial --no-input
python manage.py collectstatic --no-input
python manage.py createcachetable || true
if [ "$DJANGO_SUPERUSER_USERNAME" ]
then
    python manage.py ensure_superuser
fi

if [ "$#" -gt 0 ]; then
    exec "$@"
fi

exec gunicorn backend.wsgi:application --bind 0.0.0.0:8000
