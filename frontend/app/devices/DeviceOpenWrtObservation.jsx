import { Anchor, Group, SimpleGrid, Stack, Text, Title } from '@mantine/core';
import { IconExternalLink, IconRouter } from '@tabler/icons-react';

import { formatDate } from '../utils/date';
import { DeviceField } from './DeviceDetailFields';

export default function DeviceOpenWrtObservation({ device, timeZone }) {
  const interfaces = device.interfaces?.length ? device.interfaces : [device];
  const observations = interfaces.filter((item) => item.openwrt_data?.observed_at);
  if (!observations.length) return null;
  return (
    <section className="device-detail-section">
      <Group gap="xs"><IconRouter size={20} /><Title order={4}>OpenWrt observations</Title></Group>
      <Stack gap="md" mt="md">
        {observations.map((item) => {
          const data = item.openwrt_data;
          const fields = [
            ['Reported name', data.name !== device.name ? data.name : null],
            ['IPv4 lease', data.lease_ip], ['Lease interface', data.lease_interface],
            ['Host hint addresses', data.hint_addresses?.join(', ')],
            ['Observed at', formatDate(data.observed_at, timeZone)],
          ].filter(([, value]) => value);
          return (
            <Stack key={item.id} gap="xs">
              {interfaces.length > 1 && <Text size="sm" fw={600}>{item.mac}</Text>}
              <SimpleGrid cols={{ base: 2, lg: 3 }}>
                {fields.map(([label, value]) => <DeviceField key={label} label={label} value={value} />)}
              </SimpleGrid>
              {data.wireless?.map((association) => (
                <SimpleGrid key={association.interface} cols={{ base: 2, lg: 3 }}>
                  <DeviceField label="Wi-Fi interface" value={association.interface} />
                  <DeviceField label="Radio" value={association.radio} />
                  {association.ssid && <DeviceField label="SSID" value={association.ssid} />}
                  {association.networks?.length > 0 && <DeviceField label="Networks" value={association.networks.join(', ')} />}
                  {association.channel && <DeviceField label="Channel" value={association.channel} />}
                  {association.frequency && <DeviceField label="Frequency" value={`${association.frequency} MHz`} />}
                  {association.rssi != null && <DeviceField label="Signal" value={`${association.rssi} dBm`} />}
                </SimpleGrid>
              ))}
              {/^https?:\/\//.test(data.router_url || '') && (
                <Anchor href={data.router_url} target="_blank" rel="noopener noreferrer" size="sm">
                  <Group gap={4}>Open LuCI <IconExternalLink size={14} /></Group>
                </Anchor>
              )}
            </Stack>
          );
        })}
      </Stack>
    </section>
  );
}
