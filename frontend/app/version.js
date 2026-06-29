import packageInfo from '../package.json';

export const APP_VERSION = packageInfo.version;

export const CHANGELOG_ENTRIES = [
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
