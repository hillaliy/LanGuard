import { Alert, Divider, Group, SimpleGrid, Stack, Text } from '@mantine/core';
import { IconAlertCircle, IconShieldCheck } from '@tabler/icons-react';

import SummaryMetric from '../components/SummaryMetric';
import { formatDate, formatDuration } from '../utils/date';
import { formatScanRange, normalizedScanRanges } from '../utils/scan';
import { ThemeIconLike } from './DashboardCardElements';

export default function ScanDetailsContent({ scanStatus, scanVisibility, timeZone }) {
  const ranges = scanVisibility?.current_ranges?.length
    ? normalizedScanRanges(scanVisibility.current_ranges)
    : normalizedScanRanges([], scanVisibility?.current_range);
  const rangeLabels = scanVisibility?.current_range_labels
    || scanStatus?.scan_range_labels
    || {};
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
        <SummaryMetric
          label="Status"
          value={scanVisibility?.is_scanning ? 'Scanning' : scanStatus?.status || '-'}
        />
        <SummaryMetric label="Devices" value={scanStatus?.devices_seen ?? 0} />
        <SummaryMetric
          label="Duration"
          value={formatDuration(scanVisibility?.duration_seconds)}
        />
        <SummaryMetric
          label="Ranges"
          value={ranges.map((range) => formatScanRange(range, rangeLabels)).join(', ') || '-'}
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
