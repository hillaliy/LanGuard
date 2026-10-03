import { Alert, Box, Button, Group, Modal, Stack, Text } from '@mantine/core';
import { IconLogout, IconRefresh } from '@tabler/icons-react';

import UserManagementModal from '../auth/UserManagementModal';
import ScanDetailsContent from '../dashboard/ScanDetailsContent';
import { APP_VERSION, CHANGELOG_ENTRIES } from '../version';

export default function AppShellModals({ controller, user }) {
  const c = controller;

  return (
    <>
      <Modal
        opened={c.scanDetailsOpened}
        onClose={c.scanDetailsModal.close}
        title="Latest scan details"
        centered
        size="lg"
      >
        <ScanDetailsContent
          scanStatus={c.scanStatus}
          scanVisibility={c.scanVisibility}
          timeZone={c.displayTimeZone}
        />
      </Modal>

      <UserManagementModal
        opened={c.usersModalOpened}
        onClose={c.usersModal.close}
        currentUser={user}
        onCurrentUserUpdated={c.updateCurrentUser}
      />

      <Modal
        opened={c.logoutModalOpened}
        onClose={c.logoutModal.close}
        title="Log off"
        centered
        closeOnClickOutside={!c.loggingOut}
        closeOnEscape={!c.loggingOut}
        withCloseButton={!c.loggingOut}
      >
        <Stack>
          <Text>Are you sure you want to log off?</Text>
          <Group justify="flex-end">
            <Button variant="default" onClick={c.logoutModal.close} disabled={c.loggingOut}>
              Cancel
            </Button>
            <Button
              color="red"
              leftSection={<IconLogout size={18} />}
              onClick={c.logout}
              loading={c.loggingOut}
            >
              Log off
            </Button>
          </Group>
        </Stack>
      </Modal>

      <Modal
        opened={c.changelogOpened}
        onClose={c.closeChangelog}
        title={`What's new in v${APP_VERSION}`}
        centered
        size="90rem"
      >
        <Stack>
          {c.hasVersionUpdate && (
            <Alert color="blue" icon={<IconRefresh size={18} />}>
              Version v{c.latestVersion} is available. Pull the latest Docker images and restart
              the containers to update.
            </Alert>
          )}
          {CHANGELOG_ENTRIES.map((entry) => (
            <Box key={entry.version}>
              <Group justify="space-between" mb="xs">
                <Text fw={700}>Version {entry.version}</Text>
                <Text size="sm" c="dimmed">{entry.date}</Text>
              </Group>
              <Stack gap={4}>
                {entry.items.map((item) => (
                  <Group key={item} gap="xs" align="flex-start" wrap="nowrap">
                    <span className="changelog-bullet" />
                    <Text size="xs">{item}</Text>
                  </Group>
                ))}
              </Stack>
            </Box>
          ))}
          <Group justify="flex-end">
            <Button onClick={c.closeChangelog}>Done</Button>
          </Group>
        </Stack>
      </Modal>
    </>
  );
}
