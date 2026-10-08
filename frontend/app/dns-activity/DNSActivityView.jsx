'use client';

import { useEffect, useState } from 'react';
import {
  Alert,
  Badge,
  Box,
  Button,
  Divider,
  Group,
  LoadingOverlay,
  SegmentedControl,
  Select,
  SimpleGrid,
  Stack,
  Table,
  Text,
  TextInput,
  Title,
  UnstyledButton,
} from '@mantine/core';
import {
  IconAlertCircle,
  IconArrowUpRight,
  IconSearch,
  IconWorldSearch,
} from '@tabler/icons-react';

import { apiRequest } from '../api';
import ActivityTablePanel from '../components/ActivityTablePanel';
import PageIcon from '../components/PageIcon';
import { appendUniqueById, hasNextActivityPage } from '../utils/activity';
import { formatDate } from '../utils/date';

export default function DNSActivityView({ timeZone, onSelectDevice, onError }) {
  const [activity, setActivity] = useState([]);
  const [activityPagination, setActivityPagination] = useState(null);
  const [summary, setSummary] = useState(null);
  const [integration, setIntegration] = useState(null);
  const [unmatchedClients, setUnmatchedClients] = useState([]);
  const [unmatchedPagination, setUnmatchedPagination] = useState(null);
  const [unmatchedSummary, setUnmatchedSummary] = useState(null);
  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState('all');
  const [ordering, setOrdering] = useState('-last_seen');
  const [loading, setLoading] = useState(true);
  const [loadingMoreActivity, setLoadingMoreActivity] = useState(false);
  const [loadingMoreUnmatched, setLoadingMoreUnmatched] = useState(false);
  const [error, setError] = useState('');

  async function loadActivity({ offset = 0, append = false } = {}) {
    const params = { limit: 100, offset, search: search.trim(), ordering };
    if (filter === 'blocked') params.blocked = true;
    if (filter === 'allowed') params.blocked = false;
    const payload = await apiRequest('dns-activity/', { params });
    const nextActivity = payload.data || [];
    setActivity((current) => append ? appendUniqueById(current, nextActivity) : nextActivity);
    setActivityPagination(payload.pagination || null);
    setSummary(payload.summary || null);
    setIntegration(payload.integration || null);
  }

  async function loadUnmatched({ offset = 0, append = false } = {}) {
    const payload = await apiRequest('dns-activity/unmatched/', {
      params: { limit: 100, offset, search: search.trim(), ordering: '-last_seen' },
    });
    const nextClients = payload.data || [];
    setUnmatchedClients((current) => append ? appendUniqueById(current, nextClients) : nextClients);
    setUnmatchedPagination(payload.pagination || null);
    setUnmatchedSummary(payload.summary || null);
  }

  useEffect(() => {
    let active = true;
    const timer = window.setTimeout(() => {
      setLoading(true);
      setError('');
      Promise.all([loadActivity(), loadUnmatched()])
        .catch((err) => { if (active) setError(err.message); })
        .finally(() => { if (active) setLoading(false); });
    }, 250);
    return () => {
      active = false;
      window.clearTimeout(timer);
    };
  }, [search, filter, ordering]);

  async function loadMoreActivity() {
    if (!hasNextActivityPage(activityPagination) || loadingMoreActivity) return;
    setLoadingMoreActivity(true);
    try {
      await loadActivity({ offset: activityPagination.next_offset, append: true });
    } catch (err) {
      onError(err);
    } finally {
      setLoadingMoreActivity(false);
    }
  }

  async function loadMoreUnmatched() {
    if (!hasNextActivityPage(unmatchedPagination) || loadingMoreUnmatched) return;
    setLoadingMoreUnmatched(true);
    try {
      await loadUnmatched({ offset: unmatchedPagination.next_offset, append: true });
    } catch (err) {
      onError(err);
    } finally {
      setLoadingMoreUnmatched(false);
    }
  }

  const number = (value) => Number(value || 0).toLocaleString();

  return (
    <Stack gap="lg">
      <Group justify="space-between" align="flex-end" wrap="wrap">
        <Group gap="sm">
          <PageIcon>
            <IconWorldSearch size={26} />
          </PageIcon>
          <Box>
            <Title order={2}>DNS Activity</Title>
            <Text c="dimmed">
              {integration?.provider_name || 'DNS provider'} destinations grouped by device
            </Text>
          </Box>
        </Group>
        <Group gap="xs">
          {integration?.enabled && integration?.configured && integration?.web_url && (
            <Button
              component="a"
              href={integration.web_url}
              target="_blank"
              rel="noreferrer"
              variant="default"
              leftSection={<IconArrowUpRight size={17} />}
            >
              Open {integration?.provider_name || 'DNS provider'}
            </Button>
          )}
          <Badge variant="light">{number(summary?.unique_domains)} domains</Badge>
          <Badge variant="light" color="teal">{number(summary?.active_devices)} devices</Badge>
        </Group>
      </Group>

      {error && <Alert color="red" icon={<IconAlertCircle size={18} />}>{error}</Alert>}
      {!integration?.enabled && !loading && (
        <Alert color="blue" icon={<IconWorldSearch size={18} />}>
          Enable and configure AdGuard Home, Pi-hole, or Technitium in Settings to collect DNS activity.
        </Alert>
      )}
      {integration?.last_error && (
        <Alert color="red" icon={<IconAlertCircle size={18} />}>
          Last synchronization failed: {integration.last_error}
        </Alert>
      )}

      <SimpleGrid cols={{ base: 2, md: 4 }}>
        <Box className="device-field"><Text size="xs" c="dimmed">DNS queries</Text><Text fw={700} size="xl">{number(summary?.total_queries)}</Text></Box>
        <Box className="device-field"><Text size="xs" c="dimmed">Blocked queries</Text><Text fw={700} size="xl">{number(summary?.blocked_queries)}</Text></Box>
        <Box className="device-field"><Text size="xs" c="dimmed">Unmatched clients</Text><Text fw={700} size="xl">{number(unmatchedSummary?.clients)}</Text></Box>
        <Box className="device-field"><Text size="xs" c="dimmed">Last sync</Text><Text fw={600}>{formatDate(integration?.last_sync_at, timeZone)}</Text></Box>
      </SimpleGrid>

      <Group justify="space-between" align="flex-end" wrap="wrap">
        <TextInput
          w={{ base: '100%', sm: 320 }}
          label="Search"
          placeholder="Domain, device, IP, or MAC"
          leftSection={<IconSearch size={17} />}
          value={search}
          onChange={(event) => setSearch(event.currentTarget.value)}
        />
        <Group align="flex-end" wrap="wrap">
          <SegmentedControl value={filter} onChange={setFilter} data={[
            { value: 'all', label: 'All' },
            { value: 'allowed', label: 'Allowed' },
            { value: 'blocked', label: 'Blocked' },
          ]} />
          <Select w={180} label="Sort" value={ordering} onChange={(value) => setOrdering(value || '-last_seen')} data={[
            { value: '-last_seen', label: 'Latest activity' },
            { value: '-query_count', label: 'Most queries' },
            { value: '-blocked_count', label: 'Most blocked' },
            { value: 'domain', label: 'Domain' },
            { value: 'device__name', label: 'Device' },
          ]} />
        </Group>
      </Group>

      <ActivityTablePanel hasMore={hasNextActivityPage(activityPagination)} loadingMore={loadingMoreActivity} onLoadMore={loadMoreActivity}>
        <LoadingOverlay visible={loading} />
        <Table verticalSpacing="sm">
          <Table.Thead><Table.Tr><Table.Th>Domain</Table.Th><Table.Th>Device</Table.Th><Table.Th>Type</Table.Th><Table.Th>Queries</Table.Th><Table.Th>Blocked</Table.Th><Table.Th style={{ whiteSpace: 'nowrap' }}>Last seen</Table.Th></Table.Tr></Table.Thead>
          <Table.Tbody>
            {activity.map((item) => (
              <Table.Tr key={item.id}>
                <Table.Td><Text fw={600}>{item.domain}</Text></Table.Td>
                <Table.Td><UnstyledButton onClick={() => onSelectDevice({ id: item.device_id })}><Text fw={600} c="blue">{item.device_name}</Text><Text size="xs" c="dimmed">{item.device_ip}</Text></UnstyledButton></Table.Td>
                <Table.Td>{item.query_type || '-'}</Table.Td>
                <Table.Td>{number(item.query_count)}</Table.Td>
                <Table.Td><Badge color={item.blocked_count ? 'red' : 'gray'} variant="light">{number(item.blocked_count)}</Badge></Table.Td>
                <Table.Td style={{ whiteSpace: 'nowrap' }}>{formatDate(item.last_seen, timeZone)}</Table.Td>
              </Table.Tr>
            ))}
            {!loading && activity.length === 0 && (
              <Table.Tr><Table.Td colSpan={6}><Text c="dimmed" ta="center" py="xl">No DNS activity matches these filters.</Text></Table.Td></Table.Tr>
            )}
          </Table.Tbody>
        </Table>
      </ActivityTablePanel>

      <Divider />
      <Box>
        <Group justify="space-between" align="flex-end">
          <Box><Title order={3}>Unmatched clients</Title><Text c="dimmed" size="sm">DNS client identifiers that do not match a current LanGuard device IP.</Text></Box>
          <Badge color={unmatchedSummary?.clients ? 'orange' : 'gray'} variant="light">{number(unmatchedSummary?.clients)} clients</Badge>
        </Group>
        <Alert color="blue" mt="sm" icon={<IconAlertCircle size={18} />}>
          Check DHCP, DNS forwarding, or stale client addresses. Activity can only be assigned when the DNS provider records the device IP directly.
        </Alert>
      </Box>

      <ActivityTablePanel hasMore={hasNextActivityPage(unmatchedPagination)} loadingMore={loadingMoreUnmatched} onLoadMore={loadMoreUnmatched}>
        <Table verticalSpacing="sm">
          <Table.Thead><Table.Tr><Table.Th>Client</Table.Th><Table.Th>Queries</Table.Th><Table.Th>Blocked</Table.Th><Table.Th>Last domain</Table.Th><Table.Th style={{ whiteSpace: 'nowrap' }}>Last seen</Table.Th></Table.Tr></Table.Thead>
          <Table.Tbody>
            {unmatchedClients.map((client) => (
              <Table.Tr key={client.id}><Table.Td><Text fw={600}>{client.client}</Text></Table.Td><Table.Td>{number(client.query_count)}</Table.Td><Table.Td>{number(client.blocked_count)}</Table.Td><Table.Td>{client.last_domain || '-'}</Table.Td><Table.Td style={{ whiteSpace: 'nowrap' }}>{formatDate(client.last_seen, timeZone)}</Table.Td></Table.Tr>
            ))}
            {!loading && unmatchedClients.length === 0 && (
              <Table.Tr><Table.Td colSpan={5}><Text c="dimmed" ta="center" py="xl">All recorded DNS clients are matched.</Text></Table.Td></Table.Tr>
            )}
          </Table.Tbody>
        </Table>
      </ActivityTablePanel>
    </Stack>
  );
}
