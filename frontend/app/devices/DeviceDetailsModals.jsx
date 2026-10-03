import {
  Alert, Badge, Box, Button, Group, Modal, Paper, Progress, Stack, Text, TextInput,
} from '@mantine/core';
import {
  IconAlertCircle, IconArchive, IconArchiveOff, IconPlayerStop, IconRadar, IconTrash,
} from '@tabler/icons-react';

import { PortGuidanceBadge } from '../components/PortGuidance';
import { formatRoleLabel } from '../utils/device';

export default function DeviceDetailsModals({
  archiveConfirm,
  archiveConfirmOpened,
  cancelDetailedPortScan,
  changeArchiveState,
  deleteConfirm,
  deleteConfirmOpened,
  device,
  portScan,
  portScanError,
  portScanLoading,
  portScanModal,
  portScanOpened,
  portScanSpec,
  remove,
  saving,
  setPortScanSpec,
  startDetailedPortScan,
}) {
  return (
    <>
      <Modal
        opened={deleteConfirmOpened}
        onClose={deleteConfirm.close}
        title="Delete device"
        centered
      >
        <Stack>
          <Text>Are you sure you want to delete this device?</Text>
          <Text size="sm" c="dimmed">
            {device?.name} will be removed from the inventory.
          </Text>
          <Group justify="flex-end">
            <Button variant="default" onClick={deleteConfirm.close}>
              Cancel
            </Button>
            <Button
              color="red"
              leftSection={<IconTrash size={18} />}
              onClick={remove}
              loading={saving}
            >
              Delete
            </Button>
          </Group>
        </Stack>
      </Modal>
      <Modal
        opened={archiveConfirmOpened}
        onClose={archiveConfirm.close}
        title={device?.archived ? 'Restore device' : 'Archive device'}
        centered
      >
        <Stack>
          <Text>
            {device?.archived
              ? `Restore ${device.name} to the active inventory?`
              : `Archive ${device?.name}? Its history will be kept. It will return automatically if detected by a future scan.`}
          </Text>
          <Group justify="flex-end">
            <Button variant="default" onClick={archiveConfirm.close} disabled={saving}>
              Cancel
            </Button>
            <Button
              leftSection={device?.archived
                ? <IconArchiveOff size={18} />
                : <IconArchive size={18} />}
              onClick={changeArchiveState}
              loading={saving}
            >
              {device?.archived ? 'Restore' : 'Archive'}
            </Button>
          </Group>
        </Stack>
      </Modal>
      <Modal
        opened={portScanOpened}
        onClose={portScanModal.close}
        title="Detailed port scan"
        centered
        size="lg"
      >
        <Stack gap="md">
          <Text size="sm" c="dimmed">
            Scan up to 1,024 TCP ports on {device?.name}. Use commas to combine
            individual ports and ranges.
          </Text>
          <TextInput
            label="TCP ports"
            description="Examples: 1-1024 or 22, 80, 443, 8000-8100"
            value={portScanSpec}
            onChange={(event) => setPortScanSpec(event.currentTarget.value)}
            disabled={portScan?.status === 'queued' || portScan?.status === 'running'}
            error={portScanError || null}
          />

          {portScan && (
            <Paper withBorder p="md" radius="sm">
              <Stack gap="sm">
                <Group justify="space-between">
                  <Group gap="xs">
                    <Text fw={600}>Scan status</Text>
                    <Badge
                      color={portScan.status === 'success'
                        ? 'green'
                        : portScan.status === 'failed'
                          ? 'red'
                          : portScan.status === 'cancelled'
                            ? 'gray'
                            : 'blue'}
                      variant="light"
                    >
                      {formatRoleLabel(portScan.status)}
                    </Badge>
                  </Group>
                  <Text size="sm" c="dimmed">
                    {portScan.scanned_ports} / {portScan.total_ports} ports
                  </Text>
                </Group>
                <Progress
                  value={portScan.progress_percent || 0}
                  animated={portScan.status === 'running'}
                />
                <Box>
                  <Text size="xs" c="dimmed">Open ports found</Text>
                  <Group gap={6} mt={6}>
                    {portScan.open_ports?.length ? (
                      portScan.open_ports.map((port) => (
                        <PortGuidanceBadge key={`${port.protocol}-${port.port}`} port={port} />
                      ))
                    ) : <Text size="sm">None yet</Text>}
                  </Group>
                </Box>
                {portScan.error && (
                  <Alert color="red" icon={<IconAlertCircle size={18} />}>
                    {portScan.error}
                  </Alert>
                )}
                {portScan.cancel_requested && portScan.status === 'running' && (
                  <Text size="sm" c="dimmed">Stopping after the current port...</Text>
                )}
              </Stack>
            </Paper>
          )}

          <Group justify="flex-end">
            {(portScan?.status === 'queued' || portScan?.status === 'running') ? (
              <Button
                color="red"
                variant="light"
                leftSection={<IconPlayerStop size={18} />}
                onClick={cancelDetailedPortScan}
                loading={portScanLoading}
                disabled={portScan.cancel_requested}
              >
                Cancel scan
              </Button>
            ) : (
              <Button
                leftSection={<IconRadar size={18} />}
                onClick={startDetailedPortScan}
                loading={portScanLoading}
                disabled={!portScanSpec.trim()}
              >
                Start scan
              </Button>
            )}
          </Group>
        </Stack>
      </Modal>
    </>
  );
}
