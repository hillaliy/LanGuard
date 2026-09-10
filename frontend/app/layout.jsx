import '@mantine/core/styles.css';
import '@mantine/notifications/styles.css';
import './globals.css';
import './styles/shell.css';
import './styles/pages.css';
import './styles/dashboard.css';
import './styles/devices.css';
import './styles/maps.css';
import './styles/device-details.css';
import './styles/responsive.css';
import { ColorSchemeScript, MantineProvider } from '@mantine/core';
import { Notifications } from '@mantine/notifications';
import { theme } from './theme';

export const metadata = {
  title: 'LanGuard',
  description: 'Home LAN visibility and alerting dashboard',
};

export default function RootLayout({ children }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <ColorSchemeScript defaultColorScheme="auto" />
      </head>
      <body>
        <MantineProvider theme={theme} defaultColorScheme="auto">
          <Notifications position="top-right" zIndex={1000} />
          {children}
        </MantineProvider>
      </body>
    </html>
  );
}
