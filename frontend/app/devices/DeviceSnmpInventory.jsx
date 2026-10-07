import { Badge, Box, Group, SimpleGrid, Stack, Table, Text, Title } from '@mantine/core';

import { formatDate } from '../utils/date';
import { formatRoleLabel } from '../utils/device';
import { DeviceField } from './DeviceDetailFields';

function statusColor(status) {
  if (status === 'up') return 'teal';
  if (status === 'down') return 'red';
  return 'gray';
}

export default function DeviceSnmpInventory({ device, timeZone }) {
  const inventory = device?.snmp_data || {};
  const system = inventory.system || {};
  const interfaces = Array.isArray(inventory.interfaces) ? inventory.interfaces : [];
  const neighbors = Array.isArray(inventory.neighbors) ? inventory.neighbors : [];
  if (!Object.keys(inventory).length) return null;

  return (
    <section className="device-detail-section device-snmp-section">
      <Group justify="space-between" align="center" gap="sm">
        <Title order={4}>SNMP inventory</Title>
        <Badge color="blue" variant="light">
          {formatRoleLabel(inventory.device_type || 'managed device')}
        </Badge>
      </Group>

      <SimpleGrid cols={{ base: 1, sm: 2, lg: 4 }} mt="md">
        <DeviceField label="System name" value={system.name || '-'} />
        <DeviceField label="Vendor" value={inventory.vendor || '-'} />
        <DeviceField label="Location" value={system.location || '-'} />
        <DeviceField label="Last queried" value={formatDate(device.snmp_last_seen, timeZone)} />
      </SimpleGrid>
      {system.description && (
        <Box mt="md">
          <Text size="xs" c="dimmed">System description</Text>
          <Text size="sm" className="wrap-text">{system.description}</Text>
        </Box>
      )}

      <Stack gap="xs" mt="lg">
        <Text fw={700} size="sm">Interfaces</Text>
        {interfaces.length ? (
          <Table.ScrollContainer minWidth={720}>
            <Table verticalSpacing="xs" highlightOnHover>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>Interface</Table.Th>
                  <Table.Th>Type</Table.Th>
                  <Table.Th>Speed</Table.Th>
                  <Table.Th>Status</Table.Th>
                  <Table.Th>MAC</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {interfaces.map((item) => (
                  <Table.Tr key={item.index}>
                    <Table.Td>
                      <Text size="sm" fw={600} lineClamp={1}>{item.name || '-'}</Text>
                      {item.description && item.description !== item.name && (
                        <Text size="xs" c="dimmed" lineClamp={1}>{item.description}</Text>
                      )}
                    </Table.Td>
                    <Table.Td>{item.type || '-'}</Table.Td>
                    <Table.Td>{item.speed_mbps ? `${item.speed_mbps} Mbps` : '-'}</Table.Td>
                    <Table.Td>
                      <Badge color={statusColor(item.oper_status)} variant="light">
                        {item.oper_status || 'unknown'}
                      </Badge>
                    </Table.Td>
                    <Table.Td>{item.mac || '-'}</Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </Table.ScrollContainer>
        ) : (
          <Text size="sm" c="dimmed">No interface table was reported.</Text>
        )}
      </Stack>

      {neighbors.length > 0 && (
        <Stack gap="xs" mt="lg">
          <Text fw={700} size="sm">LLDP neighbors</Text>
          <Text size="xs" c="dimmed">
            Neighbor records are topology hints reported by this device, not verified links.
          </Text>
          <Table.ScrollContainer minWidth={640}>
            <Table verticalSpacing="xs" highlightOnHover>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>Local interface</Table.Th>
                  <Table.Th>Neighbor</Table.Th>
                  <Table.Th>Remote port</Table.Th>
                  <Table.Th>Chassis ID</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {neighbors.map((neighbor, index) => (
                  <Table.Tr key={`${neighbor.local_port}-${neighbor.chassis_id}-${index}`}>
                    <Table.Td>{neighbor.local_port || '-'}</Table.Td>
                    <Table.Td>{neighbor.system_name || neighbor.system_description || '-'}</Table.Td>
                    <Table.Td>{neighbor.port_id || '-'}</Table.Td>
                    <Table.Td>{neighbor.chassis_id || '-'}</Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </Table.ScrollContainer>
        </Stack>
      )}
    </section>
  );
}
