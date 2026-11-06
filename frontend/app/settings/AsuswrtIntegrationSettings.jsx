import {
  Alert, Anchor, Badge, Box, Button, Group, NumberInput, PasswordInput,
  SimpleGrid, Stack, Switch, Text, TextInput, Tooltip,
} from '@mantine/core';
import { IconExternalLink, IconPlugConnected, IconRefresh, IconRouter } from '@tabler/icons-react';

import { formatDate } from '../utils/date';

export default function AsuswrtIntegrationSettings({ controller: c }) {
  const s = c.asuswrt;
  return (
    <Stack className="settings-subsection" gap="sm">
      <Group justify="space-between" align="flex-start">
        <Group gap="sm">
          <IconRouter size={24} aria-hidden="true" />
          <Text fw={700}>ASUSWRT</Text>
          <Switch label="Enabled" checked={s.enabled}
            onChange={(event) => c.setAsuswrtField('enabled', event.currentTarget.checked)} />
        </Group>
        <Badge color={s.configured ? 'teal' : 'gray'} variant="light">
          {s.configured ? 'Configured' : 'Not configured'}
        </Badge>
      </Group>
      <SimpleGrid cols={{ base: 1, md: 2 }}>
        <TextInput label="Router URL" placeholder="https://192.168.50.1:8443" value={s.url}
          disabled={!s.enabled} onChange={(event) => c.setAsuswrtField('url', event.currentTarget.value)} />
        <TextInput label="Router username" autoComplete="off" value={s.username}
          disabled={!s.enabled} onChange={(event) => c.setAsuswrtField('username', event.currentTarget.value)} />
        <PasswordInput label="Router password" autoComplete="new-password" value={s.password}
          placeholder={s.configured ? 'Saved password' : ''} disabled={!s.enabled}
          onChange={(event) => c.setAsuswrtField('password', event.currentTarget.value)} />
        <NumberInput label="Sync interval" min={1} max={1440} allowDecimal={false} suffix=" min"
          value={s.syncInterval} disabled={!s.enabled}
          onChange={(value) => c.setAsuswrtField('syncInterval', Number(value) || 5)} />
      </SimpleGrid>
      <Switch label="Verify TLS certificate" checked={s.verifySsl} disabled={!s.enabled}
        onChange={(event) => c.setAsuswrtField('verifySsl', event.currentTarget.checked)} />
      <Switch label="Create devices from router clients" checked={s.createDevices} disabled={!s.enabled}
        onChange={(event) => c.setAsuswrtField('createDevices', event.currentTarget.checked)} />
      {s.authFailed && (
        <Alert color="orange" title="Automatic login paused">
          Check the router login, CAPTCHA, or lockout before testing or syncing manually.
        </Alert>
      )}
      <Group justify="space-between" align="flex-end" wrap="wrap">
        <Box>
          <Text size="xs" c="dimmed">{s.lastSyncAt ? `Last sync: ${formatDate(s.lastSyncAt, c.timeZone)}` : 'Not synced yet'}</Text>
          {s.lastSyncAt && (
            <Text size="xs" c="dimmed">
              {s.summary.clients_active ?? 0} active clients
              {' · '}{s.summary.devices_discovered ?? 0} created
              {' · '}{s.summary.clients_enriched ?? 0} enriched
              {' · '}{s.summary.clients_invalid ?? 0} invalid
              {' · '}{s.summary.identity_conflicts ?? 0} conflicts
            </Text>
          )}
          {s.summary.model && <Text size="xs" c="dimmed">{s.summary.model} {s.summary.firmware}</Text>}
          {s.lastError && <Text size="xs" c="red" maw={420} className="wrap-text">{s.lastError}</Text>}
        </Box>
        <Group gap="sm">
          {c.asuswrtConsoleUrl && (
            <Button component="a" href={c.asuswrtConsoleUrl} target="_blank" rel="noopener noreferrer"
              variant="default" leftSection={<IconExternalLink size={18} />}>Open ASUSWRT</Button>
          )}
          <Anchor href="https://hillaliy.github.io/LanGuard/docs/integrations#asuswrt" target="_blank" rel="noopener noreferrer">
            <Group gap={4}>ASUSWRT setup <IconExternalLink size={14} /></Group>
          </Anchor>
          <Button variant="default" leftSection={<IconPlugConnected size={18} />}
            loading={c.testingAsuswrt} disabled={!s.enabled || !c.asuswrtTestReady || c.syncingAsuswrt}
            onClick={c.testAsuswrtConnection}>Test connection</Button>
          <Tooltip label="Save changes before syncing" disabled={c.asuswrtSyncReady}>
            <Box>
              <Button variant="light" leftSection={<IconRefresh size={18} />}
                loading={c.syncingAsuswrt} disabled={!c.asuswrtSyncReady || c.testingAsuswrt}
                onClick={c.syncAsuswrtNow}>Sync now</Button>
            </Box>
          </Tooltip>
        </Group>
      </Group>
    </Stack>
  );
}
