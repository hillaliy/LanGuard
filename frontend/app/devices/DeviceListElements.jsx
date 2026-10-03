import { Group, Text, Tooltip, UnstyledButton } from '@mantine/core';
import { IconExternalLink } from '@tabler/icons-react';
import DeviceIconStack from '../components/DeviceIconStack';
import { deviceStatus, displayDeviceName, validExternalUrl } from '../utils/device';

export function DeviceListIcon({ device, className, size, interfaceEnabled = true }) {
  const externalUrl = String(
    device?.effective_external_url || device?.external_url || ''
  ).trim();
  const icon = <DeviceIconStack device={device} size={size} />;
  if (!interfaceEnabled || !externalUrl || !validExternalUrl(externalUrl)) {
    return <span className={className}>{icon}</span>;
  }

  return (
    <Tooltip label="Open device interface">
      <UnstyledButton
        component="a"
        className={`${className} device-interface-icon`}
        href={externalUrl}
        target="_blank"
        rel="noopener noreferrer"
        aria-label={`Open ${displayDeviceName(device)} interface in a new tab`}
        onClick={(event) => event.stopPropagation()}
        onKeyDown={(event) => event.stopPropagation()}
      >
        {icon}
        <span className="device-interface-marker" aria-hidden="true">
          <IconExternalLink size={10} stroke={2.5} />
        </span>
      </UnstyledButton>
    </Tooltip>
  );
}

export function DeviceStatusInline({ device, muted = false }) {
  const status = deviceStatus(device);
  return (
    <Group className="device-status-inline" gap="xs" wrap="nowrap">
      <span className={`status-dot ${status.dot}`} />
      <Text size="sm" c={muted ? 'dimmed' : undefined}>{status.label}</Text>
    </Group>
  );
}

export function deviceSubtitle(device) {
  const hostname = String(device?.hostname || '').trim();
  const vendor = String(device?.vendor || '').trim();
  return [hostname, vendor].filter(Boolean).join(' - ') || '-';
}
