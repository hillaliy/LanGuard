import { useEffect, useState } from 'react';
import {
  Alert, Anchor, Badge, Box, Button, Group, NumberInput, PasswordInput, Select, SimpleGrid,
  Stack, Switch, Text, TextInput,
} from '@mantine/core';
import { IconListSearch, IconPlugConnected, IconRefresh, IconRouter } from '@tabler/icons-react';
import Image from 'next/image';
import { apiRequest } from '../api';
import { formatDate } from '../utils/date';
import { showErrorNotification, showServerNotification } from '../utils/notifications';

export default function ControllerIntegrationSettings({ provider, timeZone, onChanged }) {
  const omada = provider === 'omada';
  const name = omada ? 'TP-Link Omada' : 'UniFi Network';
  const shortName = omada ? 'Omada' : 'UniFi';
  const secretField = omada ? 'client_secret' : 'api_key';
  const endpoint = `integrations/controllers/${provider}/`;
  const defaults = { enabled: false, url: '', [secretField]: '', site_id: null, verify_ssl: true, sync_interval: 5,
    ...(omada ? { client_id: '', controller_id: '' } : {}) };
  const [form, setForm] = useState(defaults);
  const [saved, setSaved] = useState(null);
  const [sites, setSites] = useState([]);
  const [busy, setBusy] = useState('load');
  const [error, setError] = useState('');

  function hydrate(data) {
    setSaved(data);
    setForm({ ...defaults, ...Object.fromEntries(Object.keys(defaults)
      .filter(key => key !== secretField).map(key => [key, data[key]])) });
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
    setForm(current => ({ ...current, [key]: value,
      ...(['url', 'controller_id', 'client_id'].includes(key) ? { site_id: null } : {}) }));
    if (['url', secretField, 'verify_ssl', 'controller_id', 'client_id'].includes(key)) setSites([]);
  };
  const dirty = !!saved && Object.keys(defaults).some(key => key === secretField ? !!form[secretField] : form[key] !== saved[key]);
  const sameIdentity = saved?.has_key && form.url.trim() === saved.url && (!omada
    || (form.controller_id === saved.controller_id && form.client_id === saved.client_id));
  const credentialsReady = !!form.url.trim() && (!omada || (!!form.controller_id && !!form.client_id))
    && (!!form[secretField] || sameIdentity);
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
          {omada ? <IconRouter size={24} aria-hidden="true" /> : <Box bg="white" px={6} py={4} style={{ borderRadius: 4, display: 'flex' }}>
            <Image src="/integrations/unifi.svg" alt="" width={53} height={16} />
          </Box>}
          <Text fw={700}>{name}</Text>
          <Switch label="Enabled" checked={form.enabled} disabled={!saved || !!busy}
            onChange={event => set('enabled', event.currentTarget.checked)} />
        </Group>
        <Badge color={saved?.configured ? 'teal' : 'gray'}>{saved?.configured ? 'Configured' : 'Not configured'}</Badge>
      </Group>
      <SimpleGrid cols={{ base: 1, md: 2 }}>
        <TextInput label="Controller URL" placeholder="https://192.168.1.1" value={form.url}
          disabled={!saved || !!busy} onChange={event => set('url', event.currentTarget.value)} />
        {omada && <>
          <TextInput label="Omada controller ID" value={form.controller_id} disabled={!saved || !!busy}
            onChange={event => set('controller_id', event.currentTarget.value)} />
          <TextInput label="Client ID" value={form.client_id} disabled={!saved || !!busy}
            onChange={event => set('client_id', event.currentTarget.value)} />
        </>}
        <PasswordInput label={omada ? 'Client Secret' : 'Local API key'} autoComplete="new-password" value={form[secretField]}
          placeholder={saved?.has_key ? 'Saved secret' : ''} disabled={!saved || !!busy}
          onChange={event => set(secretField, event.currentTarget.value)} />
        <Select label={`${shortName} site`} data={options} value={form.site_id} allowDeselect={false}
          disabled={!saved || !!busy || !options.length} onChange={value => set('site_id', value)} />
        <NumberInput label="Sync interval" suffix=" min" min={1} max={1440} allowDecimal={false}
          value={form.sync_interval} disabled={!saved || !!busy}
          onChange={value => set('sync_interval', Number(value) || 5)} />
      </SimpleGrid>
      <Switch label="Verify TLS certificate" checked={form.verify_ssl} disabled={!saved || !!busy}
        onChange={event => set('verify_ssl', event.currentTarget.checked)} />
      {(error || saved?.last_error) && <Alert color="red" title={shortName}>{error || saved.last_error}</Alert>}
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
        <Anchor href={`https://hillaliy.github.io/LanGuard/docs/integrations#${omada ? 'tp-link-omada' : 'unifi-network'}`}
          target="_blank" rel="noopener noreferrer" size="sm">{shortName} setup</Anchor>
        <Button variant="default" leftSection={<IconListSearch size={18} />} loading={busy === 'sites'}
          disabled={!credentialsReady || !!busy} onClick={() => probe('sites')}>Load sites</Button>
        <Button variant="default" leftSection={<IconPlugConnected size={18} />} loading={busy === 'test'}
          disabled={!credentialsReady || !!busy} onClick={() => probe('test')}>Test connection</Button>
        <Button loading={busy === 'save'} disabled={!dirty || !!busy || (form.enabled && (!credentialsReady || !form.site_id))}
          onClick={() => run('save', async () => {
            const response = await apiRequest(endpoint, { method: 'PUT', body: payload, timeoutMs: 8000 });
            hydrate(response.data);
            showServerNotification(response);
          })}>Save {shortName} settings</Button>
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
