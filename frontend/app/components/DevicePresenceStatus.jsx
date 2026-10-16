import { Group, Stack, Text } from '@mantine/core';
import { IconCircleFilled, IconClock, IconMoon } from '@tabler/icons-react';

const states = {
  online: { label: 'Online', color: 'teal', Icon: IconCircleFilled },
  recently_seen: { label: 'Recently seen', color: 'yellow', Icon: IconClock },
  sleeping: { label: 'Likely sleeping', color: 'dimmed', Icon: IconMoon },
  offline: { label: 'Offline', color: 'dimmed', Icon: IconCircleFilled },
};

const sourceDescriptions = {
  arp: 'Responded to ARP discovery',
  local: 'Detected on the local scanner interface',
  port: 'Responded on open ports',
  icmp: 'Responded to ICMP ping',
  recent: 'Recently seen during scan grace period',
  none: 'No discovery signal responded',
};

export default function DevicePresenceStatus({ device, inline = false }) {
  const value = device.status || (device.online ? 'online' : 'offline');
  const status = states[value] || {
    label: device.status_display || 'Unknown', color: 'dimmed', Icon: IconCircleFilled,
  };
  const source = device.status_source_display;
  const reason = String(device.status_reason || '').trim();
  const hasAdditionalDetail = reason
    && reason.replace(/\.$/, '') !== sourceDescriptions[device.status_source];
  const defaultDescription = value === 'online'
    ? (source && !['none', 'recent'].includes(device.status_source)
      ? `Detected via ${source}` : 'Responding to discovery')
    : (states[value] ? 'No current response' : 'No discovery information');
  const description = hasAdditionalDetail ? reason : defaultDescription;
  const StatusIcon = status.Icon;
  const Container = inline ? Group : Stack;

  return (
    <Container gap={inline ? 'xs' : 2} align={inline ? 'center' : 'flex-start'}>
      <Group gap={6} wrap="nowrap" c={status.color}>
        <StatusIcon size={StatusIcon === IconCircleFilled ? 9 : 16} aria-hidden="true" />
        <Text size="sm" fw={500}>{status.label}</Text>
      </Group>
      <Text
        size="xs"
        c="dimmed"
        maw={inline ? 480 : 320}
        className="wrap-text"
        style={{ whiteSpace: 'normal' }}
      >
        {description}
      </Text>
    </Container>
  );
}
