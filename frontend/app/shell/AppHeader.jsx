import {
  ActionIcon,
  Box,
  Burger,
  Button,
  Container,
  Group,
  Image,
  Text,
  Title,
  Tooltip,
  UnstyledButton,
} from '@mantine/core';
import { IconBrandGithub, IconClock, IconLogout, IconRefresh } from '@tabler/icons-react';

import { userDisplayName, userInitials } from '../auth/user';
import { APP_VERSION } from '../version';
import { ColorSchemeControl, formatTopbarDate, formatTopbarTime } from './ShellControls';

export default function AppHeader({ controller, user }) {
  const {
    canManageUsers,
    canRunScans,
    currentTime,
    displayTimeZone,
    hasVersionIndicator,
    loadData,
    logoutModal,
    mobileNavigation,
    mobileNavigationOpened,
    refreshing,
    runScan,
    scanButtonLabel,
    scanIsActive,
    setChangelogOpened,
    usersModal,
    versionTooltip,
  } = controller;

  return (
    <header className="topbar">
      <Container size="xl" py="sm">
        <Group justify="space-between">
          <Group className="topbar-brand" gap="sm" wrap="nowrap">
            <Burger
              className="mobile-topbar-menu"
              opened={mobileNavigationOpened}
              onClick={mobileNavigation.toggle}
              size="sm"
              aria-label={mobileNavigationOpened ? 'Close navigation' : 'Open navigation'}
            />
            <Image src="/logo.png" alt="LanGuard" w={42} h={42} radius="sm" />
            <Box className="topbar-brand-details">
              <Group className="topbar-brand-title" gap="xs">
                <Title order={3}>LanGuard</Title>
                <Tooltip label={versionTooltip}>
                  <UnstyledButton
                    className={`version-pill ${hasVersionIndicator ? 'has-update' : ''}`}
                    onClick={() => setChangelogOpened(true)}
                    aria-label={`LanGuard version ${APP_VERSION}`}
                  >
                    v{APP_VERSION}
                    {hasVersionIndicator && <span className="version-dot" aria-hidden="true" />}
                  </UnstyledButton>
                </Tooltip>
                <Tooltip label="GitHub project">
                  <ActionIcon
                    component="a"
                    href="https://github.com/hillaliy/LanGuard"
                    target="_blank"
                    rel="noreferrer"
                    variant="light"
                    color="gray"
                    size="sm"
                    aria-label="GitHub project"
                  >
                    <IconBrandGithub size={17} />
                  </ActionIcon>
                </Tooltip>
                {process.env.NODE_ENV === 'production' && (
                  <Tooltip label="Documentation">
                    <ActionIcon
                      component="a"
                      href="https://hillaliy.github.io/LanGuard/"
                      target="_blank"
                      rel="noreferrer"
                      variant="light"
                      color="gray"
                      size="sm"
                      aria-label="LanGuard documentation"
                    >
                      <Image src="/brands/docusaurus.svg" alt="" w={17} h={17} />
                    </ActionIcon>
                  </Tooltip>
                )}
              </Group>
              <Text size="xs" c="dimmed">Signed in as {userDisplayName(user)}</Text>
            </Box>
          </Group>
          <Group gap="xs">
            <Group className="topbar-clock" gap="xs" wrap="nowrap">
              <IconClock size={18} />
              <Box>
                <Text size="xs" c="var(--muted-text)" lh={1.1}>
                  {formatTopbarDate(currentTime, displayTimeZone)}
                </Text>
                <Text size="sm" fw={700} lh={1.15}>
                  {formatTopbarTime(currentTime, displayTimeZone)}
                </Text>
              </Box>
            </Group>
            <ColorSchemeControl />
            {canRunScans && (
              <Button
                size="sm"
                leftSection={<IconRefresh size={17} />}
                onClick={runScan}
                loading={refreshing}
                disabled={scanIsActive}
                className="topbar-scan-button"
              >
                {scanButtonLabel}
              </Button>
            )}
            <Tooltip label="Refresh">
              <ActionIcon
                variant="light"
                size="lg"
                onClick={() => loadData({
                  quiet: true,
                  notifyOnError: true,
                  refreshIntegrations: true,
                })}
                loading={refreshing}
              >
                <IconRefresh size={19} />
              </ActionIcon>
            </Tooltip>
            <Tooltip label={canManageUsers ? 'Manage users' : 'Edit account'}>
              <ActionIcon
                variant="light"
                size="lg"
                className="user-initials-button"
                onClick={usersModal.open}
                aria-label={canManageUsers ? 'Manage users' : 'Edit account'}
              >
                {userInitials(user)}
              </ActionIcon>
            </Tooltip>
            <Tooltip label="Sign out">
              <ActionIcon
                variant="light"
                color="gray"
                size="lg"
                onClick={logoutModal.open}
                aria-label="Sign out"
              >
                <IconLogout size={19} />
              </ActionIcon>
            </Tooltip>
          </Group>
        </Group>
      </Container>
    </header>
  );
}
