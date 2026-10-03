import { Badge, Button, Group, Image, PasswordInput, SimpleGrid, Stack, Switch, Text, TextInput } from '@mantine/core';
import { IconSend } from '@tabler/icons-react';

export default function HomeBoxIntegrationSettings({ controller }) {
  const {
    homeboxConfigured, homeboxEnabled, homeboxToken, homeboxUrl,
    setHomeboxEnabled, setHomeboxToken, setHomeboxUrl, testHomeboxConnection, testingHomebox,
  } = controller;

  return (
    <Stack className="settings-subsection" gap="sm">
      <Group justify="space-between">
        <Group>
          <Image src="/integrations/homebox.svg" alt="" aria-hidden="true" w={24} h={24} fit="contain" />
          <Text fw={700}>HomeBox</Text>
          <Switch label="Enabled" checked={homeboxEnabled}
            onChange={(event) => setHomeboxEnabled(event.currentTarget.checked)} />
        </Group>
        <Badge color={homeboxConfigured && homeboxEnabled ? 'teal' : 'gray'} variant="light">
          {homeboxConfigured ? 'Configured' : 'Not configured'}
        </Badge>
      </Group>
      <SimpleGrid cols={{ base: 1, md: 2 }}>
        <TextInput label="HomeBox URL" value={homeboxUrl} disabled={!homeboxEnabled}
          onChange={(event) => setHomeboxUrl(event.currentTarget.value)} />
        <PasswordInput label="API key" value={homeboxToken} disabled={!homeboxEnabled}
          placeholder={homeboxConfigured ? 'Saved API key' : 'API key'}
          onChange={(event) => setHomeboxToken(event.currentTarget.value)} />
      </SimpleGrid>
      <Group justify="flex-end">
        <Button variant="default" leftSection={<IconSend size={18} />}
          disabled={!homeboxEnabled || !homeboxUrl.trim()} loading={testingHomebox}
          onClick={testHomeboxConnection}>Test connection</Button>
      </Group>
    </Stack>
  );
}
