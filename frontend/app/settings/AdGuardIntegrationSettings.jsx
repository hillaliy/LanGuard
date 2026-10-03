import { Badge, Box, Button, Group, Image, NumberInput, PasswordInput, SimpleGrid, Stack, Switch, Text, TextInput } from '@mantine/core';
import { IconRefresh, IconSend } from '@tabler/icons-react';
import { formatDate } from '../utils/date';

export default function AdGuardIntegrationSettings({ controller }) {
  const {
    adguardConfigured, adguardEnabled, adguardLastError, adguardLastSyncAt, adguardPassword,
    adguardRetentionDays, adguardSyncInterval, adguardUrl, adguardUsername, setAdguardEnabled,
    setAdguardPassword, setAdguardRetentionDays, setAdguardSyncInterval, setAdguardUrl,
    setAdguardUsername, setPiholeEnabled, syncAdguardNow, syncingAdguard,
    testAdguardConnection, testingAdguard, timeZone,
  } = controller;

  return (
    <Stack className="settings-subsection" gap="sm">
      <Group justify="space-between" align="flex-start">
        <Box>
          <Group gap="sm">
            <Image src="/integrations/adguard-home.svg" alt="" aria-hidden="true" w={24} h={24} fit="contain" />
            <Text fw={700}>AdGuard Home</Text>
            <Switch label="Enabled" checked={adguardEnabled} onChange={(event) => {
              const enabled = event.currentTarget.checked;
              setAdguardEnabled(enabled);
              if (enabled) setPiholeEnabled(false);
            }} />
          </Group>
          <Text size="sm" c="dimmed" mt={4}>
            Sync aggregated DNS destinations to device pages. LanGuard stores domain counters, not raw DNS responses.
          </Text>
        </Box>
        <Badge color={adguardConfigured && adguardEnabled ? 'teal' : 'gray'} variant="light">
          {adguardConfigured ? 'Configured' : 'Not configured'}
        </Badge>
      </Group>
      <SimpleGrid className="adguard-connection-fields" cols={{ base: 1, md: 3 }}>
        <TextInput label="AdGuard Home URL" placeholder="http://192.168.1.2:3000" value={adguardUrl}
          onChange={(event) => setAdguardUrl(event.currentTarget.value)} disabled={!adguardEnabled} />
        <TextInput label="Username" placeholder="admin" value={adguardUsername}
          onChange={(event) => setAdguardUsername(event.currentTarget.value)} disabled={!adguardEnabled} />
        <PasswordInput label="Password" placeholder={adguardConfigured ? 'Saved password' : 'Password'}
          value={adguardPassword} onChange={(event) => setAdguardPassword(event.currentTarget.value)} disabled={!adguardEnabled} />
      </SimpleGrid>
      {adguardConfigured && <Text size="xs" c="dimmed">Leave the password blank to keep the saved password.</Text>}
      <Group className="adguard-sync-controls" justify="space-between" align="flex-end" wrap="wrap">
        <Group className="adguard-sync-fields" align="flex-end" wrap="wrap">
          <NumberInput w={170} label="Sync interval" value={adguardSyncInterval}
            onChange={(value) => setAdguardSyncInterval(Number(value) || 5)} min={1} max={1440}
            suffix=" min" disabled={!adguardEnabled} />
          <NumberInput w={170} label="Activity retention" value={adguardRetentionDays}
            onChange={(value) => setAdguardRetentionDays(Number(value) || 90)} min={1} max={3650}
            suffix=" days" disabled={!adguardEnabled} />
          <Box className="adguard-sync-status" pb={6}>
            <Text size="xs" c="dimmed">
              {adguardLastSyncAt ? `Last sync: ${formatDate(adguardLastSyncAt, timeZone)}` : 'Not synced yet'}
            </Text>
            {adguardLastError && <Text size="xs" c="red" maw={420} className="wrap-text">Last error: {adguardLastError}</Text>}
          </Box>
        </Group>
        <Group className="adguard-sync-actions" gap="sm">
          <Button variant="default" leftSection={<IconSend size={18} />} onClick={testAdguardConnection}
            loading={testingAdguard} disabled={!adguardEnabled || !adguardUrl.trim() || syncingAdguard}>Test connection</Button>
          <Button variant="light" leftSection={<IconRefresh size={18} />} onClick={syncAdguardNow}
            loading={syncingAdguard} disabled={!adguardEnabled || !adguardConfigured || testingAdguard}>Sync now</Button>
        </Group>
      </Group>
    </Stack>
  );
}
