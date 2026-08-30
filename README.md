<p align="center">
  <img src="frontend/public/logo.png" alt="LanGuard logo" width="120">
</p>

<h1 align="center">LanGuard</h1>

<p align="center">
  Self-hosted network visibility for discovering, organizing, and monitoring devices on your LAN.
</p>

<p align="center">
  <a href="https://github.com/hillaliy/LanGuard/releases/latest">
    <img alt="Latest version" src="https://img.shields.io/github/v/release/hillaliy/LanGuard?style=for-the-badge&label=version">
  </a>
  <a href="https://github.com/hillaliy/LanGuard/pkgs/container/languard-backend">
    <img alt="Docker pulls" src="https://ghcr-badge.elias.eu.org/shield/hillaliy/LanGuard/languard-backend">
  </a>
</p>

<p align="center">
  <a href="#features">Features</a> &middot;
  <a href="#portainer">Docker setup</a> &middot;
  <a href="macos/LanGuardMac/README.md">macOS</a> &middot;
  <a href="#migrate-from-watchyourlan">Migration</a>
</p>

LanGuard finds devices, tracks online and offline state, scans common ports,
keeps network history, and can send Discord or Telegram alerts when new devices
appear.

## Preview

### Dashboard

<p align="center">
  <img src="docs/demo-preview.png" alt="LanGuard dashboard preview with fictional device data" width="920">
</p>

### Home Map

<p align="center">
  <img src="docs/home-map-preview.png" alt="LanGuard home map preview with fictional rooms and devices" width="920">
</p>

## Features

**Discover**

- Find LAN devices and identify their IP, MAC address, vendor, and hostname
- Track identity confidence, first and last seen times, and known or new state
- Detect local HTTP/HTTPS interfaces and common open ports

**Monitor**

- Track online and offline state, port changes, and device activity
- Compare completed scans and retain scan, event, and notification history
- Run scheduled scans after the configured interval

**Organize**

- Assign names, icons, rooms, roles, and expected device behavior
- Arrange rooms and devices in the Docker Home Map view
- Export and import device inventory between LanGuard installations

**Notify and integrate**

- Send Discord or Telegram alerts for new devices and important changes
- Use Swagger, ReDoc, and the OpenAPI schema for integrations
- Create the initial administrator directly from first-user setup

## Portainer

Use the included [`docker-compose.yaml`](docker-compose.yaml), or create a new Portainer stack and paste:

```yaml
services:
  backend:
    image: ghcr.io/hillaliy/languard-backend:latest
    container_name: languard-backend
    privileged: true
    network_mode: host
    environment:
      - SECRET_KEY=change-this-to-a-long-random-secret
      - ALLOWED_HOSTS=192.168.1.10,languard.local,127.0.0.1
    volumes:
      - languard_database:/data
      - languard_static:/static
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health/', timeout=3).read()"]
      interval: 10s
      timeout: 5s
      retries: 6
      start_period: 60s
    restart: unless-stopped

  scanner:
    image: ghcr.io/hillaliy/languard-scheduler:latest
    container_name: languard-scanner
    privileged: true
    network_mode: host
    command: ["python", "-u", "manage.py", "run_scheduler", "--run-now"]
    environment:
      - SECRET_KEY=change-this-to-a-long-random-secret
      - ALLOWED_HOSTS=192.168.1.10,languard.local,127.0.0.1
    volumes:
      - languard_database:/data
      - languard_static:/static
    restart: unless-stopped
    depends_on:
      backend:
        condition: service_healthy
        restart: true

  frontend:
    image: ghcr.io/hillaliy/languard-frontend:latest
    container_name: languard-frontend
    environment:
      - BACKEND_UPSTREAM=host.docker.internal:8000
    extra_hosts:
      - host.docker.internal:host-gateway
    ports:
      - 8080:80
    restart: unless-stopped
    depends_on:
      backend:
        condition: service_healthy
        restart: true

volumes:
  languard_database:
  languard_static:
```

