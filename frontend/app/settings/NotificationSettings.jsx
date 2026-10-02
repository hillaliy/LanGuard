import { ActionIcon, Badge, Box, Checkbox, Divider, Group, Image, NumberInput, PasswordInput, Select, SimpleGrid, Stack, Switch, Tabs, Text, TextInput, Title, Tooltip } from '@mantine/core';
import { IconBrandDiscord, IconBrandTelegram, IconSend, IconWebhook } from '@tabler/icons-react';

export default function NotificationSettings({ controller }) {
  const {
    clearWebhookSecret,
    discordConfigured,
    discordEnabled,
    discordWebhook,
    notifyDeviceOffline,
    notifyDeviceOnline,
    notifyNewDevices,
    notifyPortChanges,
    notifySpeedtestChanges,
    notifyVersionUpdates,
    ntfyConfigured,
    ntfyEnabled,
    ntfyPriority,
    ntfyServerUrl,
    ntfyTopic,
    quietHoursDayOptions,
    quietHoursDays,
    quietHoursEnabled,
    quietHoursEnd,
    quietHoursStart,
    setClearWebhookSecret,
    setDiscordEnabled,
    setDiscordWebhook,
    setNotifyDeviceOffline,
    setNotifyDeviceOnline,
    setNotifyNewDevices,
    setNotifyPortChanges,
    setNotifySpeedtestChanges,
    setNotifyVersionUpdates,
    setNtfyEnabled,
    setNtfyPriority,
    setNtfyServerUrl,
    setNtfyTopic,
    setQuietHoursDays,
    setQuietHoursEnabled,
    setQuietHoursEnd,
    setQuietHoursStart,
    setTelegramApiUrl,
    setTelegramEnabled,
    setTelegramToken,
    setTelegramUserId,
    setVersionCheckIntervalHours,
    setWebhookEnabled,
    setWebhookSecret,
    setWebhookUrl,
    telegramApiUrl,
    telegramConfigured,
    telegramEnabled,
    telegramToken,
    telegramUserId,
    testNotificationChannel,
    testingChannel,
    versionCheckIntervalHours,
    webhookConfigured,
    webhookEnabled,
    webhookSecret,
    webhookSignatureConfigured,
    webhookUrl,
  } = controller;

  return (
<Tabs.Panel value="notifications" className="settings-category-panel">
        <Stack gap="xl">
          <Box>
            <Title order={3}>Notifications</Title>
            <Text c="dimmed">Choose which network changes are reported and configure delivery channels.</Text>
          </Box>
          <Stack gap="sm">
          <Text fw={700}>Rules</Text>
          <SimpleGrid cols={{ base: 1, sm: 2 }}>
            <Switch
              label="New devices"
              checked={notifyNewDevices}
              onChange={(event) => setNotifyNewDevices(event.currentTarget.checked)}
            />
            <Switch
              label="Device comes online"
              checked={notifyDeviceOnline}
              onChange={(event) => setNotifyDeviceOnline(event.currentTarget.checked)}
            />
            <Switch
              label="Device goes offline"
              checked={notifyDeviceOffline}
              onChange={(event) => setNotifyDeviceOffline(event.currentTarget.checked)}
            />
            <Switch
              label="Port changes"
              checked={notifyPortChanges}
              onChange={(event) => setNotifyPortChanges(event.currentTarget.checked)}
            />
            <Switch
              label="New LanGuard version"
              checked={notifyVersionUpdates}
              onChange={(event) => setNotifyVersionUpdates(event.currentTarget.checked)}
            />
            <Switch
              label="Speedtest health changes"
              checked={notifySpeedtestChanges}
              onChange={(event) => setNotifySpeedtestChanges(event.currentTarget.checked)}
            />
          </SimpleGrid>
          <NumberInput
            label="Update check interval"
            description="How often LanGuard checks for a new release."
            value={versionCheckIntervalHours}
            onChange={(value) => setVersionCheckIntervalHours(Number(value) || 6)}
            min={1}
            max={168}
            step={1}
            suffix=" hr"
            allowDecimal={false}
            required
            maw={320}
          />
          <SimpleGrid cols={{ base: 1, sm: 3 }}>
            <Switch
              label="Quiet hours"
              checked={quietHoursEnabled}
              onChange={(event) => setQuietHoursEnabled(event.currentTarget.checked)}
            />
            <TextInput
              type="time"
              label="Quiet from"
              value={quietHoursStart}
              onChange={(event) => setQuietHoursStart(event.currentTarget.value)}
              disabled={!quietHoursEnabled}
            />
            <TextInput
              type="time"
              label="Quiet until"
              value={quietHoursEnd}
              onChange={(event) => setQuietHoursEnd(event.currentTarget.value)}
              disabled={!quietHoursEnabled}
            />
          </SimpleGrid>
          <Checkbox.Group
            label="Quiet days"
            description="For overnight ranges, early morning hours belong to the previous day."
            value={quietHoursDays}
            onChange={setQuietHoursDays}
          >
            <Group mt="xs" gap="lg">
              {quietHoursDayOptions.map((day) => (
                <Checkbox
                  key={day.value}
                  value={day.value}
                  label={day.label}
                  disabled={!quietHoursEnabled}
                />
              ))}
            </Group>
          </Checkbox.Group>
          </Stack>

          <Divider label="Delivery channels" labelPosition="left" />

        <Stack className="settings-subsection" gap="sm">
          <Group justify="space-between">
            <Group gap="sm">
              <Group gap={6}>
                <IconBrandDiscord size={18} />
                <Text fw={700}>Discord</Text>
              </Group>
              <Switch
                label="Enabled"
                checked={discordEnabled}
                onChange={(event) => setDiscordEnabled(event.currentTarget.checked)}
              />
            </Group>
            <Badge color={discordConfigured && discordEnabled ? 'teal' : 'gray'} variant="light">
              {discordConfigured ? 'Configured' : 'Not configured'}
            </Badge>
          </Group>
          <Group align="flex-end" wrap="nowrap">
            <PasswordInput
              style={{ flex: 1 }}
              label="Discord webhook"
              description={
                discordConfigured
                  ? 'Leave blank to keep the saved webhook.'
                  : 'Paste a Discord channel webhook URL to enable Discord messages.'
              }
              placeholder={
                discordConfigured
                  ? 'Saved webhook'
                  : 'https://discord.com/api/webhooks/...'
              }
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
                disabled={
                  (!discordWebhook.trim() && !discordConfigured) ||
                  Boolean(testingChannel && testingChannel !== 'discord')
                }
                onClick={() => testNotificationChannel('discord')}
              >
                <IconSend size={18} />
              </ActionIcon>
            </Tooltip>
          </Group>
        </Stack>

        <Stack className="settings-subsection" gap="sm">
          <Group justify="space-between">
            <Group gap="sm">
              <Group gap={6}>
                <Image src="/integrations/ntfy.svg" alt="" w={18} h={18} />
                <Text fw={700}>ntfy</Text>
              </Group>
              <Switch
                label="Enabled"
                checked={ntfyEnabled}
                onChange={(event) => setNtfyEnabled(event.currentTarget.checked)}
              />
            </Group>
            <Badge color={ntfyConfigured && ntfyEnabled ? 'teal' : 'gray'} variant="light">
              {ntfyConfigured ? 'Configured' : 'Not configured'}
            </Badge>
          </Group>
          <Group align="flex-end" wrap="wrap">
            <TextInput
              style={{ flex: '1 1 320px' }}
              label="ntfy server URL"
              description="Use ntfy.sh or the root URL of your self-hosted ntfy server."
              placeholder="https://ntfy.sh"
              value={ntfyServerUrl}
              onChange={(event) => setNtfyServerUrl(event.currentTarget.value)}
            />
            <TextInput
              style={{ flex: '1 1 220px' }}
              label="Topic"
              placeholder="languard-alerts"
              value={ntfyTopic}
              onChange={(event) => setNtfyTopic(event.currentTarget.value)}
            />
            <Select
              style={{ flex: '0 1 180px' }}
              label="Priority"
              value={ntfyPriority}
              onChange={(value) => setNtfyPriority(value || '3')}
              data={[
                { value: '1', label: 'Min' },
                { value: '2', label: 'Low' },
                { value: '3', label: 'Default' },
                { value: '4', label: 'High' },
                { value: '5', label: 'Max' },
              ]}
            />
            <Tooltip label="Send test notification">
              <ActionIcon
                size={36}
                variant="light"
                aria-label="Send ntfy test notification"
                loading={testingChannel === 'ntfy'}
                disabled={
                  !ntfyServerUrl.trim() ||
                  !ntfyTopic.trim() ||
                  Boolean(testingChannel && testingChannel !== 'ntfy')
                }
                onClick={() => testNotificationChannel('ntfy')}
              >
                <IconSend size={18} />
              </ActionIcon>
            </Tooltip>
          </Group>
        </Stack>

        <Stack className="settings-subsection" gap="sm">
          <Group justify="space-between">
            <Group gap="sm">
              <Group gap={6}>
                <IconBrandTelegram size={18} />
                <Text fw={700}>Telegram</Text>
              </Group>
              <Switch
                label="Enabled"
                checked={telegramEnabled}
                onChange={(event) => setTelegramEnabled(event.currentTarget.checked)}
              />
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
            <TextInput
              style={{ flex: 1 }}
              label="Telegram user ID"
              placeholder="123456789"
              value={telegramUserId}
              onChange={(event) => setTelegramUserId(event.currentTarget.value)}
            />
            <Tooltip label="Send test notification">
              <ActionIcon
                size={36}
                variant="light"
                aria-label="Send Telegram test notification"
                loading={testingChannel === 'telegram'}
                disabled={
                  !telegramApiUrl.trim() ||
                  (!telegramToken.trim() && !telegramConfigured) ||
                  !telegramUserId.trim() ||
                  Boolean(testingChannel && testingChannel !== 'telegram')
                }
                onClick={() => testNotificationChannel('telegram')}
              >
                <IconSend size={18} />
              </ActionIcon>
            </Tooltip>
          </Group>
        </Stack>

        <Stack className="settings-subsection" gap="sm">
          <Group justify="space-between">
            <Group gap="sm">
              <Group gap={6}>
                <IconWebhook size={18} />
                <Text fw={700}>Automation webhook</Text>
              </Group>
              <Switch
                label="Enabled"
                checked={webhookEnabled}
                onChange={(event) => setWebhookEnabled(event.currentTarget.checked)}
              />
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
              description={
                webhookSignatureConfigured
                  ? 'Leave blank to keep the saved secret.'
                  : 'Optional HMAC secret used to verify LanGuard deliveries.'
              }
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
                disabled={
                  !webhookUrl.trim() ||
                  Boolean(testingChannel && testingChannel !== 'webhook')
                }
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
        </Stack>
          </Tabs.Panel>
  );
}
