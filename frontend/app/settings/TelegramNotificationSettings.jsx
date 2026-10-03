import { ActionIcon, Badge, Group, PasswordInput, Stack, Switch, Text, TextInput, Tooltip } from '@mantine/core';
import { IconBrandTelegram, IconSend } from '@tabler/icons-react';

export default function TelegramNotificationSettings({ controller }) {
  const {
    setTelegramApiUrl, setTelegramEnabled, setTelegramToken, setTelegramUserId,
    telegramApiUrl, telegramConfigured, telegramEnabled, telegramToken, telegramUserId,
    testNotificationChannel, testingChannel,
  } = controller;

  return (
    <Stack className="settings-subsection" gap="sm">
      <Group justify="space-between">
        <Group gap="sm">
          <Group gap={6}><IconBrandTelegram size={18} /><Text fw={700}>Telegram</Text></Group>
          <Switch label="Enabled" checked={telegramEnabled}
            onChange={(event) => setTelegramEnabled(event.currentTarget.checked)} />
        </Group>
        <Badge color={telegramConfigured && telegramEnabled ? 'teal' : 'gray'} variant="light">
          {telegramConfigured ? 'Configured' : 'Not configured'}
        </Badge>
      </Group>
      <TextInput
        label="Telegram API base URL"
        description="Change only when using a Telegram-compatible relay or self-hosted Bot API server."
        placeholder="https://api.telegram.org"
        value={telegramApiUrl}
        onChange={(event) => setTelegramApiUrl(event.currentTarget.value)}
      />
      <Group align="flex-end" wrap="nowrap">
        <PasswordInput
          style={{ flex: 1 }}
          label="Telegram bot token"
          placeholder={telegramConfigured ? 'Saved token' : '123456:bot-token'}
          description={telegramConfigured ? 'Leave blank to keep the saved token.' : undefined}
          value={telegramToken}
          onChange={(event) => setTelegramToken(event.currentTarget.value)}
          autoComplete="new-password"
        />
        <TextInput style={{ flex: 1 }} label="Telegram user ID" placeholder="123456789"
          value={telegramUserId} onChange={(event) => setTelegramUserId(event.currentTarget.value)} />
        <Tooltip label="Send test notification">
          <ActionIcon
            size={36}
            variant="light"
            aria-label="Send Telegram test notification"
            loading={testingChannel === 'telegram'}
            disabled={!telegramApiUrl.trim() || (!telegramToken.trim() && !telegramConfigured)
              || !telegramUserId.trim() || Boolean(testingChannel && testingChannel !== 'telegram')}
            onClick={() => testNotificationChannel('telegram')}
          >
            <IconSend size={18} />
          </ActionIcon>
        </Tooltip>
      </Group>
    </Stack>
  );
}
