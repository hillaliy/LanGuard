import { useMemo } from 'react';
import { Badge, Box, Group, Paper, Stack, Text, Title, Tooltip, UnstyledButton } from '@mantine/core';
import { IconArrowRight, IconHistory, IconShieldLock } from '@tabler/icons-react';

import { apiRequest } from '../api';
import { deviceRisk } from '../components/DeviceBadges';
import DeviceIconStack from '../components/DeviceIconStack';
import { eventDeviceId } from '../utils/activity';
import { formatDate } from '../utils/date';
import { displayDeviceName, normalizeMacText } from '../utils/device';

function eventDeviceForRow(event, deviceById, devices) {
  const id = eventDeviceId(event);
  if (id !== null && id !== undefined && deviceById.has(String(id))) {
    return deviceById.get(String(id));
  }

  const metadata = event?.metadata || {};
  const eventMac = normalizeMacText(metadata.mac);
  const eventIp = String(metadata.ip || '').trim();
  return devices.find((device) => {
    if (eventMac && normalizeMacText(device.mac) === eventMac) return true;
    return eventIp && String(device.ip || '').trim() === eventIp;
  }) || null;
}

function DashboardInsightHeader({ icon, title, count, color, onOpen, openLabel }) {
  const countBadge = (
    <Badge
      className="dashboard-insight-count"
      color={color}
      variant="light"
      rightSection={onOpen ? <IconArrowRight size={15} aria-hidden="true" /> : null}
    >
      {count}
    </Badge>
  );

  return (
    <Group justify="space-between" align="center" mb="md" wrap="nowrap">
      <Group gap="sm" wrap="nowrap">
        {icon}
        <Title order={3}>{title}</Title>
      </Group>
      {onOpen ? (
        <Tooltip label={openLabel}>
          <UnstyledButton
            className="dashboard-insight-count-link"
            onClick={onOpen}
            aria-label={`${openLabel}: ${count}`}
          >
            {countBadge}
          </UnstyledButton>
        </Tooltip>
      ) : countBadge}
    </Group>
  );
}

function DashboardEventRow({ event, timeZone, device, onSelectDevice, onError }) {
  async function handleSelectEventDevice() {
    if (device) {
      onSelectDevice(device);
      return;
    }
    const id = eventDeviceId(event);
    if (id === null || id === undefined) return;

    try {
      const payload = await apiRequest(`device/?id=${id}`);
      if (payload.data) onSelectDevice(payload.data);
    } catch (error) {
      onError?.(error);
    }
  }

  const content = (
    <>
      <span className="dashboard-insight-row-icon blue">
        <IconHistory size={20} />
      </span>
      <Box className="dashboard-insight-row-body">
        <Text fw={800} className="truncate-cell">
          {event.message || event.event_type_display || event.event_type}
        </Text>
        <Text size="sm" c="dimmed" className="truncate-cell">
          {[event.event_type_display || event.event_type, formatDate(event.created_at, timeZone)]
            .filter(Boolean)
            .join(' - ')}
        </Text>
      </Box>
    </>
  );

  if (device || eventDeviceId(event) !== null && eventDeviceId(event) !== undefined) {
    return (
      <UnstyledButton
        className="dashboard-insight-row dashboard-insight-button"
        aria-label={`Open ${event.message || 'changed device'}`}
        onClick={handleSelectEventDevice}
      >
        {content}
      </UnstyledButton>
    );
  }

  return <div className="dashboard-insight-row">{content}</div>;
}

function DashboardAttentionRow({ device, onSelectDevice }) {
  const risk = deviceRisk(device);
  const attentionReasons = Array.isArray(device.attention_reasons)
    ? device.attention_reasons.filter(Boolean)
    : [];
  const reason = attentionReasons.join(', ')
    || (!device.known ? 'Unknown device' : `${risk.label} risk`);
  const offlineOverWeek = attentionReasons.some((item) => item.startsWith('Offline for over '));
  const badgeLabel = offlineOverWeek && risk.level === 'low' ? 'Offline' : risk.label;
  const badgeColor = offlineOverWeek && risk.level === 'low' ? 'orange' : risk.color;

  return (
    <UnstyledButton
      className="dashboard-insight-row dashboard-insight-button"
      onClick={() => onSelectDevice(device)}
    >
      <span className="dashboard-insight-row-icon orange">
        <DeviceIconStack device={device} size={18} />
      </span>
      <Box className="dashboard-insight-row-body">
        <Text fw={800} className="truncate-cell">{displayDeviceName(device)}</Text>
        <Tooltip
          label={attentionReasons.join('\n')}
          multiline
          withArrow
          disabled={!attentionReasons.length}
        >
          <Text size="sm" c="dimmed" className="truncate-cell">
            {[reason, device.ip].filter(Boolean).join(' - ')}
          </Text>
        </Tooltip>
      </Box>
      <Badge className="dashboard-insight-risk" color={badgeColor} variant="light">
        {badgeLabel}
      </Badge>
    </UnstyledButton>
  );
}

function DashboardEmptyState({ label }) {
  return <Text c="dimmed" fw={700} py="sm">{label}</Text>;
}

export default function DashboardInsightCards({
  events = [],
  devices = [],
  onSelectDevice,
  onOpenAttentionDevices,
  onOpenRecentChanges,
  onError,
  timeZone,
}) {
  const deviceById = useMemo(
    () => new Map(devices.map((device) => [String(device.id), device])),
    [devices]
  );
  const attentionDevices = devices
    .filter((device) => (
      device.needs_attention
      ?? (!device.known || ['high', 'medium'].includes(device.risk_level))
    ))
    .sort((first, second) => {
      const riskWeight = { high: 0, medium: 1, low: 2 };
      const firstWeight = first.known ? riskWeight[first.risk_level] ?? 2 : -1;
      const secondWeight = second.known ? riskWeight[second.risk_level] ?? 2 : -1;
      return firstWeight - secondWeight
        || String(first.ip).localeCompare(String(second.ip), undefined, { numeric: true });
    });

  return (
    <div className="dashboard-insight-grid">
      <Paper className="dashboard-insight-card" radius="md">
        <DashboardInsightHeader
          icon={<IconHistory size={26} />}
          title="Recently Changed"
          count={events.length}
          color="blue"
          onOpen={onOpenRecentChanges}
          openLabel="View all recent changes"
        />
        <Stack className="dashboard-insight-list" gap="sm">
          {events.length ? events.map((event) => (
            <DashboardEventRow
              key={event.id}
              event={event}
              timeZone={timeZone}
              device={eventDeviceForRow(event, deviceById, devices)}
              onSelectDevice={onSelectDevice}
              onError={onError}
            />
          )) : (
            <DashboardEmptyState label="No recent changes" />
          )}
        </Stack>
      </Paper>

      <Paper className="dashboard-insight-card" radius="md">
        <DashboardInsightHeader
          icon={<IconShieldLock size={26} />}
          title="Needs Attention"
          count={attentionDevices.length}
          color="orange"
          onOpen={onOpenAttentionDevices}
          openLabel="View all devices needing attention"
        />
        <Stack className="dashboard-insight-list" gap="sm">
          {attentionDevices.map((device) => (
            <DashboardAttentionRow
              key={device.id}
              device={device}
              onSelectDevice={onSelectDevice}
            />
          ))}
          {!attentionDevices.length && (
            <DashboardEmptyState label="No devices need attention" />
          )}
        </Stack>
      </Paper>
    </div>
  );
}
