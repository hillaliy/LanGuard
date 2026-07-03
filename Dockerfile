FROM python:3.14-slim

ARG APP_VERSION=1.0.5

ENV ENVIRONMENT=production \
    APP_VERSION=${APP_VERSION} \
    DEBUG=false \
    DB_PATH=/data/db.sqlite3 \
    STATIC_ROOT=/static \
    SESSION_COOKIE_SECURE=false \
    CSRF_COOKIE_SECURE=false \
    SECURE_SSL_REDIRECT=false

RUN pip install --upgrade pip

COPY ./requirements.txt .
RUN pip install -r requirements.txt

COPY ./backend /app

WORKDIR /app

COPY ./entrypoint.sh /
ENTRYPOINT [ "sh", "/entrypoint.sh" ]
