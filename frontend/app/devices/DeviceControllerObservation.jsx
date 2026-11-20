import { Anchor, Group, SimpleGrid, Stack, Text, Title } from '@mantine/core';
import { IconAccessPoint, IconExternalLink } from '@tabler/icons-react';
import { formatDate } from '../utils/date';
import { DeviceField } from './DeviceDetailFields';

export default function DeviceControllerObservation({ device, timeZone, provider }) {
  const name = provider === 'routeros' ? 'RouterOS' : provider === 'omada' ? 'Omada' : 'UniFi';
  const observations = device.controller_observations?.filter(item => item.provider === provider) || [];
  if (!observations.length) return null;
  return (
    <section className="device-detail-section">
      <Group gap="xs"><IconAccessPoint size={20} /><Title order={4}>{name} observations</Title></Group>
      <Stack gap="md" mt="md">
        {observations.map(({ external_id, mac, metadata: info, observed_at, synced_at }) => {
          const fields = [
            ['Site', info.site_name || info.site_id], ['Reported name', info.name],
            ['Connection', { WIRED: 'Wired', WIRELESS: 'Wi-Fi' }[info.connection] || info.connection],
            ['SSID', info.ssid], ['Network', info.network], ['VLAN', info.vlan],
            ['Access point or switch', info.uplink], ['Switch port', info.switch_port],
            ['Signal', info.rssi != null ? `${info.rssi} dBm` : null],
            ['Signal strength', info.signal_percent != null ? `${info.signal_percent}%` : null],
            ['Radio', info.radio], ['Channel', info.channel],
            ['Router', info.router], ['Interface', info.interface], ['Bridge', info.bridge],
            ['Reported IP', info.reported_ip], ['DHCP server', info.dhcp_server], ['Lease status', info.lease_status],
            ['ARP state', info.arp_status], ['Presence evidence', info.presence_evidence],
            ['Observed at', formatDate(observed_at, timeZone)], ['Synced at', formatDate(synced_at, timeZone)],
          ];
          return (
            <Stack gap="xs" key={`${mac}-${external_id}`}>
              {observations.length > 1 && <Text size="sm" fw={600}>{mac}</Text>}
              <SimpleGrid cols={{ base: 1, xs: 2, lg: 3 }}>
                {fields.filter(([, value]) => value != null && value !== '').map(([label, value]) =>
                  <DeviceField key={label} label={label} value={value} />)}
              </SimpleGrid>
              {/^https:\/\//.test(info.client_url || '') && (
                <Anchor href={info.client_url} target="_blank" rel="noopener noreferrer" size="sm">
                  <Group gap={4}>Open in {name} <IconExternalLink size={14} /></Group>
                </Anchor>
              )}
            </Stack>
          );
        })}
      </Stack>
    </section>
  );
}
