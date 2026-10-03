import { Box, Checkbox, Group, Stack, Text, UnstyledButton } from '@mantine/core';
import { DeviceClassificationBadge, GatewayBadge, RiskBadge } from '../components/DeviceBadges';
import PortSummary from '../components/PortGuidance';
import { formatDate } from '../utils/date';
import { displayDeviceName, formatRoleLabel } from '../utils/device';
import { DeviceListIcon, DeviceStatusInline, deviceSubtitle } from './DeviceListElements';
import { handleDeviceRowClick, handleDeviceRowKeyDown } from './deviceListUtils';

export default function DeviceDesktopList({
  devices,
  bulkEdit,
  showFirstSeen,
  timeZone,
  listRef,
  onSelectDevice,
}) {
  const { enabled, selectedDeviceIds, onToggleDevice } = bulkEdit;
  return (
    <Stack ref={listRef} className="device-list" gap={0}>
      {devices.map((device) => {
        const selected = selectedDeviceIds.includes(device.id);
        return (
          <UnstyledButton
            component="div"
            className={`device-list-row${enabled ? ' bulk-edit' : ''}${selected ? ' selected' : ''}`}
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
            {enabled && (
              <Checkbox
                checked={selected}
                readOnly
                tabIndex={-1}
                aria-label={`Select ${displayDeviceName(device)}`}
                pointerEvents="none"
              />
            )}
            <Group className="device-list-primary" gap="md" align="center" wrap="nowrap">
              <DeviceListIcon
                device={device}
                className="device-list-icon"
                size={21}
                interfaceEnabled={!enabled}
              />
              <Box className="device-list-title">
                <Group gap="xs" wrap="nowrap">
                  <Text fw={800} className="truncate-cell">{displayDeviceName(device)}</Text>
                  <Stack className="device-list-state-badges" gap={4}>
                    <DeviceClassificationBadge device={device} />
                    <GatewayBadge device={device} compact />
                  </Stack>
                </Group>
                <Text size="sm" c="dimmed" className="truncate-cell">
                  {deviceSubtitle(device)}
                </Text>
              </Box>
            </Group>
            <div className="device-list-meta">
              <Box>
                <Text size="xs" c="dimmed">Status</Text>
                <DeviceStatusInline device={device} muted />
              </Box>
              <Box>
                <Text size="xs" c="dimmed">IP / MAC</Text>
                <Text size="sm" fw={700} className="mobile-mono-value device-list-ip-value">
                  {device.ip}
                </Text>
                <Text size="xs" c="dimmed" className="mobile-mono-value device-list-mac-value">
                  {device.mac || '-'}
                </Text>
              </Box>
              <Box>
                <Text size="xs" c="dimmed">Room</Text>
                <Text className="device-list-meta-value">{device.room || '-'}</Text>
              </Box>
              <Box>
                <Text size="xs" c="dimmed">Role</Text>
                <Text className="device-list-meta-value">{formatRoleLabel(device.role)}</Text>
              </Box>
              <Box>
                <Text size="xs" c="dimmed">Ports</Text>
                <PortSummary ports={device.open_ports || []} />
              </Box>
              <Box>
                <Text size="xs" c="dimmed">Risk</Text>
                <RiskBadge device={device} compact />
              </Box>
              <Box className="device-list-last-seen">
                <Text size="xs" c="dimmed">{showFirstSeen ? 'First seen' : 'Last seen'}</Text>
                <Text className="device-list-last-seen-value">
                  {formatDate(showFirstSeen ? device.firstseen : device.lastseen, timeZone)}
                </Text>
              </Box>
            </div>
          </UnstyledButton>
        );
      })}
    </Stack>
  );
}