The scanner uses its own `languard-scheduler` image. It does not call the web
backend, but both services share the database and schema, so Compose keeps their
startup and update order coordinated. Both images are built from the same LanGuard
source release and should be updated together. Always update and recreate the
backend, scheduler, and frontend containers as one release, even when the scheduler
service itself has no visible feature change.

> [!IMPORTANT]
> The next Docker release includes a Docker deployment change. Existing Compose
> files remain compatible, but installations should update the stack with the
> current Compose definition and recreate it once to enable the backend health
> check and coordinated service restarts. Named volumes are preserved, so this
> does not delete LanGuard data.

> [!IMPORTANT]
> When upgrading from version 1.4.0 or earlier, change the scanner service image
> from `ghcr.io/hillaliy/languard-backend` to
> `ghcr.io/hillaliy/languard-scheduler`, then pull and recreate the stack.

Change these before deploying:

- `SECRET_KEY`
- `ALLOWED_HOSTS`

Create a `SECRET_KEY` with:

```bash
openssl rand -base64 48
```

`ALLOWED_HOSTS` should include the IP or hostname you open in the browser. Keep
`127.0.0.1` for the container health check, for example:

```env
ALLOWED_HOSTS=192.168.1.10,languard.local,127.0.0.1
```

You normally do not need `CORS_ALLOWED_ORIGINS` in the Portainer stack. The frontend container serves the UI and proxies API requests to the backend on the same origin.

Open `http://<docker-host-ip>:8080` and create the first user. That user becomes admin. There is no default admin password.

After sign in, open Settings to change the scan range, scan interval, timezone, Discord webhook, or Telegram settings.

The scanner waits for the configured scan interval after a scan completes before starting the next scheduled scan. For example, with a 5 minute interval, a scan that finishes at 20:14 will schedule the next scan for about 20:19.

## Migrate from WatchYourLAN

LanGuard can import the current device inventory from
[WatchYourLAN](https://github.com/aceberg/WatchYourLAN). On the machine that can
reach WatchYourLAN, download the JSON returned by its documented `/api/all`
endpoint:

```bash
curl http://WATCHYOURLAN_IP:8840/api/all -o watchyourlan-devices.json
```

If WatchYourLAN is published through a reverse proxy, replace the URL with its
actual address and include the authentication options required by that proxy.

Then:

1. Sign in to LanGuard as an administrator.
2. Open **Settings**.
3. Under **WatchYourLAN migration**, select **Import from WatchYourLAN**.
4. Choose `watchyourlan-devices.json`.

LanGuard matches existing devices by MAC address and imports the device name,
DNS hostname, IP address, MAC address, hardware vendor, known state, online state,
and last-seen value. Invalid records are skipped and the completion notification
shows how many devices were created, updated, or skipped.

WatchYourLAN does not provide LanGuard rooms, roles, icons, comments, open-port
history, identity confidence, or Home Map layout through this endpoint. Configure
those fields in LanGuard after the migration; later scans can enrich hostname,
vendor, port, and status information. Scan history is intentionally not imported.

If you override `DISCORD_ICON_URL`, use a versioned URL when replacing the icon so Discord mobile clients do not reuse an old cached image, for example:

```env
DISCORD_ICON_URL=https://raw.githubusercontent.com/hillaliy/LanGuard/main/frontend/public/logo.png?v=current
```

Portainer will create the stack network automatically.

Backend and scanner use host networking so ARP discovery can see LAN devices. Without host networking, Docker bridge networking may only show the Docker host/gateway.

## Phone MAC Randomization

Modern iPhone and Android devices often use a private/random MAC address per Wi-Fi network. If that address changes, LanGuard will see the same phone as a new device.

For stable tracking, disable private/random MAC addressing for your home Wi-Fi network on the phone, or mark the new entry as known when it appears.

## Update

Change the image tags in the Portainer stack and redeploy. Do not delete the `languard_database` volume unless you want to reset LanGuard.

## API

- Swagger: `/api/schema/swagger/`
- ReDoc: `/api/schema/redoc/`
- Schema: `/api/schema/`

## Contributing

Development setup, checks, and release metadata instructions are documented in
[`CONTRIBUTING.md`](CONTRIBUTING.md).
