import { Badge, Box, Group, Stack, Tabs, Text, Title } from '@mantine/core';
import { IconServer, IconWorldSearch } from '@tabler/icons-react';
import AdGuardIntegrationSettings from './AdGuardIntegrationSettings';
import DockerIntegrationSettings from './DockerIntegrationSettings';
import HomeBoxIntegrationSettings from './HomeBoxIntegrationSettings';
import PiHoleIntegrationSettings from './PiHoleIntegrationSettings';
import SpeedtestTrackerIntegrationSettings from './SpeedtestTrackerIntegrationSettings';
import TechnitiumIntegrationSettings from './TechnitiumIntegrationSettings';

export default function IntegrationSettings({ controller }) {
  const { integrationCategory, onSaved, setIntegrationCategory, timeZone } = controller;

  return (
    <Tabs.Panel value="integrations" className="settings-category-panel">
      <Stack gap="xl">
        <Group justify="space-between" align="flex-start">
          <Box>
            <Title order={3}>Integrations</Title>
            <Text c="dimmed">Connect external services that extend LanGuard network visibility.</Text>
          </Box>
          <Badge variant="light">6 available</Badge>
        </Group>
        <Tabs
          value={integrationCategory}
          onChange={(value) => setIntegrationCategory(value || 'network-services')}
          variant="pills"
          keepMounted={false}
        >
          <Tabs.List>
            <Tabs.Tab value="network-services" leftSection={<IconWorldSearch size={17} />}>
              Network services
            </Tabs.Tab>
            <Tabs.Tab value="infrastructure" leftSection={<IconServer size={17} />}>
              Infrastructure
            </Tabs.Tab>
          </Tabs.List>
          <Tabs.Panel value="network-services" pt="lg">
            <Stack gap="xl">
              <Text size="sm" c="dimmed">
                Connect services that add DNS, performance, and inventory context to LanGuard.
              </Text>
              <AdGuardIntegrationSettings controller={controller} />
              <PiHoleIntegrationSettings controller={controller} />
              <TechnitiumIntegrationSettings controller={controller} />
              <SpeedtestTrackerIntegrationSettings controller={controller} />
              <HomeBoxIntegrationSettings controller={controller} />
            </Stack>
          </Tabs.Panel>
          <Tabs.Panel value="infrastructure" pt="lg">
            <Stack gap="xl">
              <Text size="sm" c="dimmed">
                Add runtime context from the infrastructure that hosts LanGuard.
              </Text>
              <DockerIntegrationSettings timeZone={timeZone} onChanged={onSaved} />
            </Stack>
          </Tabs.Panel>
        </Tabs>
      </Stack>
    </Tabs.Panel>
  );
}
