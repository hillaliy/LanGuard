#!/bin/sh

python manage.py migrate --fake-initial --no-input
python manage.py collectstatic --no-input
python manage.py createcachetable
if [ "$DJANGO_SUPERUSER_USERNAME" ]
then
    python manage.py createsuperuser \
        --noinput \
        --username $DJANGO_SUPERUSER_USERNAME \
        --email $DJANGO_SUPERUSER_USERNAME
fi
$@

gunicorn backend.wsgi:application --bind 0.0.0.0:8000
