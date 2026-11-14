import { useEffect, useState } from 'react';
import {
  Alert, Badge, Box, Button, Group, NumberInput, PasswordInput, Select, SimpleGrid,
  Stack, Switch, Text, TextInput,
} from '@mantine/core';
import { IconListSearch, IconPlugConnected, IconRefresh } from '@tabler/icons-react';
import Image from 'next/image';
import { apiRequest } from '../api';
import { formatDate } from '../utils/date';
import { showErrorNotification, showServerNotification } from '../utils/notifications';

const endpoint = 'integrations/controllers/unifi/';
const defaults = { enabled: false, url: '', api_key: '', site_id: null, verify_ssl: true, sync_interval: 5 };

export default function UniFiIntegrationSettings({ timeZone, onChanged }) {
  const [form, setForm] = useState(defaults);
  const [saved, setSaved] = useState(null);
  const [sites, setSites] = useState([]);
  const [busy, setBusy] = useState('load');
  const [error, setError] = useState('');

  function hydrate(data) {
    setSaved(data);
    setForm({ ...defaults, ...Object.fromEntries(Object.keys(defaults)
      .filter(key => key !== 'api_key').map(key => [key, data[key]])) });
  }

  async function run(action, work) {
    setBusy(action);
    setError('');
    try {
      await work();
    } catch (err) {
      setError(err.message);
      showErrorNotification(err);
    } finally {
      setBusy('');
    }
  }

  useEffect(() => {
    run('load', async () => hydrate((await apiRequest(endpoint, { timeoutMs: 8000 })).data));
  }, []);

  const set = (key, value) => {
    setForm(current => ({ ...current, [key]: value, ...(key === 'url' ? { site_id: null } : {}) }));
    if (key === 'url' || key === 'api_key' || key === 'verify_ssl') setSites([]);
  };
  const dirty = !!saved && Object.keys(defaults).some(key => key === 'api_key' ? !!form.api_key : form[key] !== saved[key]);
  const credentialsReady = !!form.url.trim() && (!!form.api_key || (saved?.has_key && form.url.trim() === saved.url));
  const payload = { ...form, url: form.url.trim() };
  const options = sites.map(site => ({ value: site.id, label: site.name }));
  if (form.site_id && !options.some(site => site.value === form.site_id)) {
    options.push({ value: form.site_id, label: saved?.last_result?.site_name || 'Saved site' });
  }
  const summary = saved?.last_result;

  function probe(action) {
    return run(action, async () => {
      const response = await apiRequest(endpoint + action + '/', {
        method: 'POST', body: payload, timeoutMs: 35000,
      });
      if (response.data.sites) {
        setSites(response.data.sites);
        setForm(current => ({ ...current, site_id: response.data.sites.some(site => site.id === current.site_id)
          ? current.site_id : response.data.sites.length === 1 ? response.data.sites[0].id : null }));
      }
      showServerNotification(response);
    });
  }

  return (
    <Stack className="settings-subsection" gap="sm">
      <Group justify="space-between">
        <Group gap="sm">
          <Box bg="white" px={6} py={4} style={{ borderRadius: 4, display: 'flex' }}>
            <Image src="/integrations/unifi.svg" alt="" width={53} height={16} />
          </Box>
          <Text fw={700}>UniFi Network</Text>
          <Switch label="Enabled" checked={form.enabled} disabled={!saved || !!busy}
            onChange={event => set('enabled', event.currentTarget.checked)} />
        </Group>
        <Badge color={saved?.configured ? 'teal' : 'gray'}>{saved?.configured ? 'Configured' : 'Not configured'}</Badge>
      </Group>
      <SimpleGrid cols={{ base: 1, md: 2 }}>
        <TextInput label="Controller URL" placeholder="https://192.168.1.1" value={form.url}
          disabled={!saved || !!busy} onChange={event => set('url', event.currentTarget.value)} />
        <PasswordInput label="Local API key" autoComplete="new-password" value={form.api_key}
          placeholder={saved?.has_key ? 'Saved API key' : ''} disabled={!saved || !!busy}
          onChange={event => set('api_key', event.currentTarget.value)} />
        <Select label="UniFi site" data={options} value={form.site_id} allowDeselect={false}
          disabled={!saved || !!busy || !options.length} onChange={value => set('site_id', value)} />
        <NumberInput label="Sync interval" suffix=" min" min={1} max={1440} allowDecimal={false}
          value={form.sync_interval} disabled={!saved || !!busy}
          onChange={value => set('sync_interval', Number(value) || 5)} />
      </SimpleGrid>
      <Switch label="Verify TLS certificate" checked={form.verify_ssl} disabled={!saved || !!busy}
        onChange={event => set('verify_ssl', event.currentTarget.checked)} />
      {(error || saved?.last_error) && <Alert color="red" title="UniFi">{error || saved.last_error}</Alert>}
      {saved?.last_error && saved.last_attempt_at && (
        <Text size="sm" c="dimmed">Last attempt: {formatDate(saved.last_attempt_at, timeZone)}</Text>
      )}
      <Text size="sm" c="dimmed">{saved?.last_sync_at ? `Last sync: ${formatDate(saved.last_sync_at, timeZone)}` : 'Not synced yet'}</Text>
      {summary?.status === 'ok' && (
        <Text size="sm" c="dimmed">
          {summary.clients_reported} reported · {summary.created} created · {summary.updated} updated · {summary.skipped} skipped · {summary.conflicts} conflicts
        </Text>
      )}
      <Group gap="sm">
        <Button variant="default" leftSection={<IconListSearch size={18} />} loading={busy === 'sites'}
          disabled={!credentialsReady || !!busy} onClick={() => probe('sites')}>Load sites</Button>
        <Button variant="default" leftSection={<IconPlugConnected size={18} />} loading={busy === 'test'}
          disabled={!credentialsReady || !!busy} onClick={() => probe('test')}>Test connection</Button>
        <Button loading={busy === 'save'} disabled={!dirty || !!busy || (form.enabled && (!credentialsReady || !form.site_id))}
          onClick={() => run('save', async () => {
            const response = await apiRequest(endpoint, { method: 'PUT', body: payload, timeoutMs: 8000 });
            hydrate(response.data);
            showServerNotification(response);
          })}>Save UniFi settings</Button>
        <Button variant="light" leftSection={<IconRefresh size={18} />} loading={busy === 'sync'}
          disabled={!saved?.enabled || !saved.configured || dirty || !!busy}
          onClick={() => run('sync', async () => {
            try {
              showServerNotification(await apiRequest(endpoint + 'sync/', { method: 'POST', timeoutMs: 45000 }));
              await onChanged?.();
            } finally {
              hydrate((await apiRequest(endpoint, { timeoutMs: 8000 })).data);
            }
          })}>Sync now</Button>
        {!saved && !busy && <Button variant="default" onClick={() => run('load', async () =>
          hydrate((await apiRequest(endpoint, { timeoutMs: 8000 })).data))}>Retry</Button>}
      </Group>
    </Stack>
  );
}
