'use client';

import {
  Alert,
  Badge,
  Box,
  Button,
  Code,
  CopyButton,
  Divider,
  Group,
  Modal,
  SimpleGrid,
  Stack,
  Text,
} from '@mantine/core';
import { IconAlertCircle, IconCheck, IconCopy } from '@tabler/icons-react';

import { formatDate, formatDuration } from '../utils/date';
import { formatScanRange, normalizedScanRanges } from '../utils/scan';

const FAILURE_STAGE_LABELS = {
  arp_discovery: 'ARP discovery',
  metadata_discovery: 'Metadata discovery',
  device_sync: 'Device synchronization',
  status_reconciliation: 'Status reconciliation',
  finalization: 'Finalization',
  heartbeat: 'Heartbeat',
};

const FAILURE_CODE_LABELS = {
  database_locked: 'Database locked',
  database_integrity: 'Database integrity error',
  database_error: 'Database error',
  permission_denied: 'Permission denied',
  timeout: 'Timeout',
  external_request: 'External request failed',
  scan_lock_lost: 'Scan lock lost',
  stale_scan_lock: 'Stale scan lock',
  superseded_scan: 'Superseded scan',
  network_io: 'Network I/O error',
  unexpected_error: 'Unexpected error',
};

function readableValue(value, labels) {
  if (!value) return 'Not recorded';
  if (labels[value]) return labels[value];
  return String(value)
    .replaceAll('_', ' ')
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

function ScanDetailField({ label, children }) {
  return (
    <Box>
      <Text size="xs" c="dimmed">{label}</Text>
      <Text fw={600}>{children}</Text>
    </Box>
  );
}

export default function ScanFailureDetailsModal({ opened, onClose, scanRun, timeZone }) {
  if (!scanRun) return null;

  const ranges = normalizedScanRanges(scanRun.scan_ranges, scanRun.ip_range);
  const durationSeconds = scanRun.started_at && scanRun.finished_at
    ? Math.max(
      0,
      Math.round((new Date(scanRun.finished_at) - new Date(scanRun.started_at)) / 1000)
    )
    : null;
  const hasStructuredDetails = Boolean(
    scanRun.failure_code
    || scanRun.failure_type
    || scanRun.failure_stage
    || scanRun.failure_fingerprint
  );

  return (
    <Modal
      opened={opened}
      onClose={onClose}
      title="Scan failure details"
      centered
      size="lg"
      returnFocus
    >
      <Stack gap="lg">
        <Alert color="red" icon={<IconAlertCircle size={18} />} title="Failure summary">
          {scanRun.error || 'The network scan could not be completed.'}
        </Alert>

        {hasStructuredDetails ? (
          <>
            <SimpleGrid cols={{ base: 1, sm: 2 }}>
              <ScanDetailField label="Failure stage">
                {readableValue(scanRun.failure_stage, FAILURE_STAGE_LABELS)}
              </ScanDetailField>
              <ScanDetailField label="Failure code">
                {readableValue(scanRun.failure_code, FAILURE_CODE_LABELS)}
                {scanRun.failure_code && (
                  <Text span size="xs" c="dimmed"> {`(${scanRun.failure_code})`}</Text>
                )}
              </ScanDetailField>
              <ScanDetailField label="Exception type">
                {scanRun.failure_type || 'Not recorded'}
              </ScanDetailField>
              <ScanDetailField label="Scan source">
                {readableValue(scanRun.source, {})}
              </ScanDetailField>
            </SimpleGrid>

            <Box>
              <Text size="xs" c="dimmed" mb={4}>Failure fingerprint</Text>
              {scanRun.failure_fingerprint ? (
                <Group gap="xs" align="center">
                  <Code>{scanRun.failure_fingerprint}</Code>
                  <CopyButton value={scanRun.failure_fingerprint} timeout={2000}>
                    {({ copied, copy }) => (
                      <Button
                        size="compact-sm"
                        variant="default"
                        leftSection={copied ? <IconCheck size={15} /> : <IconCopy size={15} />}
                        onClick={copy}
                      >
                        {copied ? 'Copied' : 'Copy'}
                      </Button>
                    )}
                  </CopyButton>
                </Group>
              ) : (
                <Text fw={600}>Not recorded</Text>
              )}
            </Box>
          </>
        ) : (
          <Alert color="blue" icon={<IconAlertCircle size={18} />}>
            Detailed failure diagnostics were not recorded for this older scan run.
            The summary above is the only stored diagnostic information.
          </Alert>
        )}

        <Divider label="Scan details" labelPosition="left" />

        <SimpleGrid cols={{ base: 1, sm: 2 }}>
          {!hasStructuredDetails && (
            <ScanDetailField label="Scan source">
              {readableValue(scanRun.source, {})}
            </ScanDetailField>
          )}
          <ScanDetailField label="Started">
            {formatDate(scanRun.started_at, timeZone)}
          </ScanDetailField>
          <ScanDetailField label="Finished">
            {formatDate(scanRun.finished_at, timeZone)}
          </ScanDetailField>
          <ScanDetailField label="Duration">
            {durationSeconds === null ? '-' : formatDuration(durationSeconds)}
          </ScanDetailField>
          <ScanDetailField label="Devices seen">
            {Number(scanRun.devices_seen) || 0}
          </ScanDetailField>
          <ScanDetailField label="Port changes">
            {Number(scanRun.ports_opened) || 0} opened / {Number(scanRun.ports_closed) || 0} closed
          </ScanDetailField>
        </SimpleGrid>

        <Box>
          <Text size="xs" c="dimmed" mb={4}>Network ranges</Text>
          <Stack gap={2}>
            {ranges.length ? ranges.map((range) => (
              <Text key={range} fw={600}>{formatScanRange(range, scanRun.scan_range_labels)}</Text>
            )) : <Text fw={600}>Not recorded</Text>}
          </Stack>
        </Box>

        <Group justify="flex-end">
          <Button variant="default" onClick={onClose}>Close</Button>
        </Group>
      </Stack>
    </Modal>
  );
}
