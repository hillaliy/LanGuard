'use client';

import { useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Badge,
  Box,
  Button,
  Group,
  Modal,
  Select,
  SimpleGrid,
  Stack,
  Table,
  Text,
  Title,
} from '@mantine/core';
import { useDisclosure } from '@mantine/hooks';
import { IconAlertCircle, IconArrowsSort, IconHistory } from '@tabler/icons-react';

import ActivityTablePanel from '../components/ActivityTablePanel';
import PageIcon from '../components/PageIcon';
import ScanRangesSummary from '../components/ScanRangesSummary';
import { activityRecordLabel, hasNextActivityPage } from '../utils/activity';
import { formatDate, formatDuration } from '../utils/date';
import { compactScanRangesLabel, normalizedScanRanges } from '../utils/scan';

function scanRunDurationSeconds(run) {
  if (!run?.started_at || !run?.finished_at) return 0;
  return Math.max(0, Math.round((new Date(run.finished_at) - new Date(run.started_at)) / 1000));
}

function ScanComparisonModal({ opened, onClose, scanRuns, timeZone }) {
  const comparableRuns = useMemo(
    () => scanRuns.filter((run) => run.status !== 'running' && run.finished_at),
    [scanRuns]
  );
  const [currentId, setCurrentId] = useState(null);
  const [baselineId, setBaselineId] = useState(null);

  useEffect(() => {
    const availableIds = new Set(comparableRuns.map((run) => String(run.id)));
    if (!currentId || !availableIds.has(currentId)) {
      setCurrentId(comparableRuns[0] ? String(comparableRuns[0].id) : null);
    }
    if (!baselineId || !availableIds.has(baselineId) || baselineId === currentId) {
      setBaselineId(comparableRuns[1] ? String(comparableRuns[1].id) : null);
    }
  }, [baselineId, comparableRuns, currentId]);

  const currentRun = comparableRuns.find((run) => String(run.id) === currentId);
  const baselineRun = comparableRuns.find((run) => String(run.id) === baselineId);
  const options = comparableRuns.map((run) => ({
    value: String(run.id),
    label: `${formatDate(run.started_at, timeZone)} · ${compactScanRangesLabel(normalizedScanRanges(run.scan_ranges, run.ip_range), run.scan_range_labels)}`,
  }));
  const metrics = [
    { label: 'Devices seen', current: currentRun?.devices_seen, baseline: baselineRun?.devices_seen },
    { label: 'Online devices', current: currentRun?.online_devices, baseline: baselineRun?.online_devices },
    { label: 'New devices', current: currentRun?.new_devices, baseline: baselineRun?.new_devices },
    { label: 'Ports opened', current: currentRun?.ports_opened, baseline: baselineRun?.ports_opened },
    { label: 'Ports closed', current: currentRun?.ports_closed, baseline: baselineRun?.ports_closed },
    {
      label: 'Duration',
      current: scanRunDurationSeconds(currentRun),
      baseline: scanRunDurationSeconds(baselineRun),
      duration: true,
    },
  ];

  return (
    <Modal opened={opened} onClose={onClose} title="Compare scans" centered size="lg">
      <Stack gap="lg">
        <SimpleGrid cols={{ base: 1, sm: 2 }}>
          <Select
            label="Current scan"
            data={options}
            value={currentId}
            onChange={setCurrentId}
            allowDeselect={false}
            searchable
          />
          <Select
            label="Baseline scan"
            data={options}
            value={baselineId}
            onChange={setBaselineId}
            allowDeselect={false}
            searchable
          />
        </SimpleGrid>

        {currentRun && baselineRun && currentRun.id !== baselineRun.id ? (
          <>
            <Group justify="space-between" gap="md">
              <Group gap="xs">
                <Text c="dimmed" size="sm">Current</Text>
                <Badge color={currentRun.status === 'success' ? 'teal' : 'red'} variant="light">
                  {currentRun.status}
                </Badge>
              </Group>
              <Group gap="xs">
                <Text c="dimmed" size="sm">Baseline</Text>
                <Badge color={baselineRun.status === 'success' ? 'teal' : 'red'} variant="light">
                  {baselineRun.status}
                </Badge>
              </Group>
            </Group>
            <Table.ScrollContainer minWidth={520}>
              <Table verticalSpacing="sm">
                <Table.Thead>
                  <Table.Tr>
                    <Table.Th>Metric</Table.Th>
                    <Table.Th>Baseline</Table.Th>
                    <Table.Th>Current</Table.Th>
                    <Table.Th>Change</Table.Th>
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {metrics.map((metric) => {
                    const current = Number(metric.current) || 0;
                    const baseline = Number(metric.baseline) || 0;
                    const delta = current - baseline;
                    const displayValue = (value) => metric.duration ? formatDuration(value) : value;
                    const deltaLabel = metric.duration
                      ? `${delta > 0 ? '+' : delta < 0 ? '-' : ''}${formatDuration(Math.abs(delta))}`
                      : `${delta > 0 ? '+' : ''}${delta}`;
                    return (
                      <Table.Tr key={metric.label}>
                        <Table.Td><Text fw={700}>{metric.label}</Text></Table.Td>
                        <Table.Td>{displayValue(baseline)}</Table.Td>
                        <Table.Td>{displayValue(current)}</Table.Td>
                        <Table.Td>
                          <Badge color={delta === 0 ? 'gray' : 'blue'} variant="light">
                            {deltaLabel}
                          </Badge>
                        </Table.Td>
                      </Table.Tr>
                    );
                  })}
                </Table.Tbody>
              </Table>
            </Table.ScrollContainer>
            <Text c="dimmed" size="sm">
              Comparison uses the totals recorded for each scan. Historical per-device snapshots were not stored.
            </Text>
          </>
        ) : (
          <Alert color="blue" icon={<IconAlertCircle size={18} />}>
            Select two different completed scans to compare them.
          </Alert>
        )}
      </Stack>
    </Modal>
  );
}

