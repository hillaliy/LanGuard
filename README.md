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
  <a href="https://www.paypal.me/hillaliy">
    <img alt="Donate through PayPal" src="https://img.shields.io/badge/PayPal-Donate-blue.svg?logo=paypal&style=for-the-badge">
  </a>
</p>

<p align="center">
  <strong><a href="https://hillaliy.github.io/LanGuard/">Documentation</a></strong>
  &middot;
  <a href="https://hillaliy.github.io/LanGuard/docs/installation">Installation</a>
  &middot;
  <a href="https://hillaliy.github.io/LanGuard/docs/integrations">Integrations</a>
  &middot;
  <a href="https://hillaliy.github.io/LanGuard/docs/troubleshooting">Troubleshooting</a>
  &middot;
  <a href="https://github.com/hillaliy/LanGuard/releases">Releases</a>
</p>

LanGuard builds a clear inventory of local network devices, tracks availability
and network changes, and surfaces equipment that needs attention. It is designed
for home and small-business networks and can run continuously as a Docker web
application or locally as a native macOS scanner.

## Highlights

- Discover IPv4 devices, names, vendors, MAC addresses, services, and common open ports.
- Track online state, scan history, IP changes, availability, and attention findings.
- Organize regular, visitor, and archived devices by room, role, icon, and notes.
- Send Discord, Telegram, ntfy, or signed automation webhook notifications.
- Connect AdGuard Home, Speedtest Tracker, and HomeBox.
- Run scheduled scans, on-demand detailed port scans, and Wake-on-LAN actions.
- Install the Docker interface as a web app on supported phones, tablets, and computers.

## Preview

<p align="center">
  <img src="docs/demo-preview.png" alt="LanGuard dashboard with fictional device data" width="920">
</p>

## Quick Start

The recommended deployment uses Docker Compose or Portainer on a trusted host
with direct access to the network being scanned.

```bash
git clone https://github.com/hillaliy/LanGuard.git
cd LanGuard
```

Before deployment, edit [`docker-compose.yaml`](docker-compose.yaml):

1. Replace `SECRET_KEY` in the backend and scanner with the same long random value.
2. Add the Docker host IP or hostname to `ALLOWED_HOSTS` while keeping `127.0.0.1`.
3. Start the stack:

```bash
docker compose up -d
```

Open `http://<docker-host-ip>:8080` and create the first account. The first
account becomes the administrator; LanGuard has no default password.

> LanGuard uses host networking and privileged discovery because ARP scanning
> requires direct Layer 2 access to the LAN. Review the Compose file before
> deployment and use a dedicated, trusted host.

For Portainer instructions, custom ports, VLAN requirements, updates, backups,
and migration, use the complete
[installation documentation](https://hillaliy.github.io/LanGuard/docs/installation).

## Editions

| Edition | Best for | Guide |
| --- | --- | --- |
| Docker web app | Continuous scanning, shared access, integrations, and notifications | [Installation](https://hillaliy.github.io/LanGuard/docs/installation) |
| Native macOS scanner | A self-contained inventory and scanner on one Mac | [macOS Scanner](https://hillaliy.github.io/LanGuard/docs/macos-scanner) |

The editions do not synchronize their inventories.

## Documentation

The public documentation is the source of truth for setup and operation:

- [Getting Started](https://hillaliy.github.io/LanGuard/docs/getting-started)
- [Configuration](https://hillaliy.github.io/LanGuard/docs/configuration)
- [Device Discovery](https://hillaliy.github.io/LanGuard/docs/device-discovery)
- [Devices and Alerts](https://hillaliy.github.io/LanGuard/docs/devices-and-alerts)
- [Integrations](https://hillaliy.github.io/LanGuard/docs/integrations)
- [Notifications](https://hillaliy.github.io/LanGuard/docs/notifications)
- [Scheduler Tasks](https://hillaliy.github.io/LanGuard/docs/scheduler-tasks)
- [Backup and Migration](https://hillaliy.github.io/LanGuard/docs/backup-and-migration)
- [Troubleshooting](https://hillaliy.github.io/LanGuard/docs/troubleshooting)
- [Release Notes](https://hillaliy.github.io/LanGuard/docs/release-notes)

## Update

Update all three Docker services together without removing the database volume:

```bash
docker compose pull
docker compose up -d --force-recreate
```

Review the [release notes](https://hillaliy.github.io/LanGuard/docs/release-notes)
before updating across multiple versions.

## API

Docker installations expose interactive API documentation through the LanGuard server:

- Swagger: `/api/schema/swagger/`
- ReDoc: `/api/schema/redoc/`
- OpenAPI schema: `/api/schema/`

## Contributing

Development setup, checks, and release instructions are documented in
[`CONTRIBUTING.md`](CONTRIBUTING.md). User-facing behavior should update the
public documentation in the same pull request.

## License

Copyright © 2026 Yossi Hillali.

LanGuard is licensed under the [Apache License 2.0](LICENSE). Third-party
components remain subject to their respective licenses.
