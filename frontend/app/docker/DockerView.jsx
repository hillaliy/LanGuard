'use client';

import { useEffect, useState } from 'react';
import {
  ActionIcon,
  Alert,
  Badge,
  Box,
  Button,
  Group,
  LoadingOverlay,
  Paper,
  SimpleGrid,
  Stack,
  Table,
  Text,
  TextInput,
  ThemeIcon,
  Title,
  Tooltip,
  UnstyledButton,
} from '@mantine/core';
import { notifications } from '@mantine/notifications';
import {
  IconAlertCircle,
  IconArrowRight,
  IconBrandDocker,
  IconCheck,
  IconRefresh,
  IconSearch,
} from '@tabler/icons-react';

import { apiRequest } from '../api';
import PageIcon from '../components/PageIcon';
import { formatDate } from '../utils/date';

function DockerPortMapping({ port, hostName }) {
  const protocol = String(port.protocol || 'tcp').toUpperCase();
  const binding = port.host_ip && !['0.0.0.0', '::'].includes(port.host_ip)
    ? `${port.host_ip}:`
    : '';
  return (
    <span className="docker-port-mapping">
      <Text component="span" size="xs" fw={700}>{protocol}</Text>
      <Text component="span" size="xs">Host {binding}{port.host_port}</Text>
      <IconArrowRight size={14} aria-hidden="true" />
      <Text component="span" size="xs">Container {port.container_port}</Text>
      {port.observed_by_languard && (
        <Tooltip label={`LanGuard also found ${protocol}/${port.host_port} reachable on ${hostName}`}>
          <span className="docker-port-confirmed" aria-label="Host port confirmed reachable by LanGuard">
            <IconCheck size={13} />
          </span>
        </Tooltip>
      )}
    </span>
  );
}
function DockerContainerState({ container }) {
  const state = String(container.state || 'unknown').toLowerCase();
  const health = String(container.health || '').toLowerCase();
  const stateColor = {
    running: 'teal',
    restarting: 'blue',
    paused: 'yellow',
    exited: 'red',
    stopped: 'red',
    dead: 'red',
    created: 'gray',
  }[state] || 'gray';
  const healthColor = {
    healthy: 'teal',
    unhealthy: 'red',
    starting: 'yellow',
  }[health] || 'gray';
  const status = String(container.status || '').replace(
    /\s*\((?:healthy|unhealthy|starting)\)\s*$/i,
    ''
  );

  return (
    <Stack className="docker-container-state" gap={4} align="center">
      <Group gap={6} wrap="nowrap" justify="center">
        <Badge color={stateColor} variant="light">
          {state}
        </Badge>
        {container.health && (
          <Badge
            color={healthColor}
            variant="light"
          >
            {container.health}
          </Badge>
        )}
      </Group>
      {status && <Text size="xs" c="dimmed" ta="center">{status}</Text>}
    </Stack>
  );
}

function DockerContainerNetwork({ container, onSelectDevice }) {
  return (
    <Box className="docker-container-network">
      <Text size="sm" truncate="end">{container.network_mode || '-'}</Text>
      {(container.addresses || []).map((address) => (
        <Text key={`${address.network}-${address.ip}`} size="xs" c="dimmed" truncate="end">
          {address.network}: {address.ip}
        </Text>
      ))}
      {container.linked_device_name && (
        <UnstyledButton className="docker-linked-device" onClick={() => onSelectDevice({ id: container.linked_device })}>
          <Text size="xs" c="blue" fw={600} truncate="end">Linked to {container.linked_device_name}</Text>
        </UnstyledButton>
      )}
    </Box>
  );
}

