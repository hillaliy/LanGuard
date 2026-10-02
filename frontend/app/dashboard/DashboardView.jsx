import { useMemo } from 'react';
import {
  Alert,
  Badge,
  Box,
  Divider,
  Group,
  Paper,
  SimpleGrid,
  Stack,
  Text,
  ThemeIcon,
  Title,
  Tooltip,
  UnstyledButton,
} from '@mantine/core';
import {
  IconAlertCircle,
  IconArrowRight,
  IconClock,
  IconDeviceDesktop,
  IconGauge,
  IconHistory,
  IconLine,
  IconNetwork,
  IconQuestionMark,
  IconShieldCheck,
  IconShieldLock,
  IconWifi,
} from '@tabler/icons-react';
import { apiRequest } from '../api';
import { deviceRisk } from '../components/DeviceBadges';
import DeviceIconStack from '../components/DeviceIconStack';
import ScanRangesSummary from '../components/ScanRangesSummary';
import SummaryMetric from '../components/SummaryMetric';
import { eventDeviceId } from '../utils/activity';
import { formatDate, formatDuration } from '../utils/date';
import { displayDeviceName, normalizeMacText } from '../utils/device';
import { formatScanRange, normalizedScanRanges } from '../utils/scan';

function ThemeIconLike({ children, color, size = 42 }) {
  return (
    <ThemeIcon
      color={color}
      size={size}
      radius="md"
      variant="light"
      style={{
        background: `var(--mantine-color-${color}-1)`,
        color: `var(--mantine-color-${color}-7)`,
      }}
    >
      {children}
    </ThemeIcon>
  );
}

function DashboardStatusCards({ counters = {} }) {
  return (
    <div className="dashboard-status-grid">
      <DashboardStatusCard
        icon={<IconDeviceDesktop size={30} />}
        label="Devices"
        value={counters.all_devices ?? 0}
        secondaryItems={[
          { value: counters.visitor_devices, singular: 'visitor', plural: 'visitors' },
          { value: counters.archived_devices, singular: 'archived', plural: 'archived' },
        ]}
        color="blue"
      />
      <DashboardStatusCard
        icon={<IconWifi size={30} />}
        label="Online"
        value={counters.online_devices ?? 0}
        secondaryItems={[
          { value: counters.online_visitors, singular: 'visitor', plural: 'visitors' },
        ]}
        color="green"
      />
      <DashboardStatusCard
        icon={<IconQuestionMark size={30} />}
        label="Unknown"
        value={counters.new_devices ?? 0}
        color="orange"
      />
      <DashboardStatusCard
        icon={<IconNetwork size={30} />}
        label="Open Ports"
        value={counters.open_ports ?? 0}
        color="purple"
      />
    </div>
  );
}

function DashboardStatusCard({ icon, label, value, secondaryItems = [], color }) {
  const visibleSecondaryItems = secondaryItems
    .map((item) => ({ ...item, value: Number(item.value) || 0 }))
    .filter((item) => item.value > 0);

  return (
    <Paper className="dashboard-status-card">
      <ThemeIcon
        className={`dashboard-status-icon ${color}`}
        color={color}
        size={56}
        radius={14}
        variant="light"
      >
        {icon}
      </ThemeIcon>
      <Box>
        <Text className="dashboard-status-label" fw={800}>{label}</Text>
        <Text className="dashboard-status-value" fw={900}>{value}</Text>
        {visibleSecondaryItems.length > 0 && (
          <Text component="div" className="dashboard-status-secondary" c="dimmed" fw={700}>
            {visibleSecondaryItems.map((item) => (
              <span className="dashboard-status-secondary-item" key={item.singular}>
                {item.value.toLocaleString()} {item.value === 1 ? item.singular : item.plural}
              </span>
            ))}
          </Text>
        )}
      </Box>
    </Paper>
  );
}

