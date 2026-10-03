import { Badge, Box, Button, Group, Image, NumberInput, PasswordInput, SimpleGrid, Stack, Switch, Text, TextInput } from '@mantine/core';
import { IconRefresh, IconSend } from '@tabler/icons-react';
import { formatDate } from '../utils/date';

export default function PiHoleIntegrationSettings({ controller }) {
  const {
    piholeConfigured, piholeEnabled, piholeLastError, piholeLastSyncAt, piholePassword,
    piholeRetentionDays, piholeSyncInterval, piholeUrl, setAdguardEnabled, setPiholeEnabled,
    setPiholePassword, setPiholeRetentionDays, setPiholeSyncInterval, setPiholeUrl,
    syncPiholeNow, syncingPihole, testPiholeConnection, testingPihole, timeZone,
  } = controller;

  return (
    <Stack className="settings-subsection" gap="sm">
      <Group justify="space-between" align="flex-start">
        <Box>
          <Group gap="sm">
            <Image src="/integrations/pi-hole.svg" alt="" aria-hidden="true" w={24} h={24} fit="contain" />
            <Text fw={700}>Pi-hole</Text>
            <Switch label="Enabled" checked={piholeEnabled} onChange={(event) => {
              const enabled = event.currentTarget.checked;
              setPiholeEnabled(enabled);
              if (enabled) setAdguardEnabled(false);
            }} />
          </Group>
          <Text size="sm" c="dimmed" mt={4}>
            Sync aggregated DNS activity and discover clients from Pi-hole v6 DHCP leases.
            Only one DNS provider can be active at a time.
          </Text>
        </Box>
        <Badge color={piholeConfigured && piholeEnabled ? 'teal' : 'gray'} variant="light">
          {piholeConfigured ? 'Configured' : 'Not configured'}
        </Badge>
      </Group>
      <SimpleGrid cols={{ base: 1, md: 2 }}>
        <TextInput label="Pi-hole URL" placeholder="http://192.168.1.2" value={piholeUrl}
          onChange={(event) => setPiholeUrl(event.currentTarget.value)} disabled={!piholeEnabled} />
        <PasswordInput label="Application password"
          placeholder={piholeConfigured ? 'Saved application password' : 'Application password'} value={piholePassword}
          onChange={(event) => setPiholePassword(event.currentTarget.value)} disabled={!piholeEnabled} />
      </SimpleGrid>
      {piholeConfigured && <Text size="xs" c="dimmed">Leave the application password blank to keep the saved password.</Text>}
      <Group justify="space-between" align="flex-end" wrap="wrap">
        <Group align="flex-end" wrap="wrap">
          <NumberInput w={170} label="Sync interval" value={piholeSyncInterval}
            onChange={(value) => setPiholeSyncInterval(Number(value) || 5)} min={1} max={1440}
            suffix=" min" disabled={!piholeEnabled} />
          <NumberInput w={170} label="Activity retention" value={piholeRetentionDays}
            onChange={(value) => setPiholeRetentionDays(Number(value) || 90)} min={1} max={3650}
            suffix=" days" disabled={!piholeEnabled} />
          <Box pb={6}>
            <Text size="xs" c="dimmed">
              {piholeLastSyncAt ? `Last sync: ${formatDate(piholeLastSyncAt, timeZone)}` : 'Not synced yet'}
            </Text>
            {piholeLastError && <Text size="xs" c="red" maw={420} className="wrap-text">Last error: {piholeLastError}</Text>}
          </Box>
        </Group>
        <Group gap="sm">
          <Button variant="default" leftSection={<IconSend size={18} />} onClick={testPiholeConnection}
            loading={testingPihole} disabled={!piholeEnabled || !piholeUrl.trim() || syncingPihole}>Test connection</Button>
          <Button variant="light" leftSection={<IconRefresh size={18} />} onClick={syncPiholeNow}
            loading={syncingPihole} disabled={!piholeEnabled || !piholeConfigured || testingPihole}>Sync now</Button>
        </Group>
      </Group>
    </Stack>
  );
}
