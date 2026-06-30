# LanGuard

<p align="center">
  <img src="frontend/public/logo.png" alt="LanGuard logo" width="120">
</p>

<p align="center">
  <img alt="Version" src="https://img.shields.io/badge/version-1.0.2-blue">
  <img alt="Release downloads" src="https://img.shields.io/github/downloads/hillaliy/LanGuard/total?label=downloads">
  <a href="https://github.com/hillaliy/LanGuard/pkgs/container/languard-backend">
    <img alt="Backend image" src="https://img.shields.io/badge/GHCR-backend-2ea44f">
  </a>
  <a href="https://github.com/hillaliy/LanGuard/pkgs/container/languard-frontend">
    <img alt="Frontend image" src="https://img.shields.io/badge/GHCR-frontend-2ea44f">
  </a>
</p>

LanGuard is a self-hosted LAN visibility tool for home networks. It finds devices, tracks online/offline state, scans common ports, keeps history, and can send Discord or Telegram alerts for new devices.

## Features

- Device inventory with IP, MAC, vendor, hostname, icon, known/new state, and last seen time
- Open port tracking and port change events
- Scan history, event history, and notification history
- Scheduled scans
- Swagger, ReDoc, and schema endpoints
- First-user setup: the first account created in the app becomes admin

## Portainer

Create a new Portainer stack and paste:

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

Portainer will create the stack network automatically.

Backend and scanner use host networking so ARP discovery can see LAN devices. Without host networking, Docker bridge networking may only show the Docker host/gateway.

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
