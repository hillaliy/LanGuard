import { readFileSync } from 'node:fs';
import { frontendChangelogEntries } from '../scripts/changelog.mjs';

const appVersion = readFileSync(new URL('../VERSION', import.meta.url), 'utf8').trim();
const changelogMarkdown = readFileSync(new URL('../CHANGELOG.md', import.meta.url), 'utf8');
const changelogEntries = frontendChangelogEntries(changelogMarkdown);

/** @type {import('next').NextConfig} */
const nextConfig = {
  ...(process.env.NODE_ENV === 'development'
    ? {
        async rewrites() {
          return [{ source: '/devices/:id', destination: '/devices' }];
        },
      }
    : { output: 'export' }),
  env: {
    NEXT_PUBLIC_APP_VERSION: appVersion,
    NEXT_PUBLIC_CHANGELOG_JSON: JSON.stringify(changelogEntries),
  },
  images: {
    unoptimized: true,
  },
};

export default nextConfig;
