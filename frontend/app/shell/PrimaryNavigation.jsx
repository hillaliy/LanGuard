import { Button, Divider, Stack } from '@mantine/core';
import {
  IconBell,
  IconBrandDocker,
  IconHistory,
  IconLayoutDashboard,
  IconNetwork,
  IconSettings,
  IconShieldLock,
  IconSmartHome,
  IconWorldSearch,
} from '@tabler/icons-react';

import { getAdminUrl } from '../api';

export const viewTitles = {
  dashboard: 'Dashboard',
  devices: 'Devices',
  'home-map': 'Home Map',
  docker: 'Docker',
  events: 'Events',
  history: 'Scan history',
  notifications: 'Notifications',
  dns: 'DNS Activity',
  settings: 'Settings',
};

export default function PrimaryNavigation({
  mainView,
  devicePageId,
  showDnsActivity,
  showDockerInventory,
  canManageUsers,
  onNavigate,
  onNavigateComplete,
  mobile = false,
}) {
  function navigate(view) {
    onNavigate(view);
    onNavigateComplete?.();
  }

  function navigationButton(view, label, icon) {
    return (
      <Button
        className="sidebar-nav-button"
        variant={!devicePageId && mainView === view ? 'filled' : 'subtle'}
        justify="flex-start"
        leftSection={icon}
        onClick={() => navigate(view)}
        fullWidth
      >
        {label}
      </Button>
    );
  }

  return (
    <Stack className={`sidebar-nav${mobile ? ' mobile-sidebar-nav' : ''}`} gap={6}>
      {navigationButton('dashboard', 'Dashboard', <IconLayoutDashboard size={18} />)}
      {navigationButton('devices', 'Devices', <IconNetwork size={18} />)}
      {navigationButton('home-map', 'Home Map', <IconSmartHome size={18} />)}
      {showDockerInventory
        && navigationButton('docker', 'Docker', <IconBrandDocker size={18} />)}
      <Divider my={4} />
      {navigationButton('events', 'Events', <IconBell size={18} />)}
      {navigationButton('history', 'Scan history', <IconHistory size={18} />)}
      {navigationButton('notifications', 'Notifications', <IconBell size={18} />)}
      {showDnsActivity
        && navigationButton('dns', 'DNS Activity', <IconWorldSearch size={18} />)}
      {canManageUsers && (
        <>
          <Divider my={4} />
          <Button
            className="sidebar-nav-button"
            component="a"
            href={getAdminUrl()}
            target="_blank"
            rel="noreferrer"
            variant="subtle"
            justify="flex-start"
            leftSection={<IconShieldLock size={18} />}
            onClick={onNavigateComplete}
            fullWidth
          >
            Admin site
          </Button>
          {navigationButton('settings', 'Settings', <IconSettings size={18} />)}
        </>
      )}
    </Stack>
  );
}
