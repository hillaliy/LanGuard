export const dynamic = 'force-static';

export default function manifest() {
  return {
    name: 'LanGuard',
    short_name: 'LanGuard',
    description: 'Home LAN visibility and alerting dashboard',
    start_url: '/dashboard',
    scope: '/',
    display: 'standalone',
    background_color: '#f5f7fb',
    theme_color: '#4c6ef5',
    orientation: 'any',
    icons: [
      {
        src: '/icons/icon-192.png',
        sizes: '192x192',
        type: 'image/png',
        purpose: 'any',
      },
      {
        src: '/icons/icon-512.png',
        sizes: '512x512',
        type: 'image/png',
        purpose: 'any',
      },
    ],
  };
}
