import { useEffect, useState } from 'react';
import { ActionIcon, Alert, Badge, Box, Button, Divider, Group, LoadingOverlay, Modal, NumberInput, Select, SimpleGrid, Stack, Switch, Table, Text, TextInput, Tooltip } from '@mantine/core';
import { notifications } from '@mantine/notifications';
import { IconAlertCircle, IconBrandDocker, IconDeviceFloppy, IconEdit, IconRefresh, IconTrash } from '@tabler/icons-react';
import { apiRequest } from '../api';
import { formatDate } from '../utils/date';
import { displayDeviceName } from '../utils/device';
import { showErrorNotification } from '../utils/notifications';

const emptyDockerHostForm = {
  id: null,
  device: '',
  name: '',
  enabled: true,
  sync_interval: 5,
};

export default function DockerIntegrationSettings({
  timeZone,
  onChanged,
}) {
  const [hosts, setHosts] = useState([]);
  const [devices, setDevices] = useState([]);
  const [form, setForm] = useState(emptyDockerHostForm);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [syncing, setSyncing] = useState(null);
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [error, setError] = useState('');

  async function loadDockerData() {
    setLoading(true);
    setError('');
    try {
      async function loadAllDevices() {
        const results = [];
        let offset = 0;
        while (true) {
          const payload = await apiRequest('device/', {
            params: { limit: 100, offset, ordering: 'name' },
          });
          results.push(...(payload.data || []));
          if (payload.pagination?.next_offset == null) {
            return results;
          }
          offset = payload.pagination.next_offset;
        }
      }

      const [hostPayload, allDevices] = await Promise.all([
        apiRequest('integrations/docker/hosts/'),
        loadAllDevices(),
      ]);
      const loadedHosts = hostPayload.data || [];
      setHosts(loadedHosts);
      setDevices(allDevices);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadDockerData();
  }, []);

  function updateForm(field, value) {
    setForm((current) => ({ ...current, [field]: value }));
  }

  function editHost(host) {
    setForm({
      id: host.id,
      device: String(host.device),
      name: host.name,
      enabled: host.enabled,
      sync_interval: host.sync_interval,
    });
    setError('');
  }

  function resetForm() {
    setForm(emptyDockerHostForm);
    setError('');
  }

  async function saveHost() {
    setSaving(true);
    setError('');
    try {
      const body = {
        device: Number(form.device),
        name: form.name.trim(),
        enabled: form.enabled,
        sync_interval: Number(form.sync_interval) || 5,
      };
      await apiRequest(
        form.id ? `integrations/docker/hosts/${form.id}/` : 'integrations/docker/hosts/',
        { method: form.id ? 'PUT' : 'POST', body }
      );
      await loadDockerData();
      await onChanged?.();
      resetForm();
      notifications.show({ title: 'Docker inventory', message: 'Host saved.', color: 'teal' });
    } catch (err) {
      setError(err.message);
      showErrorNotification(err);
    } finally {
      setSaving(false);
    }
  }

  async function syncHost(hostId) {
    setSyncing(hostId);
    try {
      const payload = await apiRequest(`integrations/docker/hosts/${hostId}/sync/`, {
        method: 'POST',
      });
      await loadDockerData();
      notifications.show({
        title: 'Docker inventory',
        message: payload.notification || 'Sync queued. The scheduler will run it shortly.',
        color: 'blue',
      });
    } catch (err) {
      showErrorNotification(err);
    } finally {
      setSyncing(null);
    }
  }

  async function deleteHost() {
    if (!deleteTarget) return;
    setSaving(true);
    try {
      await apiRequest(`integrations/docker/hosts/${deleteTarget.id}/`, { method: 'DELETE' });
      setDeleteTarget(null);
      resetForm();
      await loadDockerData();
      await onChanged?.();
      notifications.show({ title: 'Docker inventory', message: 'Host removed.', color: 'teal' });
    } catch (err) {
      showErrorNotification(err);
    } finally {
      setSaving(false);
    }
  }

  const deviceOptions = devices
    .filter((device) => !device.archived)
    .map((device) => ({
      value: String(device.id),
      label: `${displayDeviceName(device)} (${device.ip || 'No IP'})`,
    }));
  return (
    <Stack className="settings-subsection docker-integration" gap="md" pos="relative">
      <LoadingOverlay visible={loading} />
      <Group justify="space-between" align="flex-start">
        <Box>
          <Group gap="sm">
            <IconBrandDocker size={24} />
            <Text fw={700}>Docker inventory</Text>
          </Group>
          <Text size="sm" c="dimmed" mt={4}>
            Read-only container metadata from the Docker engine running LanGuard.
          </Text>
        </Box>
        <Badge color={hosts.some((host) => host.enabled) ? 'teal' : 'gray'} variant="light">
          {hosts.length ? 'Configured' : 'Not configured'}
        </Badge>
      </Group>

      {hosts.length > 0 && (
        <Table.ScrollContainer minWidth={680}>
          <Table verticalSpacing="sm" highlightOnHover>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Host</Table.Th>
                <Table.Th>Docker</Table.Th>
                <Table.Th>Containers</Table.Th>
                <Table.Th>Last sync</Table.Th>
                <Table.Th w={132} />
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {hosts.map((host) => (
                <Table.Tr key={host.id}>
                  <Table.Td>
                    <Text size="sm" fw={600}>{host.name}</Text>
                    <Text size="xs" c="dimmed">{host.device_name} · {host.device_ip}</Text>
                  </Table.Td>
                  <Table.Td>{host.docker_version || 'Not synced'}</Table.Td>
                  <Table.Td>{host.container_count}</Table.Td>
                  <Table.Td>
                    <Text size="sm">{host.sync_requested ? 'Sync queued' : (host.last_sync_at ? formatDate(host.last_sync_at, timeZone) : 'Never')}</Text>
                    {host.last_error && <Text size="xs" c="red">{host.last_error}</Text>}
                  </Table.Td>
                  <Table.Td>
                    <Group gap={4} justify="flex-end" wrap="nowrap">
                      <Tooltip label="Sync now">
                        <ActionIcon variant="subtle" loading={syncing === host.id} onClick={() => syncHost(host.id)}>
                          <IconRefresh size={17} />
                        </ActionIcon>
                      </Tooltip>
                      <Tooltip label="Edit host">
                        <ActionIcon variant="subtle" onClick={() => editHost(host)}>
                          <IconEdit size={17} />
                        </ActionIcon>
                      </Tooltip>
                      <Tooltip label="Remove host">
                        <ActionIcon color="red" variant="subtle" onClick={() => setDeleteTarget(host)}>
                          <IconTrash size={17} />
                        </ActionIcon>
                      </Tooltip>
                    </Group>
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
      )}

      {(!hosts.length || form.id) && (
        <>
          <Divider label={form.id ? `Edit ${form.name}` : 'Configure local Docker host'} labelPosition="left" />
          {error && <Alert color="red" icon={<IconAlertCircle size={18} />}>{error}</Alert>}
          <SimpleGrid cols={{ base: 1, md: 2 }}>
            <Select
              label="LanGuard device"
              description="The device that represents this Docker host."
              data={deviceOptions}
              value={form.device}
              onChange={(value) => updateForm('device', value || '')}
              searchable
              required
            />
            <TextInput
              label="Display name"
              description="The name shown for this Docker host."
              value={form.name}
              onChange={(event) => updateForm('name', event.currentTarget.value)}
              required
            />
            <NumberInput label="Sync interval" suffix=" min" min={1} max={1440} value={form.sync_interval} onChange={(value) => updateForm('sync_interval', Number(value) || 5)} />
            <Group justify="space-between" align="center" mt={27} wrap="wrap">
              <Switch label="Sync enabled" checked={form.enabled} onChange={(event) => updateForm('enabled', event.currentTarget.checked)} />
              <Group gap="xs">
                {form.id && <Button variant="subtle" onClick={resetForm}>Cancel</Button>}
                <Button variant="default" leftSection={<IconDeviceFloppy size={18} />} loading={saving} disabled={!form.device || !form.name.trim()} onClick={saveHost}>Save host</Button>
              </Group>
            </Group>
          </SimpleGrid>
        </>
      )}

      <Modal opened={Boolean(deleteTarget)} onClose={() => setDeleteTarget(null)} title="Remove Docker host" centered>
        <Stack>
          <Text>Remove {deleteTarget?.name} and its stored container inventory?</Text>
          <Text size="sm" c="dimmed">The Docker host and its containers are not changed.</Text>
          <Group justify="flex-end">
            <Button variant="default" onClick={() => setDeleteTarget(null)}>Cancel</Button>
            <Button color="red" loading={saving} onClick={deleteHost}>Remove</Button>
          </Group>
        </Stack>
      </Modal>
    </Stack>
  );
}
