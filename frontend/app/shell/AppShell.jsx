import { Alert, Container, Drawer, LoadingOverlay, Stack, Title } from '@mantine/core';
import { IconAlertCircle } from '@tabler/icons-react';

import { useLanGuardController } from '../hooks/useLanGuardController';
import AppHeader from './AppHeader';
import AppRouteContent from './AppRouteContent';
import AppShellModals from './AppShellModals';
import PrimaryNavigation, { viewTitles } from './PrimaryNavigation';

export default function AppShell({
  user,
  onLogout,
  onUserUpdated,
  initialDeviceId = null,
  initialView = 'dashboard',
}) {
  const controller = useLanGuardController({
    user,
    onLogout,
    onUserUpdated,
    initialDeviceId,
    initialView,
  });

  return (
    <main className="shell">
      <AppHeader controller={controller} user={user} />

      <div className="app-layout">
        <div className="mobile-page-title">
          <Title order={2}>
            {controller.devicePageId
              ? 'Device details'
              : viewTitles[controller.mainView] || 'Navigation'}
          </Title>
        </div>

        <Drawer
          opened={controller.mobileNavigationOpened}
          onClose={controller.mobileNavigation.close}
          title="Navigation"
          size="min(82vw, 320px)"
          className="mobile-navigation-drawer"
        >
          <PrimaryNavigation
            mainView={controller.mainView}
            devicePageId={controller.devicePageId}
            showDnsActivity={controller.showDnsActivity}
            showDockerInventory={controller.showDockerInventory}
            canManageUsers={controller.canManageUsers}
            onNavigate={controller.navigateToView}
            onNavigateComplete={controller.mobileNavigation.close}
            mobile
          />
        </Drawer>

        <aside className="app-sidebar" aria-label="Primary navigation">
          <PrimaryNavigation
            mainView={controller.mainView}
            devicePageId={controller.devicePageId}
            showDnsActivity={controller.showDnsActivity}
            showDockerInventory={controller.showDockerInventory}
            canManageUsers={controller.canManageUsers}
            onNavigate={controller.navigateToView}
          />
        </aside>

        <Container size="xl" py="xl" className="app-content">
          <LoadingOverlay visible={controller.loading} />
          <Stack gap="lg">
            {controller.error && (
              <Alert
                color="red"
                icon={<IconAlertCircle size={18} />}
                withCloseButton
                onClose={() => controller.setError('')}
              >
                {controller.error}
              </Alert>
            )}
            <AppRouteContent controller={controller} />
          </Stack>
        </Container>
      </div>

      <AppShellModals controller={controller} user={user} />
    </main>
  );
}
