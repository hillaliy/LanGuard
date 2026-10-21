import { Box, Group, Stack, Text, Tooltip, UnstyledButton } from '@mantine/core';

import DeviceIconStack from '../components/DeviceIconStack';
import { deviceStatus, displayDeviceName } from '../utils/device';
import { homeMapDeviceStatusClass } from '../utils/homeMap';

export default function HomeMapDeviceButton({ device, onSelectDevice }) {
  const status = deviceStatus(device);
  const risk = String(device.risk_level || device.risk || '').toLowerCase();
  const vendor = String(device.vendor || '').trim();
  const hostname = String(device.hostname || '').trim();
  const deviceName = displayDeviceName(device);
  const accessibleLabel = [deviceName, device.ip, status.label].filter(Boolean).join(', ');
  const tooltip = (
    <Stack gap={4} className="home-map-device-tooltip">
      <Text fw={700} size="sm">{deviceName}</Text>
      <Group gap="xs" justify="space-between" wrap="nowrap">
        <Text c="dimmed" size="xs">IP</Text>
        <Text size="xs">{device.ip || 'Not available'}</Text>
      </Group>
      <Group gap="xs" justify="space-between" wrap="nowrap">
        <Text c="dimmed" size="xs">Status</Text>
        <Text size="xs">{status.label}</Text>
      </Group>
      {(hostname || vendor) && (
        <Box className="home-map-device-tooltip-meta">
          {hostname && (
            <Group gap="xs" justify="space-between" wrap="nowrap">
              <Text c="dimmed" size="xs">Hostname</Text>
              <Text size="xs">{hostname}</Text>
            </Group>
          )}
          {vendor && (
            <Group gap="xs" justify="space-between" wrap="nowrap">
              <Text c="dimmed" size="xs">Vendor</Text>
              <Text size="xs">{vendor}</Text>
            </Group>
          )}
        </Box>
      )}
    </Stack>
  );

  return (
    <Tooltip label={tooltip} withArrow>
      <UnstyledButton
        className={`home-map-device ${homeMapDeviceStatusClass(device)}`}
        onClick={() => onSelectDevice(device)}
        aria-label={accessibleLabel}
      >
        <DeviceIconStack device={device} size={20} />
        {(risk === 'medium' || risk === 'high') && (
          <span className={`home-map-device-risk ${risk}`} aria-hidden="true" />
        )}
      </UnstyledButton>
    </Tooltip>
  );
}
