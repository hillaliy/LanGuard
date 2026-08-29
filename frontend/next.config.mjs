import { readFileSync } from 'node:fs';

const appVersion = readFileSync(new URL('../VERSION', import.meta.url), 'utf8').trim();

/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'export',
  env: {
    NEXT_PUBLIC_APP_VERSION: appVersion,
  },
  images: {
    unoptimized: true,
  },
};

export default nextConfig;
