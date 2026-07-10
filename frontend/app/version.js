import packageInfo from '../package.json';

export const APP_VERSION = packageInfo.version;

export const CHANGELOG_ENTRIES = [
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
