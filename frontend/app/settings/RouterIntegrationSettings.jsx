import {
  Alert, Anchor, Badge, Box, Button, Group, NumberInput, PasswordInput,
  SimpleGrid, Stack, Switch, Text, TextInput, Tooltip,
} from '@mantine/core';
import { IconExternalLink, IconPlugConnected, IconRefresh, IconRouter } from '@tabler/icons-react';

import { formatDate } from '../utils/date';

export default function RouterIntegrationSettings({ controller: c, provider, timeZone }) {
  const s = c.form;
  const openwrt = provider === 'openwrt';
  const name = openwrt ? 'OpenWrt / LuCI' : 'ASUSWRT';
  const counts = openwrt ? [
    `${s.summary.leases ?? 0} leases`, `${s.summary.host_hints ?? 0} host hints`,
    `${s.summary.wireless_clients ?? 0} Wi-Fi clients`,
  ] : [`${s.summary.clients_active ?? 0} active clients`, `${s.summary.clients_invalid ?? 0} invalid`];
  return (
    <Stack className="settings-subsection" gap="sm">
      <Group justify="space-between" align="flex-start">
        <Group gap="sm">
          <IconRouter size={24} aria-hidden="true" />
          <Text fw={700}>{name}</Text>
          <Switch label="Enabled" checked={s.enabled}
            onChange={(event) => c.setField('enabled', event.currentTarget.checked)} />
        </Group>
        <Badge color={s.configured ? 'teal' : 'gray'} variant="light">
          {s.configured ? 'Configured' : 'Not configured'}
        </Badge>
      </Group>
      <SimpleGrid cols={{ base: 1, md: 2 }}>
        <TextInput label="Router URL" placeholder={openwrt ? 'https://192.168.1.1' : 'https://192.168.50.1:8443'} value={s.url}
          disabled={!s.enabled} onChange={(event) => c.setField('url', event.currentTarget.value)} />
        <TextInput label="Router username" autoComplete="off" value={s.username}
          disabled={!s.enabled} onChange={(event) => c.setField('username', event.currentTarget.value)} />
        <PasswordInput label="Router password" autoComplete="new-password" value={s.password}
          placeholder={s.configured ? 'Saved password' : ''} disabled={!s.enabled}
          onChange={(event) => c.setField('password', event.currentTarget.value)} />
        <NumberInput label="Sync interval" min={1} max={1440} allowDecimal={false} suffix=" min"
          value={s.syncInterval} disabled={!s.enabled}
          onChange={(value) => c.setField('syncInterval', Number(value) || 5)} />
      </SimpleGrid>
      <Switch label="Verify TLS certificate" checked={s.verifySsl} disabled={!s.enabled}
        onChange={(event) => c.setField('verifySsl', event.currentTarget.checked)} />
      <Switch label={openwrt ? 'Create devices from IPv4 leases' : 'Create devices from router clients'}
        checked={s.createDevices} disabled={!s.enabled}
        onChange={(event) => c.setField('createDevices', event.currentTarget.checked)} />
      {s.authFailed && (
        <Alert color="orange" title="Automatic login paused">
          {openwrt ? 'Check the rpcd credentials and permissions.' : 'Check the router login, CAPTCHA, or lockout before testing or syncing manually.'}
        </Alert>
      )}
      <Group justify="space-between" align="flex-end" wrap="wrap">
        <Box>
          <Text size="xs" c="dimmed">{s.lastSyncAt ? `Last sync: ${formatDate(s.lastSyncAt, timeZone)}` : 'Not synced yet'}</Text>
          {s.lastSyncAt && (
            <Text size="xs" c="dimmed">
              {[...counts, `${s.summary.devices_discovered ?? 0} created`,
                `${s.summary.clients_enriched ?? 0} enriched`, `${s.summary.identity_conflicts ?? 0} conflicts`].join(' · ')}
            </Text>
          )}
          {s.summary.model && <Text size="xs" c="dimmed">{s.summary.model} {s.summary.firmware}</Text>}
          {s.summary.unavailable?.length > 0 && (
            <Text size="xs" c="dimmed" maw={420} className="wrap-text">Unavailable: {s.summary.unavailable.join(', ')}</Text>
          )}
          {s.lastError && <Text size="xs" c="red" maw={420} className="wrap-text">{s.lastError}</Text>}
        </Box>
        <Group gap="sm">
          {c.consoleUrl && (
            <Button component="a" href={c.consoleUrl} target="_blank" rel="noopener noreferrer"
              variant="default" leftSection={<IconExternalLink size={18} />}>Open {openwrt ? 'LuCI' : name}</Button>
          )}
          <Anchor href={`https://hillaliy.github.io/LanGuard/docs/integrations#${provider}`} target="_blank" rel="noopener noreferrer">
            <Group gap={4}>{name} setup <IconExternalLink size={14} /></Group>
          </Anchor>
          <Button variant="default" leftSection={<IconPlugConnected size={18} />}
            loading={c.testing} disabled={!s.enabled || !c.testReady || c.syncing}
            onClick={c.testConnection}>Test connection</Button>
          <Tooltip label="Save changes before syncing" disabled={c.syncReady}>
            <Box>
              <Button variant="light" leftSection={<IconRefresh size={18} />}
                loading={c.syncing} disabled={!c.syncReady || c.testing}
                onClick={c.syncNow}>Sync now</Button>
            </Box>
          </Tooltip>
        </Group>
      </Group>
    </Stack>
  );
}
