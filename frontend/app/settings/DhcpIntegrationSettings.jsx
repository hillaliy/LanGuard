import { Badge, Box, Button, Group, NumberInput, Select, SimpleGrid, Stack, Switch, Text, TextInput, Tooltip } from '@mantine/core';
import { IconAddressBook, IconFileCheck, IconRefresh } from '@tabler/icons-react';

import { formatDate } from '../utils/date';

export default function DhcpIntegrationSettings({ controller: c }) {
  return (
    <Stack className="settings-subsection" gap="sm">
      <Group justify="space-between" align="flex-start">
        <Group gap="sm">
          <IconAddressBook size={24} aria-hidden="true" />
          <Text fw={700}>DHCP lease source</Text>
          <Switch label="Enabled" checked={c.dhcpEnabled}
            onChange={(event) => c.setDhcpEnabled(event.currentTarget.checked)} />
        </Group>
        <Badge color={c.dhcpEnabled && c.dhcpLeaseFile.trim() ? 'teal' : 'gray'} variant="light">
          {c.dhcpLeaseFile.trim() ? 'Configured' : 'Not configured'}
        </Badge>
      </Group>
      <SimpleGrid cols={{ base: 1, md: 2 }}>
        <Select label="Lease format" value={c.dhcpFormat} disabled={!c.dhcpEnabled}
          data={[{ value: 'dnsmasq', label: 'dnsmasq' }, { value: 'kea', label: 'Kea DHCPv4 (CSV)' }, { value: 'isc', label: 'ISC DHCPv4' }]}
          onChange={(value) => c.setDhcpFormat(value || 'dnsmasq')} />
        <TextInput label="Lease file" placeholder="dnsmasq.leases" value={c.dhcpLeaseFile}
          disabled={!c.dhcpEnabled}
          onChange={(event) => c.setDhcpLeaseFile(event.currentTarget.value)} />
      </SimpleGrid>
      <Switch label="Create devices from leases" checked={c.dhcpCreateDevices}
        disabled={!c.dhcpEnabled}
        onChange={(event) => c.setDhcpCreateDevices(event.currentTarget.checked)} />
      <Group justify="space-between" align="flex-end" wrap="wrap">
        <Group align="flex-end" wrap="wrap">
          <NumberInput label="Sync interval" w={170} min={1} max={1440} allowDecimal={false}
            suffix=" min" value={c.dhcpSyncInterval} disabled={!c.dhcpEnabled}
            onChange={(value) => c.setDhcpSyncInterval(Number(value) || 5)} />
          <Box pb={6}>
            <Text size="xs" c="dimmed">
              {c.dhcpLastSyncAt ? `Last sync: ${formatDate(c.dhcpLastSyncAt, c.timeZone)}` : 'Not synced yet'}
            </Text>
            {c.dhcpLastSyncAt && (
              <Text size="xs" c="dimmed">
                {c.dhcpLastSyncSummary.active_leases ?? 0} active leases
                {' · '}{c.dhcpLastSyncSummary.devices_discovered ?? 0} created
                {' · '}{c.dhcpLastSyncSummary.devices_updated ?? 0} updated
                {' · '}{c.dhcpLastSyncSummary.identity_conflicts ?? 0} conflicts
              </Text>
            )}
            {c.dhcpLastError && <Text size="xs" c="red" maw={420} className="wrap-text">{c.dhcpLastError}</Text>}
          </Box>
        </Group>
        <Group gap="sm">
          <Button variant="default" leftSection={<IconFileCheck size={18} />}
            loading={c.testingDhcp} disabled={!c.dhcpEnabled || !c.dhcpLeaseFile.trim() || c.syncingDhcp}
            onClick={c.testDhcpSource}>Test source</Button>
          <Tooltip label="Save source changes before syncing" disabled={c.dhcpSyncReady}>
            <Box>
              <Button variant="light" leftSection={<IconRefresh size={18} />}
                loading={c.syncingDhcp} disabled={!c.dhcpSyncReady || c.testingDhcp}
                onClick={c.syncDhcpNow}>Sync now</Button>
            </Box>
          </Tooltip>
        </Group>
      </Group>
    </Stack>
  );
}
