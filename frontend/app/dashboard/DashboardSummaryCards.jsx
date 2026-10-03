import { Alert, Badge, Paper, SimpleGrid, Stack, Text } from '@mantine/core';
import { IconAlertCircle, IconClock, IconGauge, IconLine } from '@tabler/icons-react';

import ScanRangesSummary from '../components/ScanRangesSummary';
import SummaryMetric from '../components/SummaryMetric';
import { formatDate, formatDuration } from '../utils/date';
import { normalizedScanRanges } from '../utils/scan';
import { DashboardCardHeader, SummaryRow, ThemeIconLike } from './DashboardCardElements';

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
        <SummaryMetric
          label="Interval"
          value={appSettings?.scan_interval ? `${appSettings.scan_interval} min` : '-'}
        />
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
        <SummaryMetric
          label="Duration"
          value={formatDuration(scanVisibility?.duration_seconds)}
        />
        <SummaryMetric
          label="Started"
          value={formatDate(scanVisibility?.started_at, timeZone)}
          nowrap
        />
        <SummaryMetric
          label="Finished"
          value={formatDate(scanVisibility?.finished_at, timeZone)}
          nowrap
        />
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
  const healthColor = !available
    ? 'gray'
    : result.healthy === false
      ? 'orange'
      : result.healthy === true
        ? 'teal'
        : 'blue';
  const healthLabel = !available
    ? 'Unavailable'
    : result.healthy === false
      ? 'Degraded'
      : result.healthy === true
        ? 'Healthy'
        : 'Available';
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
            <SummaryMetric
              label="Packet loss"
              value={formatSpeedtestNumber(result.packet_loss_percent, '%')}
              align="right"
            />
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

export default function DashboardSummaryCards({
  appSettings,
  counters,
  networkRangeLabels,
  networkRanges,
  onOpenScanDetails,
  scanStatus,
  scanVisibility,
  speedtestTrackerPayload,
  timeZone,
}) {
  const speedtestEnabled = speedtestTrackerPayload?.integration?.enabled
    && speedtestTrackerPayload?.integration?.configured;

  return (
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
  );
}
