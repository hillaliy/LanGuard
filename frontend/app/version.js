import packageInfo from '../package.json';

export const APP_VERSION = packageInfo.version;

export const CHANGELOG_ENTRIES = [
  {
    version: '1.0.5',
    date: '2026-07-03',
    items: [
      'Separated hubs and cameras into their own network map sections.',
      'Added smart hub, smart watch, LED strip, desk lamp, and ceiling light icons.',
      'Improved automatic icon detection for Aqara hubs and common lighting devices.',
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
