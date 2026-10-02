'use client';

import {
  Group,
  Popover,
  ScrollArea,
  Stack,
  Text,
  Tooltip,
  UnstyledButton,
} from '@mantine/core';
import { IconChevronDown } from '@tabler/icons-react';

import { compactScanRangesLabel, formatScanRange } from '../utils/scan';

export default function ScanRangesSummary({ ranges, labels = {}, namesOnly = false }) {
  const fullLabel = ranges.map((range) => formatScanRange(range, labels)).join(', ') || '-';
  const displayRanges = namesOnly
    ? ranges.map((range) => String(labels?.[range] || range).trim())
    : ranges;
  const displayLabel = namesOnly
    ? displayRanges.length > 1
      ? `${displayRanges.length} networks`
      : displayRanges[0] || '-'
    : compactScanRangesLabel(ranges, labels);

  if (namesOnly && ranges.length > 1) {
    return (
      <Popover position="bottom-end" width={360} shadow="md" withinPortal>
        <Popover.Target>
          <UnstyledButton aria-label={`Show ${ranges.length} configured networks`}>
            <span className="scan-ranges-summary">
              <span>{displayLabel}</span>
              <IconChevronDown size={17} aria-hidden="true" />
            </span>
          </UnstyledButton>
        </Popover.Target>
        <Popover.Dropdown p={0}>
          <ScrollArea.Autosize mah={260} type="auto">
            <Stack gap={0} py={6}>
              {ranges.map((range) => (
                <Group key={range} gap="md" wrap="nowrap" px="md" py="sm">
                  <Text fw={700} truncate style={{ flex: 1, minWidth: 0 }}>
                    {String(labels?.[range] || range).trim()}
                  </Text>
                  <Text size="sm" c="dimmed" ff="monospace" style={{ flexShrink: 0 }}>
                    {range}
                  </Text>
                </Group>
              ))}
            </Stack>
          </ScrollArea.Autosize>
        </Popover.Dropdown>
      </Popover>
    );
  }

  return (
    <Tooltip label={fullLabel} disabled={!namesOnly && ranges.length < 2} multiline withArrow>
      <Text span inherit truncate style={{ display: 'block', maxWidth: '100%' }}>
        {displayLabel}
      </Text>
    </Tooltip>
  );
}
