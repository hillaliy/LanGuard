import {
  Badge, Button, Group, ScrollArea, Stack, Table, Text, Title,
} from '@mantine/core';
import { IconUnlink } from '@tabler/icons-react';

import { PortGuidanceBadge } from '../components/PortGuidance';
import { formatDate } from '../utils/date';

function statusColor(status) {
  if (status === 'online') return 'green';
  if (status === 'recently_seen' || status === 'sleeping') return 'yellow';
  return 'red';
}

export default function DeviceInterfacesSection({
  canEditDevices,
  device,
  onSeparate,
  timeZone,
}) {
  const interfaces = device.interfaces || [];

  return (
    <section className="device-detail-section device-interfaces-section">
      <Group justify="space-between" align="flex-start" gap="md">
        <Stack gap={2}>
          <Title order={4}>Network interfaces</Title>
          <Text size="sm" c="dimmed">
            Each MAC address keeps its own IP, status, ports, and observation history.
          </Text>
        </Stack>
        <Badge variant="light">
          {interfaces.length} interface{interfaces.length === 1 ? '' : 's'}
        </Badge>
      </Group>
      <ScrollArea mt="md" type="auto">
        <Table className="device-interfaces-table" verticalSpacing="sm">
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Interface</Table.Th>
              <Table.Th>Address</Table.Th>
              <Table.Th>Status</Table.Th>
              <Table.Th>Open ports</Table.Th>
              <Table.Th>Last seen</Table.Th>
              {canEditDevices && <Table.Th aria-label="Interface actions" />}
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {interfaces.map((networkInterface) => (
              <Table.Tr key={networkInterface.id}>
                <Table.Td>
                  <Stack gap={2}>
                    <Group gap="xs" wrap="nowrap">
                      <Text fw={600} className="device-interface-mac">
                        {networkInterface.mac}
                      </Text>
                      {networkInterface.primary && (
                        <Badge size="xs" variant="light">Primary</Badge>
                      )}
                    </Group>
                    <Text size="xs" c="dimmed" className="device-interface-hostname">
                      {networkInterface.hostname || networkInterface.vendor || '-'}
                    </Text>
                  </Stack>
                </Table.Td>
                <Table.Td>{networkInterface.ip}</Table.Td>
                <Table.Td>
                  <Stack gap={2} align="flex-start">
                    <Badge
                      color={statusColor(networkInterface.status)}
                      variant="light"
                    >
                      {networkInterface.status_display}
                    </Badge>
                    <Text size="xs" c="dimmed">
                      {networkInterface.status_source_display || '-'}
                    </Text>
                  </Stack>
                </Table.Td>
                <Table.Td>
                  <Group gap={5} wrap="nowrap" className="device-interface-ports">
                    {(networkInterface.open_ports || []).length ? (
                      networkInterface.open_ports.map((port) => (
                        <PortGuidanceBadge
                          key={`${port.protocol}-${port.port}`}
                          port={port}
                        />
                      ))
                    ) : <Text size="sm">-</Text>}
                  </Group>
                </Table.Td>
                <Table.Td className="device-interface-last-seen">
                  {formatDate(networkInterface.lastseen, timeZone)}
                </Table.Td>
                {canEditDevices && (
                  <Table.Td>
                    {!networkInterface.primary && (
                      <Button
                        size="compact-sm"
                        variant="subtle"
                        color="red"
                        leftSection={<IconUnlink size={16} />}
                        onClick={() => onSeparate(networkInterface)}
                      >
                        Separate
                      </Button>
                    )}
                  </Table.Td>
                )}
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      </ScrollArea>
    </section>
  );
}