export default function ScanHistoryView({
  scanRuns,
  timeZone,
  pagination,
  loadingMore,
  onLoadMore,
}) {
  const [comparisonOpened, comparison] = useDisclosure(false);
  const comparableRunCount = scanRuns.filter(
    (run) => run.status !== 'running' && run.finished_at
  ).length;

  return (
    <>
      <Stack gap="lg">
        <Group justify="space-between" align="flex-end">
          <Group gap="sm">
            <PageIcon>
              <IconHistory size={26} />
            </PageIcon>
            <Box>
              <Title order={2}>Scan history</Title>
              <Text c="dimmed">Recent scan runs and detected changes</Text>
            </Box>
          </Group>
          <Group gap="sm">
            <Button
              variant="light"
              leftSection={<IconArrowsSort size={18} />}
              onClick={comparison.open}
              disabled={comparableRunCount < 2}
            >
              Compare scans
            </Button>
            <Badge variant="light">{activityRecordLabel(pagination, scanRuns.length)}</Badge>
          </Group>
        </Group>

        <ActivityTablePanel
          hasMore={hasNextActivityPage(pagination)}
          loadingMore={loadingMore}
          onLoadMore={onLoadMore}
        >
          <Table verticalSpacing="sm">
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Status</Table.Th>
                <Table.Th>Ranges</Table.Th>
                <Table.Th>Started</Table.Th>
                <Table.Th>Seen</Table.Th>
                <Table.Th>Port changes</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {scanRuns.map((run) => (
                <Table.Tr key={run.id}>
                  <Table.Td>
                    <Badge color={run.status === 'success' ? 'teal' : run.status === 'failed' ? 'red' : 'blue'} variant="light">
                      {run.status}
                    </Badge>
                  </Table.Td>
                  <Table.Td>
                    <ScanRangesSummary
                      ranges={normalizedScanRanges(run.scan_ranges, run.ip_range)}
                      labels={run.scan_range_labels}
                    />
                  </Table.Td>
                  <Table.Td>{formatDate(run.started_at, timeZone)}</Table.Td>
                  <Table.Td>{run.devices_seen}</Table.Td>
                  <Table.Td>{run.ports_opened} / {run.ports_closed}</Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </ActivityTablePanel>
      </Stack>
      <ScanComparisonModal
        opened={comparisonOpened}
        onClose={comparison.close}
        scanRuns={scanRuns}
        timeZone={timeZone}
      />
    </>
  );
}
