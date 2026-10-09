import { ActionIcon, Box, Button, Group, Stack, Text, Title, Tooltip } from '@mantine/core';
import {
  IconArchive,
  IconArchiveOff,
  IconArrowLeft,
  IconDeviceFloppy,
  IconEdit,
  IconGitMerge,
  IconPower,
  IconRadar,
} from '@tabler/icons-react';

import {
  DeviceClassificationBadge,
  GatewayBadge,
  RiskBadge,
} from '../components/DeviceBadges';
import DeviceIconStack from '../components/DeviceIconStack';
import { displayDeviceName } from '../utils/device';

export default function DeviceDetailsHeader({
  archiveConfirm,
  canEditDevices,
  canRunScans,
  cancelEditing,
  currentStatus,
  device,
  editing,
  onBack,
  openPortScan,
  openMerge,
  save,
  saving,
  startEditing,
  wake,
  waking,
}) {
  const primaryInterface = device?.interfaces?.find((item) => item.primary);
  const primaryInterfaceOnline = primaryInterface
    ? primaryInterface.status === 'online'
    : device?.status === 'online';

  return (
    <div className="device-detail-header">
      <Group className="device-detail-summary" gap="sm" align="flex-start" wrap="nowrap">
        <Tooltip label="Back to devices">
          <ActionIcon variant="subtle" color="gray" onClick={onBack} aria-label="Back to devices">
            <IconArrowLeft size={20} />
          </ActionIcon>
        </Tooltip>
        {device && (
          <span className="device-detail-icon">
            <DeviceIconStack device={device} size={26} />
          </span>
        )}
        <Box className="device-detail-identity">
          <Group className="device-detail-title-row" gap="xs" wrap="wrap">
            <Title order={2}>{device ? displayDeviceName(device) : 'Device'}</Title>
            {(device?.archived || device?.is_visitor) && (
              <DeviceClassificationBadge device={device} compact />
            )}
            {device && <GatewayBadge device={device} compact />}
            {device && <RiskBadge device={device} compact />}
          </Group>
          {device && (
            <Stack className="device-detail-subtitle" gap={0}>
              {String(device.hostname || '').trim() && (
                <Text c="dimmed">{device.hostname}</Text>
              )}
              {String(device.vendor || '').trim() && (
                <Text c="dimmed">{device.vendor}</Text>
              )}
              {!String(device.hostname || '').trim() && !String(device.vendor || '').trim() && (
                <Text c="dimmed">-</Text>
              )}
            </Stack>
          )}
          {currentStatus && (
            <Group gap="xs" mt={4}>
              <span className={`status-dot ${currentStatus.dot}`} />
              <Text size="sm">{currentStatus.label}</Text>
              {device?.status_source_display && (
                <Text size="sm" c="dimmed">via {device.status_source_display}</Text>
              )}
            </Group>
          )}
        </Box>
      </Group>
      {device && (canEditDevices || canRunScans) && (
        editing && canEditDevices ? (
          <Group className="device-detail-actions" gap="xs" wrap="nowrap">
            <Button variant="default" onClick={cancelEditing} disabled={saving}>Cancel</Button>
            <Button leftSection={<IconDeviceFloppy size={18} />} onClick={save} loading={saving}>
              Save
            </Button>
          </Group>
        ) : (
          <Group className="device-detail-actions" gap="xs" wrap="nowrap">
            {(canEditDevices || canRunScans) && !device.archived && primaryInterfaceOnline && (
              <Button
                variant="light"
                leftSection={<IconRadar size={18} />}
                onClick={openPortScan}
              >
                Detailed port scan
              </Button>
            )}
            {canRunScans && !device.archived && (
              <Button
                variant="light"
                leftSection={<IconPower size={18} />}
                loading={waking}
                onClick={wake}
              >
                Wake device
              </Button>
            )}
            {canEditDevices && (
              <>
                {!device.archived && (
                  <Button
                    variant="default"
                    leftSection={<IconGitMerge size={18} />}
                    onClick={openMerge}
                  >
                    Merge interfaces
                  </Button>
                )}
                <Button
                  variant="default"
                  leftSection={device.archived
                    ? <IconArchiveOff size={18} />
                    : <IconArchive size={18} />}
                  onClick={archiveConfirm.open}
                >
                  {device.archived ? 'Restore device' : 'Archive device'}
                </Button>
                <Button leftSection={<IconEdit size={18} />} onClick={startEditing}>
                  Edit device
                </Button>
              </>
            )}
          </Group>
        )
      )}
    </div>
  );
}
