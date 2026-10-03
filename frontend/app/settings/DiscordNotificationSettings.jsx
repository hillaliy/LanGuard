import { ActionIcon, Badge, Group, PasswordInput, Stack, Switch, Text, Tooltip } from '@mantine/core';
import { IconBrandDiscord, IconSend } from '@tabler/icons-react';

export default function DiscordNotificationSettings({ controller }) {
  const {
    discordConfigured, discordEnabled, discordWebhook, setDiscordEnabled,
    setDiscordWebhook, testNotificationChannel, testingChannel,
  } = controller;

  return (
    <Stack className="settings-subsection" gap="sm">
      <Group justify="space-between">
        <Group gap="sm">
          <Group gap={6}><IconBrandDiscord size={18} /><Text fw={700}>Discord</Text></Group>
          <Switch label="Enabled" checked={discordEnabled}
            onChange={(event) => setDiscordEnabled(event.currentTarget.checked)} />
        </Group>
        <Badge color={discordConfigured && discordEnabled ? 'teal' : 'gray'} variant="light">
          {discordConfigured ? 'Configured' : 'Not configured'}
        </Badge>
      </Group>
      <Group align="flex-end" wrap="nowrap">
        <PasswordInput
          style={{ flex: 1 }}
          label="Discord webhook"
          description={discordConfigured
            ? 'Leave blank to keep the saved webhook.'
            : 'Paste a Discord channel webhook URL to enable Discord messages.'}
          placeholder={discordConfigured ? 'Saved webhook' : 'https://discord.com/api/webhooks/...'}
          value={discordWebhook}
          onChange={(event) => setDiscordWebhook(event.currentTarget.value)}
          autoComplete="new-password"
        />
        <Tooltip label="Send test notification">
          <ActionIcon
            size={36}
            variant="light"
            aria-label="Send Discord test notification"
            loading={testingChannel === 'discord'}
            disabled={(!discordWebhook.trim() && !discordConfigured)
              || Boolean(testingChannel && testingChannel !== 'discord')}
            onClick={() => testNotificationChannel('discord')}
          >
            <IconSend size={18} />
          </ActionIcon>
        </Tooltip>
      </Group>
    </Stack>
  );
}
