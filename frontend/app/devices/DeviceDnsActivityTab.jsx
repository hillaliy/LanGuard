import {
  Alert, Badge, Box, Button, Group, LoadingOverlay, ScrollArea, SegmentedControl,
  Select, SimpleGrid, Stack, Table, Tabs, Text, TextInput, Title, Tooltip,
} from '@mantine/core';
import { IconAlertCircle, IconSearch, IconWorldSearch } from '@tabler/icons-react';

import { hasNextActivityPage } from '../utils/activity';
import { formatDate } from '../utils/date';
import { DeviceField } from './DeviceDetailFields';

export default function DeviceDnsActivityTab({
  dnsActivity,
  dnsFilter,
  dnsIntegration,
  dnsOrdering,
  dnsPagination,
  dnsSearch,
  dnsSummary,
  loadMoreDnsActivity,
  loadingDnsActivity,
  loadingMoreDnsActivity,
  setDnsFilter,
  setDnsOrdering,
  setDnsSearch,
  timeZone,
}) {
  return (
    <Tabs.Panel value="dns" pt="lg">
      <Stack gap="md">
        <Group justify="space-between" align="flex-start" wrap="wrap">
          <Box>
            <Title order={4}>DNS activity</Title>
            <Text size="sm" c="dimmed">
              Aggregated {dnsIntegration?.provider_name || 'DNS provider'} destinations for this device.
            </Text>
          </Box>
          {dnsIntegration?.last_sync_at && (
            <Text size="sm" c="dimmed">
              Last synced {formatDate(dnsIntegration.last_sync_at, timeZone)}
            </Text>
          )}
        </Group>

        {dnsIntegration && !dnsIntegration.configured && (
          <Alert color="blue" icon={<IconWorldSearch size={18} />}>
            Configure a DNS provider in Settings to collect DNS activity.
          </Alert>
        )}
        {dnsIntegration?.configured && !dnsIntegration.enabled && (
          <Alert color="gray">DNS activity synchronization is currently disabled.</Alert>
        )}
        {dnsIntegration?.last_error && (
          <Alert color="red" icon={<IconAlertCircle size={18} />}>
            Last sync failed: {dnsIntegration.last_error}
          </Alert>
        )}

        <SimpleGrid cols={{ base: 1, sm: 3 }}>
          <DeviceField
            label="Unique domains"
            value={Number(dnsSummary?.unique_domains || 0).toLocaleString()}
          />
          <DeviceField
            label="DNS queries"
            value={Number(dnsSummary?.total_queries || 0).toLocaleString()}
          />
          <DeviceField
            label="Blocked queries"
            value={Number(dnsSummary?.blocked_queries || 0).toLocaleString()}
          />
        </SimpleGrid>

        <Group align="flex-end" wrap="wrap">
          <TextInput
            label="Search domains"
            placeholder="api.example.com"
            value={dnsSearch}
            onChange={(event) => setDnsSearch(event.currentTarget.value)}
            leftSection={<IconSearch size={16} />}
            style={{ flex: '1 1 260px' }}
          />
          <SegmentedControl
            value={dnsFilter}
            onChange={setDnsFilter}
            data={[
              { value: 'all', label: 'All' },
              { value: 'allowed', label: 'Allowed' },
              { value: 'blocked', label: 'Blocked' },
            ]}
          />
          <Select
            label="Sort by"
            value={dnsOrdering}
            onChange={(value) => setDnsOrdering(value || '-last_seen')}
            data={[
              { value: '-last_seen', label: 'Recently seen' },
              { value: '-query_count', label: 'Most queries' },
              { value: '-blocked_count', label: 'Most blocked' },
              { value: 'domain', label: 'Domain name' },
            ]}
            w={180}
          />
        </Group>

        <Box pos="relative">
          <LoadingOverlay visible={loadingDnsActivity} />
          <ScrollArea.Autosize mah={520} type="auto" className="activity-table-scroll">
            <Table striped highlightOnHover verticalSpacing="sm">
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>Domain</Table.Th>
                  <Table.Th>Type</Table.Th>
                  <Table.Th>Queries</Table.Th>
                  <Table.Th>Blocked</Table.Th>
                  <Table.Th>Last seen</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {dnsActivity.map((activity) => (
                  <Table.Tr key={activity.id}>
                    <Table.Td>
                      <Text size="sm" fw={600} className="wrap-text">
                        {activity.domain}
                      </Text>
                      {activity.last_service_name && (
                        <Text size="xs" c="dimmed">{activity.last_service_name}</Text>
                      )}
                    </Table.Td>
                    <Table.Td>{activity.query_type || '-'}</Table.Td>
                    <Table.Td>{Number(activity.query_count || 0).toLocaleString()}</Table.Td>
                    <Table.Td>
                      {activity.blocked_count > 0 ? (
                        <Tooltip
                          label={activity.last_reason
                            || `Blocked by ${dnsIntegration?.provider_name || 'DNS provider'}`}
                        >
                          <Badge color="red" variant="light">
                            {Number(activity.blocked_count).toLocaleString()}
                          </Badge>
                        </Tooltip>
                      ) : (
                        <Text size="sm" c="dimmed">0</Text>
                      )}
                    </Table.Td>
                    <Table.Td className="device-history-time">
                      {formatDate(activity.last_seen, timeZone)}
                    </Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </ScrollArea.Autosize>
        </Box>
        {!loadingDnsActivity && !dnsActivity.length && (
          <Text c="dimmed">No DNS activity recorded for this device.</Text>
        )}
        {hasNextActivityPage(dnsPagination) && (
          <Group justify="center">
            <Button
              variant="default"
              onClick={loadMoreDnsActivity}
              loading={loadingMoreDnsActivity}
            >
              Load more domains
            </Button>
          </Group>
        )}
      </Stack>
    </Tabs.Panel>
  );
}
