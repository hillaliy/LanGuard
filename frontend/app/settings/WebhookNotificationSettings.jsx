import { ActionIcon, Badge, Checkbox, Group, PasswordInput, Stack, Switch, Text, TextInput, Tooltip } from '@mantine/core';
import { IconSend, IconWebhook } from '@tabler/icons-react';

export default function WebhookNotificationSettings({ controller }) {
  const {
    clearWebhookSecret, setClearWebhookSecret, setWebhookEnabled, setWebhookSecret,
    setWebhookUrl, testNotificationChannel, testingChannel, webhookConfigured,
    webhookEnabled, webhookSecret, webhookSignatureConfigured, webhookUrl,
  } = controller;

  return (
    <Stack className="settings-subsection" gap="sm">
      <Group justify="space-between">
        <Group gap="sm">
          <Group gap={6}><IconWebhook size={18} /><Text fw={700}>Automation webhook</Text></Group>
          <Switch label="Enabled" checked={webhookEnabled}
            onChange={(event) => setWebhookEnabled(event.currentTarget.checked)} />
        </Group>
        <Group gap="xs">
          {webhookConfigured && (
            <Badge color={webhookSignatureConfigured ? 'teal' : 'yellow'} variant="light">
              {webhookSignatureConfigured ? 'Signed' : 'Unsigned'}
            </Badge>
          )}
          <Badge color={webhookConfigured && webhookEnabled ? 'teal' : 'gray'} variant="light">
            {webhookConfigured ? 'Configured' : 'Not configured'}
          </Badge>
        </Group>
      </Group>
      <Group align="flex-end" wrap="wrap">
        <TextInput
          style={{ flex: '1 1 360px' }}
          label="Webhook URL"
          description="Send structured network events to n8n, Home Assistant, or another automation service."
          placeholder="https://automation.example/webhook/languard"
          value={webhookUrl}
          onChange={(event) => setWebhookUrl(event.currentTarget.value)}
        />
        <PasswordInput
          style={{ flex: '1 1 260px' }}
          label="Signing secret"
          description={webhookSignatureConfigured
            ? 'Leave blank to keep the saved secret.'
            : 'Optional HMAC secret used to verify LanGuard deliveries.'}
          placeholder={webhookSignatureConfigured ? 'Saved secret' : 'Shared secret'}
          value={webhookSecret}
          onChange={(event) => setWebhookSecret(event.currentTarget.value)}
          disabled={clearWebhookSecret}
        />
        <Tooltip label="Send test notification">
          <ActionIcon
            size={36}
            variant="light"
            aria-label="Send webhook test notification"
            loading={testingChannel === 'webhook'}
            disabled={!webhookUrl.trim() || Boolean(testingChannel && testingChannel !== 'webhook')}
            onClick={() => testNotificationChannel('webhook')}
          >
            <IconSend size={18} />
          </ActionIcon>
        </Tooltip>
      </Group>
      {webhookSignatureConfigured && (
        <Checkbox
          label="Remove the saved signing secret when settings are saved"
          checked={clearWebhookSecret}
          onChange={(event) => setClearWebhookSecret(event.currentTarget.checked)}
        />
      )}
    </Stack>
  );
}
