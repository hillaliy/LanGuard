import { Anchor, Group, SimpleGrid, Stack, Text, Title } from '@mantine/core';
import { IconExternalLink, IconRouter } from '@tabler/icons-react';

import { formatDate } from '../utils/date';
import { DeviceField } from './DeviceDetailFields';

export default function DeviceAsuswrtObservation({ device, timeZone }) {
  const interfaces = device.interfaces?.length ? device.interfaces : [device];
  const observations = interfaces.filter((item) => item.asuswrt_data?.observed_at);
  if (!observations.length) return null;
  return (
    <section className="device-detail-section">
      <Group gap="xs"><IconRouter size={20} /><Title order={4}>ASUSWRT observation</Title></Group>
      <Stack gap="md" mt="md">
        {observations.map((item) => {
          const data = item.asuswrt_data;
          const fields = [
            ['Reported name', data.name && data.name !== device.name ? data.name : null],
            ['Connection', data.connection], ['SSID', data.ssid],
            ['Signal', data.rssi != null ? `${data.rssi} dBm` : null],
            ['Router model', data.model], ['Observed at', formatDate(data.observed_at, timeZone)],
          ].filter(([, value]) => value);
          return (
            <Stack key={item.id} gap="xs">
              {observations.length > 1 && <Text size="sm" fw={600}>{item.mac}</Text>}
              <SimpleGrid cols={{ base: 1, sm: 2, lg: 3 }}>
                {fields.map(([label, value]) => <DeviceField key={label} label={label} value={value} />)}
              </SimpleGrid>
              {/^https?:\/\//.test(data.router_url || '') && (
                <Anchor href={data.router_url} target="_blank" rel="noopener noreferrer" size="sm">
                  <Group gap={4}>Open ASUSWRT <IconExternalLink size={14} /></Group>
                </Anchor>
              )}
            </Stack>
          );
        })}
      </Stack>
    </section>
  );
}
