# Changelog

## 1.0.7 - 2026-07-05

- Fixed device status filters so Offline, Online, Recently seen, and Sleeping use the same status field shown in the table.
- Aligned dashboard online/offline counters with the displayed device status.
- Added a settings option to configure new-version checks in minutes or hours.
- Updated frontend dependencies through Dependabot.
- Added Dependabot handling for Node Docker image major updates.

## 1.0.6 - 2026-07-04

- Improved online/offline status with status reasons, per-device grace, ICMP checks, and remembered-port confirmation.
- Added Dependabot updates and dependency review checks for GitHub pull requests.

## 1.0.5 - 2026-07-03

- Separated hubs and cameras into their own network map sections.
- Added smart hub, smart watch, LED strip, desk lamp, and ceiling light icons.
- Improved automatic icon detection for Aqara hubs and common lighting devices.
- Reworked device guessing into reusable backend rules using hostnames, vendors, and open ports.
- Improved vendor fallback names, including Foxconn and Espressif IoT devices, without adding MAC suffixes.
- Added a top-bar link to the LanGuard GitHub project.

## 1.0.4 - 2026-07-03

- Added a network map view with Internet, router, and device nodes.
- Added power strip, fan, ceiling fan, and separate shutter/blinds icons.
- Improved network map labels so long device names wrap cleanly.
- Cleaned up README badges for GHCR container images.

## 1.0.3 - 2026-07-01

- Added a new-version indicator that checks for published releases every 6 hours.
- Improved the mobile device list so phone screens no longer squeeze table columns.
- Added tablet, lock, and robot vacuum device icons.
- Cleaned up frontend Caddyfile formatting for quieter container startup logs.

## 1.0.0 - 2026-06-29

- Initial LanGuard release.
- Added light, dark, and auto theme modes.
- Added account management for admins and self-editing for regular users.
- Improved device editing with vendor, hostname, icon, and scan details.
- Improved scan results with hostname detection, safer device matching, and better notifications.
- Added top-bar version history and Docker image publishing support.
