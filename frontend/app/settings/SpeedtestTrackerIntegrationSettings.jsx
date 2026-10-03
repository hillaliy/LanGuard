import { Badge, Box, Button, Group, Image, PasswordInput, SimpleGrid, Stack, Switch, Text, TextInput } from '@mantine/core';
import { IconSend } from '@tabler/icons-react';

export default function SpeedtestTrackerIntegrationSettings({ controller }) {
  const {
    setSpeedtestTrackerApiToken, setSpeedtestTrackerEnabled, setSpeedtestTrackerUrl,
    speedtestTrackerApiToken, speedtestTrackerConfigured, speedtestTrackerEnabled,
    speedtestTrackerUrl, testSpeedtestTrackerConnection, testingSpeedtestTracker,
  } = controller;

  return (
    <Stack className="settings-subsection" gap="sm">
      <Group justify="space-between" align="flex-start">
        <Box>
          <Group gap="sm">
            <Image src="/integrations/speedtest-tracker.svg" alt="" aria-hidden="true" w={24} h={24} fit="contain" />
            <Text fw={700}>Speedtest Tracker</Text>
            <Switch label="Enabled" checked={speedtestTrackerEnabled}
              onChange={(event) => setSpeedtestTrackerEnabled(event.currentTarget.checked)} />
          </Group>
          <Text size="sm" c="dimmed" mt={4}>Show the latest internet performance result on the dashboard.</Text>
        </Box>
        <Badge color={speedtestTrackerConfigured && speedtestTrackerEnabled ? 'teal' : 'gray'} variant="light">
          {speedtestTrackerConfigured ? 'Configured' : 'Not configured'}
        </Badge>
      </Group>
      <Stack className="speedtest-connection-controls" gap="sm">
        <SimpleGrid className="speedtest-connection-fields" cols={{ base: 1, md: 2 }}>
          <TextInput label="Speedtest Tracker URL" placeholder="http://192.168.1.2:8080" value={speedtestTrackerUrl}
            onChange={(event) => setSpeedtestTrackerUrl(event.currentTarget.value)} disabled={!speedtestTrackerEnabled} />
          <PasswordInput label="API token" placeholder={speedtestTrackerConfigured ? 'Saved API token' : 'API token'}
            value={speedtestTrackerApiToken} onChange={(event) => setSpeedtestTrackerApiToken(event.currentTarget.value)}
            disabled={!speedtestTrackerEnabled} />
        </SimpleGrid>
        {speedtestTrackerConfigured && <Text className="speedtest-connection-hint" size="xs" c="dimmed">Leave the API token blank to keep the saved token.</Text>}
        <Group className="speedtest-connection-actions" justify="flex-end">
          <Button variant="default" leftSection={<IconSend size={18} />} onClick={testSpeedtestTrackerConnection}
            loading={testingSpeedtestTracker} disabled={!speedtestTrackerEnabled || !speedtestTrackerUrl.trim()}>Test connection</Button>
        </Group>
      </Stack>
    </Stack>
  );
}
