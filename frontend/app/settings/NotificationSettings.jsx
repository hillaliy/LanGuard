import { Box, Divider, Stack, Tabs, Text, Title } from '@mantine/core';
import DiscordNotificationSettings from './DiscordNotificationSettings';
import NotificationRules from './NotificationRules';
import NtfyNotificationSettings from './NtfyNotificationSettings';
import TelegramNotificationSettings from './TelegramNotificationSettings';
import WebhookNotificationSettings from './WebhookNotificationSettings';

export default function NotificationSettings({ controller }) {
  return (
    <Tabs.Panel value="notifications" className="settings-category-panel">
      <Stack gap="xl">
        <Box>
          <Title order={3}>Notifications</Title>
          <Text c="dimmed">Choose which network changes are reported and configure delivery channels.</Text>
        </Box>
        <NotificationRules controller={controller} />
        <Divider label="Delivery channels" labelPosition="left" />
        <DiscordNotificationSettings controller={controller} />
        <NtfyNotificationSettings controller={controller} />
        <TelegramNotificationSettings controller={controller} />
        <WebhookNotificationSettings controller={controller} />
      </Stack>
    </Tabs.Panel>
  );
}
