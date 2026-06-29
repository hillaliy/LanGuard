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
- Docker Compose stack with Django, scanner, Next.js frontend, Caddy, and shared SQLite storage

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

- Next.js
- Mantine
- Tabler Icons

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
INTERVAL=10
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

Builds the static Next.js frontend into a shared volume.

`caddy`

Serves the frontend and proxies API, admin, schema, and static routes to Django.

## Releases

The app version is read from `frontend/package.json` and shown in the top bar.
When the version changes, the frontend opens the changelog modal once per browser profile.

Build and push backend/frontend Docker images to GHCR:

```bash
docker login ghcr.io
./push_image.sh
```

Pass an explicit version when needed:

```bash
./push_image.sh 1.0.0
```

Default image names:

- `ghcr.io/hillaliy/languard-backend`
- `ghcr.io/hillaliy/languard-frontend`

Set `BACKEND_IMAGE` or `FRONTEND_IMAGE` to override the target repository names.

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

Scan safety limits are enforced by both the API and scheduler:

```env
SCAN_MAX_HOSTS=256
SCAN_ALLOW_PUBLIC_RANGES=false
SCAN_ARP_TIMEOUT=2
SCAN_ARP_RETRIES=2
SCAN_OFFLINE_AFTER_MISSES=3
PORT_SCAN_MAX_PORTS=64
PORT_SCAN_INTERVAL=30
```

By default, LanGuard only scans IPv4 private, loopback, or link-local ranges and rejects large CIDR ranges.
Devices are only marked offline after repeated missed scans, and port scanning runs less frequently than device discovery by default. Vendor names use Scapy's built-in manufacturer database.

## API Filtering

List endpoints return a `data` array and a `pagination` object. Use `limit` and `offset` to page through larger histories.

Useful filters:

- `/api/v1/device/?online=true&known=false&search=laptop&open_port=22`
- `/api/v1/scan/runs/?status=success&ip_range=192.168.1.0/24`
- `/api/v1/events/?event_type=port_opened&device=1&notified=false`
- `/api/v1/notifications/?status=failed&channel=discord`

## Production Settings

For home use, the default `ENVIRONMENT=development` keeps local setup simple. When `ENVIRONMENT=production` is set, LanGuard fails startup if the configuration is unsafe.

Production mode requires:

- a strong `SECRET_KEY`
- `DEBUG=false`
- `ALLOWED_HOSTS` with a real LAN IP, hostname, or domain
- no wildcard `ALLOWED_HOSTS=*`

Cookie security defaults to enabled in production. If you serve LanGuard only over plain HTTP on a trusted home LAN, set these explicitly:

```env
SESSION_COOKIE_SECURE=false
CSRF_COOKIE_SECURE=false
SECURE_SSL_REDIRECT=false
```

If you put LanGuard behind HTTPS, keep secure cookies enabled and set `CSRF_TRUSTED_ORIGINS` to the HTTPS origin.

## Notifications

LanGuard supports Discord and Telegram notifications.
Events for devices marked as known are still saved in history, but they are not sent to Discord or Telegram.

Discord:

```env
DISCORD_WEBHOOK=https://discord.com/api/webhooks/...
DISCORD_ICON_URL=https://raw.githubusercontent.com/hillaliy/LanGuard/main/frontend/public/logo.png
```

Discord notifications are sent as embeds with the LanGuard icon, a red alert bar, and device details.

Telegram:

```env
TELEGRAM_TOKEN=123456:token
TELEGRAM_USERID=123456789
```

Notification settings:

```env
NOTIFICATIONS_ENABLED=true
NOTIFICATION_EVENT_TYPES=new_device
NOTIFICATION_TIMEOUT=5
NOTIFICATION_RETRY_INTERVAL=15
NOTIFICATION_MAX_ATTEMPTS=3
```

By default, external notifications are sent only for newly discovered devices. Other events, such as online/offline changes and port changes, are still saved in the event history.

Manual retry:

```bash
python backend/manage.py retry_notifications
```

## Important Environment Variables

| Variable | Purpose | Default |
| --- | --- | --- |
| `ENVIRONMENT` | Runtime mode, use `production` for strict config checks | `development` |
| `IP_RANGE` | CIDR range to scan | `192.168.1.0/24` |
| `INTERVAL` | Scan interval in minutes | `10` |
| `PORT_SCAN_ENABLED` | Enable TCP port scanning | `true` |
| `PORT_SCAN_PORTS` | Comma-separated TCP ports | common LAN/service ports |
| `PORT_SCAN_TIMEOUT` | Per-port socket timeout | `0.5` |
| `PORT_SCAN_INTERVAL` | Minutes between port scans for each device | `30` |
| `SCAN_ARP_TIMEOUT` | ARP discovery timeout in seconds | `2` |
| `SCAN_ARP_RETRIES` | ARP discovery attempts per scan | `2` |
| `SCAN_OFFLINE_AFTER_MISSES` | Missed scans before a device is marked offline | `3` |
| `SCAN_MAX_HOSTS` | Maximum addresses allowed in one scan range | `256` |
| `SCAN_ALLOW_PUBLIC_RANGES` | Allow scanning public IPv4 ranges | `false` |
| `PORT_SCAN_MAX_PORTS` | Maximum ports scanned per device | `64` |
| `DB_PATH` | SQLite database path | `/data/db.sqlite3` in Docker |
| `STATIC_ROOT` | Django static output path | `/static` in Docker |
| `ALLOWED_HOSTS` | Django allowed hosts | `localhost,127.0.0.1` |
| `CORS_ALLOWED_ORIGINS` | Frontend origins for API access | localhost origins |
| `CSRF_TRUSTED_ORIGINS` | Trusted browser origins for HTTPS deployments | empty |
| `SESSION_COOKIE_SECURE` | Send session cookies only over HTTPS | production defaults to `true` |
| `CSRF_COOKIE_SECURE` | Send CSRF cookies only over HTTPS | production defaults to `true` |
| `SECURE_SSL_REDIRECT` | Redirect HTTP to HTTPS in Django | `false` |

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
npm run lint
```

Docker Compose:

```bash
docker compose config --quiet
```

## Notes

ARP scanning and some network operations may require elevated container permissions. The Docker Compose stack currently runs the backend and scanner with `privileged: true` for this reason.

SQLite is shared between the backend and scanner containers through a Docker volume. For heavier multi-user or multi-worker deployments, PostgreSQL would be a better long-term database.