function DashboardCardHeader({ icon, title, badge }) {
  return (
    <Group className="dashboard-card-header" justify="space-between" align="center" wrap="nowrap">
      <Group className="dashboard-card-header-title" gap="sm" wrap="nowrap">
        {icon}
        <Title order={3}>{title}</Title>
      </Group>
      {badge}
    </Group>
  );
}

function SummaryRow({ label, value }) {
  return (
    <Group justify="space-between" wrap="nowrap">
      <Text c="dimmed" fw={600}>{label}</Text>
      <Text fw={800}>{value}</Text>
    </Group>
  );
}

function NetworkHealthCard({ counters = {} }) {
  const totalDevices = Number(counters.all_devices) || 0;
  const newDevices = Number(counters.new_devices) || 0;
  const knownCoverage = totalDevices > 0
    ? Math.round(((totalDevices - newDevices) / totalDevices) * 100)
    : 100;
  const healthColor = knownCoverage >= 95 ? 'teal' : 'orange';
  const healthLabel = knownCoverage >= 95 ? 'Good' : 'Review';

  return (
    <Paper className="dashboard-summary-card network-health-card" radius="md">
      <DashboardCardHeader
        icon={<IconLine size={28} />}
        title="Network Health"
        badge={(
          <Badge className="dashboard-status-badge" color={healthColor} variant="light">
            {healthLabel}
          </Badge>
        )}
      />
      <div className="network-health-meter" aria-hidden="true">
        <div
          className={`network-health-meter-fill ${healthColor}`}
          style={{ width: `${Math.min(100, Math.max(0, knownCoverage))}%` }}
        />
      </div>
      <Stack gap={8} mt="lg">
        <SummaryRow label="Known coverage" value={`${knownCoverage}%`} />
        <SummaryRow label="Online devices" value={counters.online_devices ?? 0} />
        <SummaryRow label="Open ports" value={counters.open_ports ?? 0} />
      </Stack>
    </Paper>
  );
}

function AutomaticScanningCard({ appSettings, networkRanges, networkRangeLabels }) {
  const configuredRanges = normalizedScanRanges(networkRanges);
  const ranges = configuredRanges.length
    ? configuredRanges
    : normalizedScanRanges(appSettings?.scan_ranges, appSettings?.ip_range);
  const rangeLabels = Object.keys(networkRangeLabels || {}).length
    ? networkRangeLabels
    : appSettings?.scan_range_labels || {};

  return (
    <Paper className="dashboard-summary-card automatic-scanning-card" radius="md">
      <DashboardCardHeader
        icon={(
          <ThemeIconLike color="blue">
            <IconClock size={24} />
          </ThemeIconLike>
        )}
        title="Automatic Scanning"
        badge={(
          <Badge className="dashboard-status-badge" color="blue" variant="light">
            Enabled
          </Badge>
        )}
      />
      <SimpleGrid cols={2} mt="xl">
        <SummaryMetric label="Interval" value={appSettings?.scan_interval ? `${appSettings.scan_interval} min` : '-'} />
        <SummaryMetric
          label="Ranges"
          value={<ScanRangesSummary ranges={ranges} labels={rangeLabels} namesOnly />}
          align="right"
        />
      </SimpleGrid>
    </Paper>
  );
}

function LatestScanCard({ scanStatus, scanVisibility, timeZone, onOpenDetails }) {
  const statusColor = scanVisibility?.is_scanning
    ? 'blue'
    : scanStatus?.status === 'failed'
      ? 'red'
      : 'teal';
  const statusLabel = scanVisibility?.is_scanning ? 'Scanning' : scanStatus?.status || '-';

  return (
    <Paper
      className="dashboard-summary-card latest-scan-card dashboard-clickable-card"
      radius="md"
      component="button"
      type="button"
      onClick={onOpenDetails}
    >
      <DashboardCardHeader
        icon={<IconClock size={28} />}
        title="Latest Scan"
        badge={(
          <Badge className="dashboard-status-badge" color={statusColor} variant="light">
            {statusLabel}
          </Badge>
        )}
      />
      <SimpleGrid cols={2}>
        <SummaryMetric label="Devices" value={scanStatus?.devices_seen ?? 0} />
        <SummaryMetric label="Duration" value={formatDuration(scanVisibility?.duration_seconds)} />
        <SummaryMetric label="Started" value={formatDate(scanVisibility?.started_at, timeZone)} nowrap />
        <SummaryMetric label="Finished" value={formatDate(scanVisibility?.finished_at, timeZone)} nowrap />
      </SimpleGrid>
      {scanVisibility?.last_error && (
        <Alert mt="md" color="red" icon={<IconAlertCircle size={18} />}>
          {scanVisibility.last_error}
        </Alert>
      )}
    </Paper>
  );
}

