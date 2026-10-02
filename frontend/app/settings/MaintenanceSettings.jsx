import {
  Box, Button, Divider, Group, Loader, Modal, NumberInput, Stack, Tabs, Text, Title,
} from '@mantine/core';
import { IconCheck, IconDownload, IconTrash } from '@tabler/icons-react';

export default function MaintenanceSettings({ controller }) {
  const {
    cleaningActivity,
    cleanupActivity,
    cleanupConfirm,
    cleanupConfirmOpened,
    cleanupDays,
    cleanupRetentionStatus,
    cleanupTarget,
    cleanupTargetLabels,
    exportDiagnostics,
    exportingDiagnostics,
    openCleanupConfirm,
    saveCleanupRetention,
    setCleanupDays,
    setCleanupRetentionStatus,
  } = controller;

  const cleanupLabel = cleanupTargetLabels[cleanupTarget] || 'activity';

  return (
    <Tabs.Panel value="maintenance" className="settings-category-panel">
      <Stack gap="xl">
        <Box>
          <Title order={3}>Maintenance</Title>
          <Text c="dimmed">Manage retained activity without changing device inventory.</Text>
        </Box>
        <Group justify="space-between" align="center" wrap="wrap">
          <Box>
            <Text fw={700}>Diagnostics report</Text>
            <Text size="sm" c="dimmed">
              Export a sanitized report for support without credentials or device identifiers.
            </Text>
          </Box>
          <Button
            variant="default"
            leftSection={<IconDownload size={18} />}
            onClick={exportDiagnostics}
            loading={exportingDiagnostics}
          >
            Export diagnostics
          </Button>
        </Group>
        <Divider />
        <Group justify="space-between" align="flex-start" wrap="wrap">
          <Box>
            <Text fw={700}>Activity cleanup</Text>
            <Text size="sm" c="dimmed">
              Scheduled cleanup runs every 24 hours using this retention period. Use clean all only for manual resets.
            </Text>
          </Box>
          <Group className="activity-cleanup-controls" gap="sm" align="flex-end">
            <NumberInput
              w={150}
              label="Older than"
              value={cleanupDays}
              description="Saved automatically"
              onChange={(value) => {
                setCleanupDays(value === '' || value === null ? 90 : Number(value));
                setCleanupRetentionStatus('pending');
              }}
              onBlur={saveCleanupRetention}
              onKeyDown={(event) => {
                if (event.key === 'Enter') {
                  event.currentTarget.blur();
                }
              }}
              min={1}
              max={3650}
              suffix=" days"
            />
            {cleanupRetentionStatus === 'saving' && (
              <Group gap={6} pb={8} wrap="nowrap">
                <Loader size="xs" />
                <Text size="xs" c="dimmed">Saving</Text>
              </Group>
            )}
            {cleanupRetentionStatus === 'saved' && (
              <Group gap={6} pb={8} wrap="nowrap">
                <IconCheck size={15} color="var(--mantine-color-teal-6)" />
                <Text size="xs" c="teal">Saved</Text>
              </Group>
            )}
            <Button
              color="red"
              variant="light"
              leftSection={<IconTrash size={18} />}
              onClick={() => openCleanupConfirm('events')}
              loading={cleaningActivity === 'events'}
            >
              Clean events
            </Button>
            <Button
              color="red"
              variant="light"
              leftSection={<IconTrash size={18} />}
              onClick={() => openCleanupConfirm('scan_runs')}
              loading={cleaningActivity === 'scan_runs'}
            >
              Clean history
            </Button>
            <Button
              color="red"
              variant="light"
              leftSection={<IconTrash size={18} />}
              onClick={() => openCleanupConfirm('notifications')}
              loading={cleaningActivity === 'notifications'}
            >
              Clean notifications
            </Button>
            <Button
              color="red"
              variant="light"
              leftSection={<IconTrash size={18} />}
              onClick={() => openCleanupConfirm('dns_activity')}
              loading={cleaningActivity === 'dns_activity'}
            >
              Clean DNS activity
            </Button>
          </Group>
        </Group>
      </Stack>
      <Modal
        opened={cleanupConfirmOpened}
        onClose={cleanupConfirm.close}
        title={`Clean ${cleanupLabel}`}
        centered
      >
        <Stack>
          <Text>Delete {cleanupLabel} records older than {cleanupDays} days?</Text>
          <Text size="sm" c="dimmed">
            Device inventory and current device data will not be deleted.
            {cleanupTarget === 'events'
              ? ' Notifications linked to deleted events will be kept, but their event link will be cleared.'
              : ''}
            {cleanupTarget === 'scan_runs' ? ' Running scans are never deleted.' : ''}
            {cleanupTarget === 'dns_activity'
              ? ' Both device DNS aggregates and unmatched-client diagnostics are included.'
              : ''}
            {' '}Clean all deletes every record of this type and cannot be undone.
          </Text>
          <Group justify="flex-end">
            <Button
              color="red"
              leftSection={<IconTrash size={18} />}
              loading={Boolean(cleaningActivity)}
              onClick={async () => {
                const cleaned = await cleanupActivity(true);
                if (cleaned) cleanupConfirm.close();
              }}
            >
              Clean all
            </Button>
            <Button variant="default" onClick={cleanupConfirm.close}>
              Cancel
            </Button>
            <Button
              color="red"
              variant="light"
              leftSection={<IconTrash size={18} />}
              loading={Boolean(cleaningActivity)}
              onClick={async () => {
                const cleaned = await cleanupActivity(false);
                if (cleaned) cleanupConfirm.close();
              }}
            >
              Clean
            </Button>
          </Group>
        </Stack>
      </Modal>
    </Tabs.Panel>
  );
}