export default function DockerView({ timeZone, canManageUsers, onSelectDevice, onError }) {
  const [inventory, setInventory] = useState({ hosts: [], total_containers: 0 });
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState('');
  const [search, setSearch] = useState('');

  async function loadInventory({ quiet = false } = {}) {
    if (!quiet) setLoading(true);
    try {
      const payload = await apiRequest('integrations/docker/inventory/');
      setInventory(payload.data || { hosts: [], total_containers: 0 });
      setError('');
    } catch (err) {
      setError(err.message);
    } finally {
      if (!quiet) setLoading(false);
    }
  }

  useEffect(() => {
    loadInventory();
  }, []);

  const hosts = inventory.hosts || [];
  const containers = hosts.flatMap((host) => host.containers || []);
  const runningCount = containers.filter((container) => container.state === 'running').length;
  const attentionCount = containers.filter(
    (container) => container.state !== 'running' || container.health === 'unhealthy'
  ).length;
  const normalizedSearch = search.trim().toLowerCase();
  const filteredHosts = hosts.map((host) => ({
    ...host,
    containers: (host.containers || []).filter((container) => {
      if (!normalizedSearch) return true;
      const searchable = [
        container.name,
        container.image,
        container.network_mode,
        ...(container.addresses || []).flatMap((address) => [address.network, address.ip]),
        ...(container.published_ports || []).flatMap((port) => [
          port.host_port,
          port.container_port,
          port.protocol,
        ]),
      ].join(' ').toLowerCase();
      return searchable.includes(normalizedSearch);
    }),
  })).filter((host) => !normalizedSearch || host.containers.length);

  async function requestSync() {
    setSyncing(true);
    try {
      await Promise.all(hosts.map((host) => apiRequest(
        `integrations/docker/hosts/${host.id}/sync/`,
        { method: 'POST' }
      )));
      notifications.show({
        title: 'Docker inventory',
        message: 'Inventory sync queued. The scheduler will process it shortly.',
        color: 'teal',
      });
    } catch (err) {
      onError(err);
    } finally {
      setSyncing(false);
    }
  }

  return (
    <Stack gap="lg" className="docker-inventory-page" pos="relative">
      <LoadingOverlay visible={loading} />
      <Group justify="space-between" align="flex-end" wrap="wrap">
        <Group gap="sm">
          <PageIcon>
            <IconBrandDocker size={27} />
          </PageIcon>
          <Box>
            <Title order={2}>Docker</Title>
            <Text c="dimmed">Local container inventory and published host ports</Text>
          </Box>
        </Group>
        <Group gap="sm">
          <Tooltip label="Reload saved inventory">
            <ActionIcon variant="light" size="lg" onClick={() => loadInventory()} loading={loading}>
              <IconRefresh size={19} />
            </ActionIcon>
          </Tooltip>
          {canManageUsers && hosts.length > 0 && (
            <Button
              variant="default"
              leftSection={<IconRefresh size={17} />}
              loading={syncing}
              onClick={requestSync}
            >
              Sync inventory
            </Button>
          )}
        </Group>
      </Group>

      {error && <Alert color="red" icon={<IconAlertCircle size={18} />}>{error}</Alert>}

      {!loading && hosts.length === 0 ? (
        <Paper className="content-panel docker-empty-state" radius="md" p="xl">
          <ThemeIcon size={54} radius="md" variant="light"><IconBrandDocker size={30} /></ThemeIcon>
          <Title order={3}>Docker inventory is not configured</Title>
          <Text c="dimmed" ta="center">
            {canManageUsers
              ? 'Configure the local Docker host under Settings > Integrations > Network services.'
              : 'Ask an administrator to configure the local Docker inventory integration.'}
          </Text>
        </Paper>
      ) : (
        <>
          <SimpleGrid cols={{ base: 2, md: 4 }}>
            <Box className="device-field"><Text size="xs" c="dimmed">Docker hosts</Text><Text fw={700} size="xl">{hosts.length}</Text></Box>
            <Box className="device-field"><Text size="xs" c="dimmed">Containers</Text><Text fw={700} size="xl">{containers.length}</Text></Box>
            <Box className="device-field"><Text size="xs" c="dimmed">Running</Text><Text fw={700} size="xl">{runningCount}</Text></Box>
            <Box className="device-field"><Text size="xs" c="dimmed">Needs review</Text><Text fw={700} size="xl">{attentionCount}</Text></Box>
          </SimpleGrid>

          <TextInput
            className="docker-inventory-search"
            label="Search containers"
            placeholder="Name, image, network, IP, or port"
            leftSection={<IconSearch size={17} />}
            value={search}
            onChange={(event) => setSearch(event.currentTarget.value)}
          />

          {filteredHosts.map((host) => (
            <Paper key={host.id} className="content-panel docker-host-panel" radius="md">
              <Group className="docker-host-header" justify="space-between" align="flex-start" wrap="wrap">
                <Box>
                  <Group gap="xs" wrap="wrap">
                    <IconBrandDocker size={22} />
                    <Title order={3}>Docker inventory</Title>
                    <Badge color={host.enabled ? 'teal' : 'gray'} variant="light">
                      {host.enabled ? 'Sync enabled' : 'Sync disabled'}
                    </Badge>
                  </Group>
                  <Text size="sm" c="dimmed" mt={4}>
                    {host.docker_name || host.name} · Docker {host.docker_version || 'not synced'} · {host.operating_system || 'Operating system unknown'} {host.architecture || ''}
                  </Text>
                  <UnstyledButton mt={4} onClick={() => onSelectDevice({ id: host.device })}>
                    <Text c="blue" fw={600} size="sm">{host.device_name} · {host.device_ip}</Text>
                  </UnstyledButton>
                </Box>
                <Text size="sm" c="dimmed">Synced {formatDate(host.last_sync_at, timeZone)}</Text>
              </Group>

              {host.last_error && (
                <Alert color="red" mx="md" mt="md" icon={<IconAlertCircle size={18} />}>
                  Last synchronization failed: {host.last_error}
                </Alert>
              )}

              <div className="docker-container-table">
                <Table.ScrollContainer minWidth={900}>
                  <Table className="docker-inventory-table" striped highlightOnHover verticalSpacing="sm">
                    <colgroup>
                      <col className="docker-column-container" />
                      <col className="docker-column-state" />
                      <col className="docker-column-network" />
                      <col className="docker-column-ports" />
                      <col className="docker-column-restarts" />
                    </colgroup>
                    <Table.Thead>
                      <Table.Tr>
                        <Table.Th>Container</Table.Th>
                        <Table.Th ta="center">State</Table.Th>
                        <Table.Th>Network</Table.Th>
                        <Table.Th>Published ports</Table.Th>
                        <Table.Th ta="center">Restarts</Table.Th>
                      </Table.Tr>
                    </Table.Thead>
                    <Table.Tbody>
                      {host.containers.map((container) => (
                        <Table.Tr key={container.id}>
                          <Table.Td className="docker-container-identity">
                            <Text size="sm" fw={700} truncate="end">
                              {container.name}
                            </Text>
                            <Text
                              size="xs"
                              c="dimmed"
                              truncate="end"
                            >
                              {container.image || container.image_id || '-'}
                            </Text>
                            {container.started_at && (
                              <Text size="xs" c="dimmed" truncate="end">
                                Started {formatDate(container.started_at, timeZone)}
                              </Text>
                            )}
                          </Table.Td>
                          <Table.Td ta="center"><DockerContainerState container={container} /></Table.Td>
                          <Table.Td><DockerContainerNetwork container={container} onSelectDevice={onSelectDevice} /></Table.Td>
                          <Table.Td>
                            <Stack gap={5} align="flex-start">
                              {(container.published_ports || []).length
                                ? container.published_ports.map((port) => (
                                  <DockerPortMapping
                                    key={`${port.host_ip}-${port.host_port}-${port.protocol}`}
                                    port={port}
                                    hostName={host.name}
                                  />
                                ))
                                : <Text size="sm">-</Text>}
                            </Stack>
                          </Table.Td>
                          <Table.Td ta="center">{container.restart_count ?? 0}</Table.Td>
                        </Table.Tr>
                      ))}
                    </Table.Tbody>
                  </Table>
                </Table.ScrollContainer>
              </div>

              <Stack className="docker-container-mobile-list" gap="sm">
                {host.containers.map((container) => (
                  <Box key={container.id} className="docker-container-mobile-card">
                    <Group justify="space-between" align="flex-start" gap="sm">
                      <Box className="docker-container-mobile-title">
                        <Text fw={700} truncate="end">{container.name}</Text>
                        <Text
                          size="xs"
                          c="dimmed"
                          truncate="end"
                        >
                          {container.image || container.image_id || '-'}
                        </Text>
                      </Box>
                      <DockerContainerState container={container} />
                    </Group>
                    <SimpleGrid cols={2} mt="sm">
                      <Box><Text size="xs" c="dimmed">Network</Text><DockerContainerNetwork container={container} onSelectDevice={onSelectDevice} /></Box>
                      <Box><Text size="xs" c="dimmed">Restarts</Text><Text size="sm">{container.restart_count ?? 0}</Text></Box>
                    </SimpleGrid>
                    <Stack gap={5} mt="sm" align="flex-start">
                      <Text size="xs" c="dimmed">Published ports</Text>
                      {(container.published_ports || []).length
                        ? container.published_ports.map((port) => (
                          <DockerPortMapping
                            key={`${port.host_ip}-${port.host_port}-${port.protocol}`}
                            port={port}
                            hostName={host.name}
                          />
                        ))
                        : <Text size="sm">-</Text>}
                    </Stack>
                  </Box>
                ))}
              </Stack>

              {!host.containers.length && (
                <Text c="dimmed" ta="center" py="xl">No containers match this search.</Text>
              )}
            </Paper>
          ))}

          {!loading && normalizedSearch && filteredHosts.length === 0 && (
            <Alert color="blue" icon={<IconSearch size={18} />}>No containers match this search.</Alert>
          )}
        </>
      )}
    </Stack>
  );
}
