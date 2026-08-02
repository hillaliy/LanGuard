import packageInfo from '../package.json';

export const APP_VERSION = packageInfo.version;

export const CHANGELOG_ENTRIES = [
  {
    version: '1.0.18',
    date: '2026-08-02',
    items: [
      'Added native macOS room support for devices, settings, import/export, filtering, and grouping views.',
      'Improved the macOS Devices page compact layout so search, filters, sorting, and the sidebar behave better in small windows.',
      'Preserved room assignments during device discovery merges.',
    ],
  },
  {
    version: '1.0.17',
    date: '2026-08-01',
    items: [
      'Redesigned the native macOS About page with richer project details, support links, and a manual update check.',
      'Added GitHub release version checking for the native macOS app.',
      'Added icons to the macOS menu bar status items and quit action.',
    ],
  },
  {
    version: '1.0.16',
    date: '2026-07-30',
    items: [
      'Fixed native macOS notification registration by signing the packaged app bundle with the stable LanGuard bundle identifier.',
      'Added explicit notification permission and notification settings actions in the macOS Settings page.',
      'Delayed notification permission prompts until the user enables or requests notifications from Settings.',
    ],
  },
  {
    version: '1.0.15',
    date: '2026-07-30',
    items: [
      'Added the native macOS Grouping page for role-based device views.',
      'Added temporary Guest Scan so client or guest networks can be scanned without saving devices, history, or inventory changes.',
      'Added macOS device import/export, launch-at-login, an About page, menu bar status, and richer device detail editing.',
      'Improved macOS discovery with bundled vendor data, better role and icon detection, offline grace handling, and network/broadcast address filtering.',
      'Added more device icons, secondary device icons, manual role editing, and device deletion.',
      'Polished the macOS dashboard, Devices filters, compact layouts, sidebar behavior, and empty states across small and full-screen windows.',
    ],
  },
  {
    version: '1.0.14',
    date: '2026-07-29',
    items: [
      'Published Docker backend and frontend images as multi-architecture builds for linux/amd64 and linux/arm64.',
      'Fixed Portainer startup failures on non-Apple-Silicon hosts caused by single-architecture images.',
      'Added the version badge to the native macOS app header.',
    ],
  },
  {
    version: '1.0.13',
    date: '2026-07-29',
    items: [
      'Added device inventory export and import for Docker LanGuard so device names, icons, vendors, IPs, MAC addresses, known state, and open ports can be moved between installs.',
      'Added matching device inventory export and import to the native macOS app settings.',
      'Updated the Docker project logo assets to use the improved LanGuard shield/network icon.',
      'Added the initial native macOS SwiftUI app source, packaging files, app icon, and tests under macos/LanGuardMac.',
    ],
  },
  {
    version: '1.0.12',
    date: '2026-07-14',
    items: [
      'Updated backend dependencies through Dependabot, including Django 6.0.7 and drf-spectacular 0.30.0.',
      'Updated the frontend ESLint dependency through Dependabot.',
      'Improved the device table layout on mobile landscape and narrow tablet widths so columns use the compact mobile layout before they get cut off.',
    ],
  },
  {
    version: '1.0.11',
    date: '2026-07-11',
    items: [
      'Fixed dashboard timestamps so timezone-less API dates are treated as UTC and displayed in the configured LanGuard timezone.',
      'Added automatic scan-status refresh for the Scan control and Latest scan panels without changing device table pagination.',
      'Standardized API and Discord notification timestamps to UTC ISO strings with a Z suffix.',
    ],
  },
  {
    version: '1.0.10',
    date: '2026-07-10',
    items: [
      'Added gateway/router detection from the default network route and marks the gateway as a known router.',
      'Added device risk badges with backend risk scoring for unknown devices, risky ports, many open ports, missing vendors, and unstable scan status.',
    ],
  },
  {
    version: '1.0.9',
    date: '2026-07-08',
    items: [
      'Fixed stale running scan records so newer completed scans show as finished instead of running.',
      'Added README guidance about private/random phone MAC addresses.',
    ],
  },
  {
    version: '1.0.8',
    date: '2026-07-05',
    items: [
      'Added notification rules for new devices, online/offline changes, port changes, and quiet hours.',
      'Improved scan visibility with active/idle state, current range, duration, timing, and last error details.',
    ],
  },
  {
    version: '1.0.7',
    date: '2026-07-05',
    items: [
      'Fixed device status filters so Offline, Online, Recently seen, and Sleeping use the same status field shown in the table.',
      'Aligned dashboard online/offline counters with the displayed device status.',
      'Added a settings option to configure new-version checks in minutes or hours.',
      'Updated frontend dependencies through Dependabot.',
      'Added Dependabot handling for Node Docker image major updates.',
    ],
  },
  {
    version: '1.0.6',
    date: '2026-07-04',
    items: [
      'Improved online/offline status with status reasons, per-device grace, ICMP checks, and remembered-port confirmation.',
      'Added Dependabot updates and dependency review checks for GitHub pull requests.',
    ],
  },
  {
    version: '1.0.5',
    date: '2026-07-03',
    items: [
      'Separated hubs and cameras into their own network map sections.',
      'Added smart hub, smart watch, LED strip, desk lamp, and ceiling light icons.',
      'Improved automatic icon detection for Aqara hubs and common lighting devices.',
      'Reworked device guessing into reusable backend rules using hostnames, vendors, and open ports.',
      'Improved vendor fallback names, including Foxconn and Espressif IoT devices, without adding MAC suffixes.',
      'Added a top-bar link to the LanGuard GitHub project.',
    ],
  },
  {
    version: '1.0.4',
    date: '2026-07-03',
    items: [
      'Added a network map view with Internet, router, and device nodes.',
      'Added power strip, fan, ceiling fan, and separate shutter/blinds icons.',
      'Improved network map labels so long device names wrap cleanly.',
      'Cleaned up README badges for GHCR container images.',
    ],
  },
  {
    version: '1.0.3',
    date: '2026-07-01',
    items: [
      'Added a new-version indicator that checks for published releases every 6 hours.',
      'Improved the mobile device list so phone screens no longer squeeze table columns.',
      'Added tablet, lock, and robot vacuum device icons.',
      'Cleaned up frontend Caddyfile formatting for quieter container startup logs.',
    ],
  },
  {
    version: '1.0.2',
    date: '2026-06-30',
    items: [
      'Updated Docker networking so scans can see LAN devices instead of only the Docker host.',
      'Added configurable frontend backend upstream for host-network deployments.',
      'Tuned Granian backend concurrency for home use.',
    ],
  },
  {
    version: '1.0.1',
    date: '2026-06-29',
    items: [
      'Added a container startup lock so backend and scanner migrations do not race on first deploy.',
      'Improved README logo sizing and project badges.',
    ],
  },
  {
    version: '1.0.0',
    date: '2026-06-29',
    items: [
      'Initial LanGuard release.',
      'Added light, dark, and auto theme modes.',
      'Added account management for admins and self-editing for regular users.',
      'Improved device editing with vendor, hostname, icon, and scan details.',
      'Improved scan results with hostname detection, safer device matching, and better notifications.',
      'Added top-bar version history and Docker image publishing support.',
    ],
  },
];