function formatSpeedtestSpeed(displayValue, numericValue) {
  if (displayValue) return displayValue;
  if (numericValue === null || numericValue === undefined || numericValue === '') return '-';
  const value = Number(numericValue);
  return Number.isFinite(value) ? `${value.toFixed(value >= 100 ? 0 : 1)} Mbps` : '-';
}

function formatSpeedtestNumber(value, suffix) {
  if (value === null || value === undefined || value === '') return '-';
  const numberValue = Number(value);
  return Number.isFinite(numberValue) ? `${numberValue.toFixed(1)} ${suffix}` : '-';
}

function SpeedtestTrackerCard({ payload, timeZone }) {
  const result = payload?.data || null;
  const integration = payload?.integration || {};
  const available = Boolean(integration.available && result);
  const healthColor = !available ? 'gray' : result.healthy === false ? 'orange' : result.healthy === true ? 'teal' : 'blue';
  const healthLabel = !available ? 'Unavailable' : result.healthy === false ? 'Degraded' : result.healthy === true ? 'Healthy' : 'Available';
  const serviceUrl = result?.service_url || integration.service_url;
  const linkProps = serviceUrl
    ? { component: 'a', href: serviceUrl, target: '_blank', rel: 'noreferrer' }
    : {};

  return (
    <Paper
      className={`dashboard-summary-card speedtest-tracker-card ${serviceUrl ? 'dashboard-clickable-card' : ''}`}
      radius="md"
      {...linkProps}
    >
      <DashboardCardHeader
        icon={<IconGauge size={28} />}
        title="Speedtest"
        badge={(
          <Badge className="dashboard-status-badge" color={healthColor} variant="light">
            {healthLabel}
          </Badge>
        )}
      />
      {available ? (
        <>
          <SimpleGrid cols={2} spacing="sm">
            <SummaryMetric
              label="Download"
              value={formatSpeedtestSpeed(result.download_display, result.download_mbps)}
            />
            <SummaryMetric
              label="Upload"
              value={formatSpeedtestSpeed(result.upload_display, result.upload_mbps)}
              align="right"
            />
            <SummaryMetric label="Ping" value={formatSpeedtestNumber(result.ping_ms, 'ms')} />
            <SummaryMetric label="Packet loss" value={formatSpeedtestNumber(result.packet_loss_percent, '%')} align="right" />
          </SimpleGrid>
          <Text size="xs" c="dimmed" mt="md">
            Tested {formatDate(result.tested_at, timeZone)}
          </Text>
        </>
      ) : (
        <Text c="dimmed" size="sm">
          The latest result could not be loaded from Speedtest Tracker.
        </Text>
      )}
    </Paper>
  );
}

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
  const reason = attentionReasons.join(', ') || (!device.known ? 'Unknown device' : `${risk.label} risk`);
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
        <Tooltip label={attentionReasons.join('\n')} multiline withArrow disabled={!attentionReasons.length}>
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

