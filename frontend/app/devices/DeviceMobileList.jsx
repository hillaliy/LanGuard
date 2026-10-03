import { Box, Checkbox, Group, SimpleGrid, Stack, Text, UnstyledButton } from '@mantine/core';
import { DeviceClassificationBadge, GatewayBadge, RiskBadge } from '../components/DeviceBadges';
import PortSummary from '../components/PortGuidance';
import { formatDate } from '../utils/date';
import { displayDeviceName, formatRoleLabel } from '../utils/device';
import { DeviceListIcon, DeviceStatusInline } from './DeviceListElements';
import { handleDeviceRowClick, handleDeviceRowKeyDown } from './deviceListUtils';

export default function DeviceMobileList({
  devices,
  bulkEdit,
  showFirstSeen,
  timeZone,
  onSelectDevice,
}) {
  const { enabled, selectedDeviceIds, onToggleDevice } = bulkEdit;
  return (
    <Stack className="device-mobile-list" gap={0}>
      {devices.map((device) => {
        const selected = selectedDeviceIds.includes(device.id);
        return (
          <UnstyledButton
            component="div"
            className={`device-mobile-row${enabled ? ' bulk-edit' : ''}${selected ? ' selected' : ''}`}
            key={device.id}
            role={enabled ? 'checkbox' : 'button'}
            aria-label={enabled
              ? `Select ${displayDeviceName(device)}`
              : `Open ${displayDeviceName(device)} details`}
            aria-checked={enabled ? selected : undefined}
            tabIndex={0}
            onClick={(event) => handleDeviceRowClick(
              event, device, enabled, onToggleDevice, onSelectDevice
            )}
            onKeyDown={(event) => handleDeviceRowKeyDown(
              event, device, enabled, onToggleDevice, onSelectDevice
            )}
          >
            <Group justify="space-between" align="flex-start" wrap="nowrap">
              <Group gap="sm" align="flex-start" wrap="nowrap" className="device-mobile-main">
                {enabled && (
                  <Checkbox
                    checked={selected}
                    readOnly
                    tabIndex={-1}
                    aria-label={`Select ${displayDeviceName(device)}`}
                    pointerEvents="none"
                  />
                )}
                <DeviceListIcon
                  device={device}
                  className="device-mobile-icon"
                  size={18}
                  interfaceEnabled={!enabled}
                />
                <Box className="device-mobile-title">
                  <Text fw={700} className="truncate-cell">{displayDeviceName(device)}</Text>
                  <DeviceStatusInline device={device} muted />
                </Box>
              </Group>
              <Group className="device-mobile-badges" gap={6} justify="flex-end" wrap="wrap">
                <RiskBadge device={device} compact />
                <GatewayBadge device={device} compact />
                <DeviceClassificationBadge device={device} />
              </Group>
            </Group>
            <SimpleGrid className="device-mobile-details" cols={2} spacing="xs" mt="sm">
              <Box>
                <Text size="xs" c="dimmed">IP / MAC</Text>
                <Text size="sm" className="mobile-mono-value">{device.ip}</Text>
                <Text size="xs" c="dimmed" className="mobile-mono-value device-list-mac-value">
                  {device.mac || '-'}
                </Text>
              </Box>
              <Box>
                <Text size="xs" c="dimmed">{showFirstSeen ? 'First seen' : 'Last seen'}</Text>
                <Text size="sm">
                  {formatDate(showFirstSeen ? device.firstseen : device.lastseen, timeZone)}
                </Text>
              </Box>
              <Box className="device-mobile-wide">
                <Text size="xs" c="dimmed">Room</Text>
                <Text size="sm">{device.room || '-'}</Text>
              </Box>
              <Box className="device-mobile-wide">
                <Text size="xs" c="dimmed">Role</Text>
                <Text size="sm">{formatRoleLabel(device.role)}</Text>
              </Box>
              <Box className="device-mobile-wide">
                <Text size="xs" c="dimmed">Ports</Text>
                <PortSummary ports={device.open_ports || []} />
              </Box>
            </SimpleGrid>
          </UnstyledButton>
        );
      })}
    </Stack>
  );
}
