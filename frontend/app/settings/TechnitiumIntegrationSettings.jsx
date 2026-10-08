import {
  Alert, Badge, Box, Button, Group, NumberInput, PasswordInput, SimpleGrid,
  Stack, Switch, Text, TextInput,
} from '@mantine/core';
import { IconDatabase, IconExternalLink, IconRefresh, IconSend } from '@tabler/icons-react';
import { formatDate } from '../utils/date';

export default function TechnitiumIntegrationSettings({ controller }) {
  const {
    setAdguardEnabled, setPiholeEnabled, setTechnitiumApiToken,
    setTechnitiumDhcpCreateDevices, setTechnitiumDhcpEnabled,
    setTechnitiumEnabled, setTechnitiumRetentionDays, setTechnitiumSyncInterval,
    setTechnitiumUrl, syncTechnitiumNow, syncingTechnitium, technitiumApiToken,
    technitiumConfigured, technitiumDhcpCreateDevices, technitiumDhcpEnabled,
    technitiumEnabled, technitiumLastError, technitiumLastSyncAt,
    technitiumLastSyncSummary, technitiumRetentionDays, technitiumSyncInterval,
    technitiumUrl, testTechnitiumConnection, testingTechnitium, timeZone,
  } = controller;

  return (
    <Stack className="settings-subsection" gap="sm">
      <Group justify="space-between" align="flex-start">
        <Box>
          <Group gap="sm">
            <IconDatabase size={24} aria-hidden="true" />
            <Text fw={700}>Technitium DNS Server</Text>
            <Switch label="Enabled" checked={technitiumEnabled} onChange={(event) => {
              const enabled = event.currentTarget.checked;
              setTechnitiumEnabled(enabled);
              if (enabled) {
                setAdguardEnabled(false);
                setPiholeEnabled(false);
              }
            }} />
          </Group>
          <Text size="sm" c="dimmed" mt={4}>
            Sync aggregated activity from an installed Query Logs app. Technitium v15 or later is required.
          </Text>
        </Box>
        <Badge color={technitiumConfigured && technitiumEnabled ? 'teal' : 'gray'} variant="light">
          {technitiumConfigured ? 'Configured' : 'Not configured'}
        </Badge>
      </Group>

      <SimpleGrid cols={{ base: 1, md: 2 }}>
        <TextInput label="Technitium URL" placeholder="https://192.168.1.2:5380"
          value={technitiumUrl} onChange={(event) => setTechnitiumUrl(event.currentTarget.value)}
          disabled={!technitiumEnabled} />
        <PasswordInput label="API token"
          placeholder={technitiumConfigured ? 'Saved API token' : 'API token'}
          value={technitiumApiToken}
          onChange={(event) => setTechnitiumApiToken(event.currentTarget.value)}
          disabled={!technitiumEnabled} />
      </SimpleGrid>
      {technitiumConfigured && (
        <Text size="xs" c="dimmed">Leave the API token blank to keep the saved token.</Text>
      )}

      <Group align="flex-start" wrap="wrap">
        <Switch label="Sync DHCP leases" description="Enrich existing devices with lease IP and hostname data."
          checked={technitiumDhcpEnabled} disabled={!technitiumEnabled}
          onChange={(event) => {
            const enabled = event.currentTarget.checked;
            setTechnitiumDhcpEnabled(enabled);
            if (!enabled) setTechnitiumDhcpCreateDevices(false);
          }} />
        <Switch label="Create devices from leases"
          description="Create Unknown devices for valid leases that are not already in LanGuard."
          checked={technitiumDhcpCreateDevices}
          disabled={!technitiumEnabled || !technitiumDhcpEnabled}
          onChange={(event) => setTechnitiumDhcpCreateDevices(event.currentTarget.checked)} />
      </Group>

      {technitiumDhcpCreateDevices && (
        <Alert color="yellow" variant="light">
          DHCP-only devices are added as Unknown and are not marked online by the integration.
        </Alert>
      )}

      <Group justify="space-between" align="flex-end" wrap="wrap">
        <Group align="flex-end" wrap="wrap">
          <NumberInput w={170} label="Sync interval" value={technitiumSyncInterval}
            onChange={(value) => setTechnitiumSyncInterval(Number(value) || 5)} min={1} max={1440}
            suffix=" min" disabled={!technitiumEnabled} />
          <NumberInput w={170} label="Activity retention" value={technitiumRetentionDays}
            onChange={(value) => setTechnitiumRetentionDays(Number(value) || 90)} min={1} max={3650}
            suffix=" days" disabled={!technitiumEnabled} />
          <Box pb={6}>
            <Text size="xs" c="dimmed">
              {technitiumLastSyncAt ? `Last sync: ${formatDate(technitiumLastSyncAt, timeZone)}` : 'Not synced yet'}
            </Text>
            {technitiumLastSyncAt && (
              <Text size="xs" c="dimmed">
                {technitiumLastSyncSummary.matched || 0} matched, {technitiumLastSyncSummary.unmatched || 0} unmatched
                {technitiumDhcpEnabled ? `, ${technitiumLastSyncSummary.leases || 0} leases` : ''}
              </Text>
            )}
            {technitiumLastError && <Text size="xs" c="red" maw={420} className="wrap-text">Last error: {technitiumLastError}</Text>}
          </Box>
        </Group>
        <Group gap="sm">
          {technitiumConfigured && technitiumUrl && (
            <Button component="a" href={technitiumUrl} target="_blank" rel="noreferrer"
              variant="subtle" leftSection={<IconExternalLink size={18} />}>
              Open console
            </Button>
          )}
          <Button variant="default" leftSection={<IconSend size={18} />}
            onClick={testTechnitiumConnection} loading={testingTechnitium}
            disabled={!technitiumEnabled || !technitiumUrl.trim() || syncingTechnitium}>
            Test connection
          </Button>
          <Button variant="light" leftSection={<IconRefresh size={18} />}
            onClick={syncTechnitiumNow} loading={syncingTechnitium}
            disabled={!technitiumEnabled || !technitiumConfigured || testingTechnitium}>
            Sync now
          </Button>
        </Group>
      </Group>
    </Stack>
  );
}
