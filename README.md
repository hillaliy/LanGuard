# LanGuard

![LanGuard logo](frontend/public/logo.png)

LanGuard is a self-hosted LAN visibility and alerting tool for home networks and small offices. It discovers devices on your local network, tracks online/offline state, scans common TCP ports, records scan history, and emits events when something meaningful changes.

## Features

- ARP-based device discovery
- Device inventory with IP, MAC address, vendor, hostname, known/unknown state, and last seen time
- TCP open-port scanning per device
- Scan history with status, timing, device counts, and port-change counts
- Network event stream for new devices, online/offline transitions, opened ports, and closed ports
- Discord and Telegram notifications with delivery tracking and retry support
- Scheduled scans via a dedicated scanner service
- Manual scan endpoint for "scan now" workflows
- Admin dashboard
- OpenAPI schema, Swagger UI, and ReDoc
- Docker Compose stack with Django, scanner, React frontend, Caddy, and shared SQLite storage

## Stack

Backend:

- Django 6
- Django REST Framework
- drf-spectacular
- APScheduler
- Scapy
- Granian
- WhiteNoise

Frontend:

- React
- Bootstrap / React Bootstrap

Runtime:

- Docker Compose
- Caddy reverse proxy
- Shared SQLite volume

## Quick Start

1. Copy the example environment file:

```bash
cp .env.example .env
```

2. Edit `.env` for your network:

```env
IP_RANGE=192.168.1.0/24
INTERVAL=5
TIME_ZONE=UTC
```

3. Start the stack:

```bash
docker compose up --build
```

4. Open the app:

```text
http://localhost
```

The backend API is exposed through Caddy at:

```text
http://localhost/api/v1/
```

## API Docs

API documentation is generated with `drf-spectacular`.

- OpenAPI schema: `/api/schema/`
- Swagger UI: `/api/schema/swagger/`
- ReDoc: `/api/schema/redoc/`

The Django admin dashboard also links to Swagger UI, ReDoc, and the raw schema.

## Services

`backend`

Runs Django with Granian, applies migrations, collects static files, and serves the API/admin.

`scanner`

Runs scheduled network scans with:

```bash
python manage.py run_scheduler
```

`frontend`

Builds the React frontend into a shared volume.

`caddy`

Serves the frontend and proxies API, admin, schema, and static routes to Django.

## Scanning

Manual one-off scan:

```bash
python backend/manage.py scan_network
```

Scheduled scan process:

```bash
python backend/manage.py run_scheduler
```

Run one scan immediately before starting the scheduler:

```bash
python backend/manage.py run_scheduler --run-now
```

The scheduler also retries failed notification deliveries.

## Notifications

LanGuard supports Discord and Telegram notifications.

Discord:

```env
DISCORD_WEBHOOK=https://discord.com/api/webhooks/...
```

Telegram:

```env
TELEGRAM_TOKEN=123456:token
TELEGRAM_USERID=123456789
```

Notification settings:

```env
NOTIFICATIONS_ENABLED=true
NOTIFICATION_TIMEOUT=5
NOTIFICATION_RETRY_INTERVAL=15
NOTIFICATION_MAX_ATTEMPTS=3
```

Manual retry:

```bash
python backend/manage.py retry_notifications
```

## Important Environment Variables

| Variable | Purpose | Default |
| --- | --- | --- |
| `IP_RANGE` | CIDR range to scan | `192.168.1.0/24` |
| `INTERVAL` | Scan interval in minutes | `5` |
| `PORT_SCAN_ENABLED` | Enable TCP port scanning | `true` |
| `PORT_SCAN_PORTS` | Comma-separated TCP ports | common LAN/service ports |
| `PORT_SCAN_TIMEOUT` | Per-port socket timeout | `0.5` |
| `DB_PATH` | SQLite database path | `/data/db.sqlite3` in Docker |
| `STATIC_ROOT` | Django static output path | `/static` in Docker |
| `ALLOWED_HOSTS` | Django allowed hosts | `localhost,127.0.0.1` |
| `CORS_ALLOWED_ORIGINS` | Frontend origins for API access | localhost origins |

## Development Checks

Backend:

```bash
python backend/manage.py check
python backend/manage.py makemigrations --check --dry-run
python backend/manage.py spectacular --validate --file /tmp/languard-schema.yaml
python backend/manage.py test core
python -m compileall backend
```

Frontend:

```bash
cd frontend
npm ci
npm run build
npm test -- --watchAll=false --passWithNoTests
```

Docker Compose:

```bash
docker compose config --quiet
```

## Notes

ARP scanning and some network operations may require elevated container permissions. The Docker Compose stack currently runs the backend and scanner with `privileged: true` for this reason.

SQLite is shared between the backend and scanner containers through a Docker volume. For heavier multi-user or multi-worker deployments, PostgreSQL would be a better long-term database.
