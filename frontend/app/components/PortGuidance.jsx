'use client';

import { useState } from 'react';
import {
  Badge,
  Box,
  Divider,
  Drawer,
  Group,
  Stack,
  Text,
  Tooltip,
} from '@mantine/core';
import { IconInfoCircle } from '@tabler/icons-react';

export default function PortSummary({ ports = [] }) {
  const visiblePorts = ports.slice(0, 2);
  const hiddenPortCount = Math.max(0, ports.length - visiblePorts.length);
  const hiddenPortLabel = ports
    .slice(visiblePorts.length)
    .map((port) => `${port.protocol || 'tcp'}/${port.port}`)
    .join(', ');

  if (!ports.length) {
    return (
      <Text size="sm" c="dimmed">
        -
      </Text>
    );
  }

  return (
    <div className="ports-list">
      {visiblePorts.map((port) => (
        <PortGuidanceBadge
          key={`${port.protocol}-${port.port}`}
          port={port}
          compact
        />
      ))}
      {hiddenPortCount > 0 && (
        <Tooltip label={hiddenPortLabel} multiline withArrow>
          <Badge className="port-badge port-overflow-badge" color="gray" variant="light">
            +{hiddenPortCount}
          </Badge>
        </Tooltip>
      )}
    </div>
  );
}
const portRecommendationColors = {
  expected: 'teal',
  review: 'yellow',
  usually_disable: 'red',
};

export function PortGuidanceBadge({ port, compact = false }) {
  const [opened, setOpened] = useState(false);
  const guidance = port?.guidance;
  const protocol = String(port?.protocol || 'tcp').toUpperCase();
  const label = compact
    ? port?.port
    : `${protocol}/${port?.port}${port?.service ? ` ${port.service}` : ''}`;

  if (!guidance) {
    return <Badge className="port-badge" variant="light">{label}</Badge>;
  }

  const recommendationColor = portRecommendationColors[guidance.recommendation] || 'gray';
  return (
    <>
      <button
        type="button"
        className="port-guidance-control port-guidance-trigger"
        aria-label={`Open guidance for ${protocol}/${port.port}`}
        aria-expanded={opened}
        onClick={(event) => {
          event.preventDefault();
          event.stopPropagation();
          setOpened(true);
        }}
      >
        <Badge
          className="port-badge port-guidance-badge"
          variant="light"
          rightSection={<IconInfoCircle size={12} stroke={2} />}
        >
          {label}
        </Badge>
      </button>
      <Drawer
        opened={opened}
        onClose={() => setOpened(false)}
        position="right"
        size={420}
        title="Open port guidance"
        classNames={{
          content: 'port-guidance-drawer port-guidance-control',
          overlay: 'port-guidance-control',
        }}
        closeButtonProps={{ 'aria-label': 'Close port guidance' }}
      >
        <Stack gap="sm">
          <Group justify="space-between" align="flex-start" wrap="nowrap">
            <Box>
              <Text fw={800}>{guidance.service_name}</Text>
              <Text size="xs" c="dimmed">{protocol}/{port.port}</Text>
            </Box>
            <Badge color={recommendationColor} variant="light">
              {guidance.recommendation_label}
            </Badge>
          </Group>

          <Box>
            <Text size="xs" c="dimmed" fw={700}>Common uses</Text>
            <Text size="sm">{guidance.common_uses}</Text>
          </Box>

          <Box>
            <Text size="xs" c="dimmed" fw={700}>Why this guidance</Text>
            <Text size="sm">{guidance.context}</Text>
          </Box>

          <Box>
            <Text size="xs" c="dimmed" fw={700}>Recommended next step</Text>
            <Text size="sm">{guidance.next_step}</Text>
          </Box>

          <Divider />
          <Group gap="xs" align="flex-start" wrap="nowrap">
            <IconInfoCircle size={16} stroke={1.8} className="port-guidance-info-icon" />
            <Box>
              <Text size="xs" fw={700}>{guidance.identification_label}</Text>
              {guidance.registry_service ? (
                <Text size="xs" c="dimmed">
                  Standard registry label: {guidance.registry_service}
                </Text>
              ) : null}
              <Text size="xs" c="dimmed" mt={4}>{guidance.scope_notice}</Text>
            </Box>
          </Group>
        </Stack>
      </Drawer>
    </>
  );
}
