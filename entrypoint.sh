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

exec granian --interface wsgi --host 0.0.0.0 --port 8000 backend.wsgi:application
