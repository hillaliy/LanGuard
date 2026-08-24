# LanGuard

<p align="center">
  <img src="frontend/public/logo.png" alt="LanGuard logo" width="120">
</p>

<p align="center">
  <img alt="Version" src="https://img.shields.io/badge/version-1.3.2-2496ed?style=for-the-badge">
  <a href="https://github.com/hillaliy/LanGuard/pkgs/container/languard-backend">
    <img alt="Docker pulls" src="https://ghcr-badge.elias.eu.org/shield/hillaliy/LanGuard/languard-backend">
  </a>
  <a href="https://github.com/users/hillaliy/packages/container/package/languard-backend">
    <img alt="Backend image" src="https://img.shields.io/badge/backend-GHCR-2ea44f?style=for-the-badge&logo=github">
  </a>
  <a href="https://github.com/users/hillaliy/packages/container/package/languard-frontend">
    <img alt="Frontend image" src="https://img.shields.io/badge/frontend-GHCR-2ea44f?style=for-the-badge&logo=github">
  </a>
</p>

LanGuard is a self-hosted LAN visibility tool for home networks. It finds devices, tracks online/offline state, scans common ports, keeps history, and can send Discord or Telegram alerts for new devices.

## Preview

<p align="center">
  <img src="docs/demo-preview.png" alt="LanGuard dashboard preview with fictional device data" width="920">
</p>

<p align="center">
  <img src="docs/home-map-preview.png" alt="LanGuard home map preview with fictional rooms and devices" width="920">
</p>

## Features

- Device inventory with IP, MAC, vendor, hostname, icon, known/new state, and last seen time
- Home Map view for arranging rooms and device icons into a simple floor-plan style layout
- Open port tracking and port change events
- Scan history, event history, and notification history
- Scheduled scans that wait for the configured interval after each scan completes
- Device inventory export/import for moving names, icons, rooms, roles, vendors, IPs, MAC addresses, and open ports between installs
- Swagger, ReDoc, and schema endpoints
- First-user setup: the first account created in the app becomes admin

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
      - ALLOWED_HOSTS=192.168.1.10,languard.local
    volumes:
      - languard_database:/data
      - languard_static:/static
    restart: unless-stopped

  scanner:
    image: ghcr.io/hillaliy/languard-backend:latest
    container_name: languard-scanner
    privileged: true
    network_mode: host
    command: ["python", "-u", "manage.py", "run_scheduler", "--run-now"]
    environment:
      - SECRET_KEY=change-this-to-a-long-random-secret
      - ALLOWED_HOSTS=192.168.1.10,languard.local
    volumes:
      - languard_database:/data
      - languard_static:/static
    restart: unless-stopped
    depends_on:
      - backend

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
      - backend

volumes:
  languard_database:
  languard_static:
```

Change these before deploying:

- `SECRET_KEY`
- `ALLOWED_HOSTS`

Create a `SECRET_KEY` with:

```bash
openssl rand -base64 48
```

`ALLOWED_HOSTS` should be the IP or hostname you open in the browser, for example:

```env
ALLOWED_HOSTS=192.168.1.10,languard.local
```

You normally do not need `CORS_ALLOWED_ORIGINS` in the Portainer stack. The frontend container serves the UI and proxies API requests to the backend on the same origin.

Open `http://<docker-host-ip>:8080` and create the first user. That user becomes admin. There is no default admin password.

After sign in, open Settings to change the scan range, scan interval, timezone, Discord webhook, or Telegram settings.

The scanner waits for the configured scan interval after a scan completes before starting the next scheduled scan. For example, with a 5 minute interval, a scan that finishes at 20:14 will schedule the next scan for about 20:19.

If you override `DISCORD_ICON_URL`, use a versioned URL when replacing the icon so Discord mobile clients do not reuse an old cached image, for example:

```env
DISCORD_ICON_URL=https://raw.githubusercontent.com/hillaliy/LanGuard/main/frontend/public/logo.png?v=1.3.2
```

Portainer will create the stack network automatically.

Backend and scanner use host networking so ARP discovery can see LAN devices. Without host networking, Docker bridge networking may only show the Docker host/gateway.

## Phone MAC Randomization

Modern iPhone and Android devices often use a private/random MAC address per Wi-Fi network. If that address changes, LanGuard will see the same phone as a new device.

For stable tracking, disable private/random MAC addressing for your home Wi-Fi network on the phone, or mark the new entry as known when it appears.

## Update

Change the image tags in the Portainer stack and redeploy. Do not delete the `languard_database` volume unless you want to reset LanGuard.

## Development

```bash
python3.14 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python backend/manage.py migrate
python backend/manage.py runserver 127.0.0.1:8000
```

```bash
cd frontend
npm ci
npm run dev
```

Open `http://127.0.0.1:3000`.

## Checks

```bash
.venv/bin/python backend/manage.py test core
cd frontend && npm run lint && npm run build
```

## API

- Swagger: `/api/schema/swagger/`
- ReDoc: `/api/schema/redoc/`
- Schema: `/api/schema/`