function DashboardInsightCards({
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
    .filter((device) => device.needs_attention ?? (!device.known || ['high', 'medium'].includes(device.risk_level)))
    .sort((first, second) => {
      const riskWeight = { high: 0, medium: 1, low: 2 };
      const firstWeight = first.known ? riskWeight[first.risk_level] ?? 2 : -1;
      const secondWeight = second.known ? riskWeight[second.risk_level] ?? 2 : -1;
      return firstWeight - secondWeight || String(first.ip).localeCompare(String(second.ip), undefined, { numeric: true });
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
          {!attentionDevices.length && <DashboardEmptyState label="No devices need attention" />}
        </Stack>
      </Paper>
    </div>
  );
}

export function ScanDetailsContent({ scanStatus, scanVisibility, timeZone }) {
  const ranges = scanVisibility?.current_ranges?.length
    ? normalizedScanRanges(scanVisibility.current_ranges)
    : normalizedScanRanges([], scanVisibility?.current_range);
  const rangeLabels = scanVisibility?.current_range_labels || scanStatus?.scan_range_labels || {};
  const checks = [
    'Device discovery and online status checks',
    'Open port scanning for the configured TCP ports',
    'Hostname discovery using local network name protocols',
    'Metadata probing from device services when available',
    'Offline confirmation before a device is marked unavailable',
  ];

  return (
    <Stack gap="md">
      <SimpleGrid cols={{ base: 1, sm: 2 }}>
        <SummaryMetric label="Status" value={scanVisibility?.is_scanning ? 'Scanning' : scanStatus?.status || '-'} />
        <SummaryMetric label="Devices" value={scanStatus?.devices_seen ?? 0} />
        <SummaryMetric label="Duration" value={formatDuration(scanVisibility?.duration_seconds)} />
        <SummaryMetric
          label="Ranges"
          value={ranges.map((range) => formatScanRange(range, rangeLabels)).join(', ') || '-'}
        />
        <SummaryMetric label="Started" value={formatDate(scanVisibility?.started_at, timeZone)} nowrap />
        <SummaryMetric label="Finished" value={formatDate(scanVisibility?.finished_at, timeZone)} nowrap />
      </SimpleGrid>

      {scanVisibility?.last_error && (
        <Alert color="red" icon={<IconAlertCircle size={18} />}>
          {scanVisibility.last_error}
        </Alert>
      )}

      <Divider />

      <Stack gap={8}>
        <Text fw={700}>Deep scan checks</Text>
        {checks.map((check) => (
          <Group key={check} gap="sm" wrap="nowrap">
            <ThemeIconLike color="blue" size={28}>
              <IconShieldCheck size={16} />
            </ThemeIconLike>
            <Text c="dimmed">{check}</Text>
          </Group>
        ))}
      </Stack>

      <Text c="dimmed" size="sm">
        Longer scans are usually caused by devices that do not answer and force timeout-based checks.
      </Text>
    </Stack>
  );
}

export default function DashboardView({
  counters,
  appSettings,
  networkRanges,
  networkRangeLabels,
  scanStatus,
  scanVisibility,
  timeZone,
  onOpenScanDetails,
  speedtestTrackerPayload,
  events,
  devices,
  onSelectDevice,
  onOpenAttentionDevices,
  onOpenRecentChanges,
  onError,
}) {
  const speedtestEnabled = speedtestTrackerPayload?.integration?.enabled
    && speedtestTrackerPayload?.integration?.configured;

  return (
    <>
      <DashboardStatusCards counters={counters} />

      <div className={`dashboard-summary-grid ${speedtestEnabled ? 'with-speedtest' : ''}`}>
        <NetworkHealthCard counters={counters} />
        <AutomaticScanningCard
          appSettings={appSettings}
          networkRanges={networkRanges}
          networkRangeLabels={networkRangeLabels}
        />
        <LatestScanCard
          scanStatus={scanStatus}
          scanVisibility={scanVisibility}
          timeZone={timeZone}
          onOpenDetails={onOpenScanDetails}
        />
        {speedtestEnabled && (
          <SpeedtestTrackerCard payload={speedtestTrackerPayload} timeZone={timeZone} />
        )}
      </div>

      <DashboardInsightCards
        events={events}
        devices={devices}
        onSelectDevice={onSelectDevice}
        onOpenAttentionDevices={onOpenAttentionDevices}
        onOpenRecentChanges={onOpenRecentChanges}
        onError={onError}
        timeZone={timeZone}
      />
    </>
  );
}
