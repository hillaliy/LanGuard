import { ActionIcon, Badge, Group, Image, Select, Stack, Switch, Text, TextInput, Tooltip } from '@mantine/core';
import { IconSend } from '@tabler/icons-react';

export default function NtfyNotificationSettings({ controller }) {
  const {
    ntfyConfigured, ntfyEnabled, ntfyPriority, ntfyServerUrl, ntfyTopic,
    setNtfyEnabled, setNtfyPriority, setNtfyServerUrl, setNtfyTopic,
    testNotificationChannel, testingChannel,
  } = controller;

  return (
    <Stack className="settings-subsection" gap="sm">
      <Group justify="space-between">
        <Group gap="sm">
          <Group gap={6}><Image src="/integrations/ntfy.svg" alt="" w={18} h={18} /><Text fw={700}>ntfy</Text></Group>
          <Switch label="Enabled" checked={ntfyEnabled}
            onChange={(event) => setNtfyEnabled(event.currentTarget.checked)} />
        </Group>
        <Badge color={ntfyConfigured && ntfyEnabled ? 'teal' : 'gray'} variant="light">
          {ntfyConfigured ? 'Configured' : 'Not configured'}
        </Badge>
      </Group>
      <Group align="flex-end" wrap="wrap">
        <TextInput style={{ flex: '1 1 320px' }} label="ntfy server URL"
          description="Use ntfy.sh or the root URL of your self-hosted ntfy server."
          placeholder="https://ntfy.sh" value={ntfyServerUrl}
          onChange={(event) => setNtfyServerUrl(event.currentTarget.value)} />
        <TextInput style={{ flex: '1 1 220px' }} label="Topic" placeholder="languard-alerts"
          value={ntfyTopic} onChange={(event) => setNtfyTopic(event.currentTarget.value)} />
        <Select
          style={{ flex: '0 1 180px' }}
          label="Priority"
          value={ntfyPriority}
          onChange={(value) => setNtfyPriority(value || '3')}
          data={[
            { value: '1', label: 'Min' }, { value: '2', label: 'Low' },
            { value: '3', label: 'Default' }, { value: '4', label: 'High' },
            { value: '5', label: 'Max' },
          ]}
        />
        <Tooltip label="Send test notification">
          <ActionIcon
            size={36}
            variant="light"
            aria-label="Send ntfy test notification"
            loading={testingChannel === 'ntfy'}
            disabled={!ntfyServerUrl.trim() || !ntfyTopic.trim()
              || Boolean(testingChannel && testingChannel !== 'ntfy')}
            onClick={() => testNotificationChannel('ntfy')}
          >
            <IconSend size={18} />
          </ActionIcon>
        </Tooltip>
      </Group>
    </Stack>
  );
}
