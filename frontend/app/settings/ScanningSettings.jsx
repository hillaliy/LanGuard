import { ActionIcon, Box, Button, Group, NumberInput, Select, SimpleGrid, Stack, Table, Tabs, Text, TextInput, Title, Tooltip } from '@mantine/core';
import { IconPlus, IconTrash } from '@tabler/icons-react';

export default function ScanningSettings({ controller }) {
  const {
    addScanNetwork,
    removeScanNetwork,
    scanInterval,
    scanMaxHosts,
    scanNetworks,
    setScanInterval,
    setTimeZone,
    timeZone,
    timeZoneOptions,
    updateScanNetwork,
  } = controller;

  return (
<Tabs.Panel value="scanning" className="settings-category-panel">
        <Stack gap="lg">
          <Box>
            <Title order={3}>Network scanning</Title>
            <Text c="dimmed">Configure network ranges and scheduled scan timing.</Text>
          </Box>
        <Stack gap="sm">
          <Group justify="space-between">
            <Text fw={700}>Network ranges</Text>
            <Button
              size="xs"
              variant="light"
              leftSection={<IconPlus size={16} />}
              onClick={addScanNetwork}
              disabled={scanNetworks.length >= 16}
            >
              Add network
            </Button>
          </Group>
          <Table.ScrollContainer minWidth={560}>
            <Table withTableBorder verticalSpacing="xs">
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>Network name</Table.Th>
                  <Table.Th>CIDR range</Table.Th>
                  <Table.Th w={48} />
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {scanNetworks.map((network, index) => (
                  <Table.Tr key={index}>
                    <Table.Td>
                      <TextInput
                        value={network.name}
                        onChange={(event) =>
                          updateScanNetwork(index, 'name', event.currentTarget.value)
                        }
                        placeholder={index === 0 ? 'Primary network' : `Network ${index + 1}`}
                        aria-label={`Name for network ${index + 1}`}
                        maxLength={64}
                        required
                      />
                    </Table.Td>
                    <Table.Td>
                      <TextInput
                        value={network.cidr}
                        onChange={(event) =>
                          updateScanNetwork(index, 'cidr', event.currentTarget.value)
                        }
                        placeholder="192.168.1.0/24"
                        aria-label={`CIDR for network ${index + 1}`}
                        required
                      />
                    </Table.Td>
                    <Table.Td>
                      <Tooltip label="Remove network">
                        <ActionIcon
                          color="red"
                          variant="subtle"
                          onClick={() => removeScanNetwork(index)}
                          disabled={scanNetworks.length === 1}
                          aria-label={`Remove network ${index + 1}`}
                        >
                          <IconTrash size={17} />
                        </ActionIcon>
                      </Tooltip>
                    </Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </Table.ScrollContainer>
        </Stack>
        <SimpleGrid cols={{ base: 1, sm: 2 }}>
          <NumberInput
            label="Scan interval"
            value={scanInterval}
            onChange={(value) => setScanInterval(Number(value) || 10)}
            min={1}
            max={1440}
            suffix=" min"
            required
          />
          <Select
            label="Time zone"
            data={timeZoneOptions}
            value={timeZone}
            onChange={(value) => setTimeZone(value || 'UTC')}
            placeholder="Asia/Jerusalem"
            searchable
            maxDropdownHeight={260}
            required
          />
        </SimpleGrid>

        <Text size="xs" c="dimmed">
          Each range can contain up to {scanMaxHosts.toLocaleString()} addresses. The interval starts after each scan completes. Network range and interval changes apply automatically on the next scheduler cycle.
        </Text>
        </Stack>
          </Tabs.Panel>
  );
}
