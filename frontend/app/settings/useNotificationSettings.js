import { useState } from 'react';
import { apiRequest } from '../api';
import { showErrorNotification, showServerNotification } from '../utils/notifications';

const quietHoursDayOptions = [
  { value: 'mon', label: 'Mon' },
  { value: 'tue', label: 'Tue' },
  { value: 'wed', label: 'Wed' },
  { value: 'thu', label: 'Thu' },
  { value: 'fri', label: 'Fri' },
  { value: 'sat', label: 'Sat' },
  { value: 'sun', label: 'Sun' },
];
const allQuietHoursDays = quietHoursDayOptions.map(({ value }) => value);

export default function useNotificationSettings({ setError }) {
  const [discordEnabled, setDiscordEnabled] = useState(true);
  const [telegramEnabled, setTelegramEnabled] = useState(true);
  const [ntfyEnabled, setNtfyEnabled] = useState(false);
  const [webhookEnabled, setWebhookEnabled] = useState(false);
  const [discordConfigured, setDiscordConfigured] = useState(false);
  const [telegramConfigured, setTelegramConfigured] = useState(false);
  const [ntfyConfigured, setNtfyConfigured] = useState(false);
  const [webhookConfigured, setWebhookConfigured] = useState(false);
  const [webhookSignatureConfigured, setWebhookSignatureConfigured] = useState(false);
  const [discordWebhook, setDiscordWebhook] = useState('');
  const [telegramApiUrl, setTelegramApiUrl] = useState('https://api.telegram.org');
  const [telegramToken, setTelegramToken] = useState('');
  const [telegramUserId, setTelegramUserId] = useState('');
  const [ntfyServerUrl, setNtfyServerUrl] = useState('');
  const [ntfyTopic, setNtfyTopic] = useState('');
  const [ntfyPriority, setNtfyPriority] = useState('3');
  const [webhookUrl, setWebhookUrl] = useState('');
  const [webhookSecret, setWebhookSecret] = useState('');
  const [clearWebhookSecret, setClearWebhookSecret] = useState(false);
  const [notifyNewDevices, setNotifyNewDevices] = useState(true);
  const [notifyDeviceOnline, setNotifyDeviceOnline] = useState(false);
  const [notifyDeviceOffline, setNotifyDeviceOffline] = useState(false);
  const [notifyPortChanges, setNotifyPortChanges] = useState(false);
  const [notifyVersionUpdates, setNotifyVersionUpdates] = useState(false);
  const [versionCheckIntervalHours, setVersionCheckIntervalHours] = useState(6);
  const [notifySpeedtestChanges, setNotifySpeedtestChanges] = useState(false);
  const [quietHoursEnabled, setQuietHoursEnabled] = useState(false);
  const [quietHoursStart, setQuietHoursStart] = useState('22:00');
  const [quietHoursEnd, setQuietHoursEnd] = useState('07:00');
  const [quietHoursDays, setQuietHoursDays] = useState(allQuietHoursDays);
  const [testingChannel, setTestingChannel] = useState('');

  function hydrate(data) {
    setDiscordEnabled(Boolean(data.discord_enabled));
    setTelegramEnabled(Boolean(data.telegram_enabled));
    setNtfyEnabled(Boolean(data.ntfy_enabled));
    setWebhookEnabled(Boolean(data.webhook_enabled));
    setDiscordConfigured(Boolean(data.discord_configured));
    setTelegramConfigured(Boolean(data.telegram_configured));
    setNtfyConfigured(Boolean(data.ntfy_configured));
    setWebhookConfigured(Boolean(data.webhook_configured));
    setWebhookSignatureConfigured(Boolean(data.webhook_signature_configured));
    setDiscordWebhook('');
    setTelegramApiUrl(data.telegram_api_url || 'https://api.telegram.org');
    setTelegramToken('');
    setTelegramUserId(data.telegram_user_id || '');
    setNtfyServerUrl(data.ntfy_server_url || '');
    setNtfyTopic(data.ntfy_topic || '');
    setNtfyPriority(String(data.ntfy_priority || 3));
    setWebhookUrl(data.webhook_url || '');
    setWebhookSecret('');
    setClearWebhookSecret(false);
    setNotifyNewDevices(Boolean(data.notify_new_devices));
    setNotifyDeviceOnline(Boolean(data.notify_device_online));
    setNotifyDeviceOffline(Boolean(data.notify_device_offline));
    setNotifyPortChanges(Boolean(data.notify_port_changes));
    setNotifyVersionUpdates(Boolean(data.notify_version_updates));
    setVersionCheckIntervalHours(
      Math.max(1, Math.round(Number(data.version_check_interval || 21600) / 3600))
    );
    setNotifySpeedtestChanges(Boolean(data.notify_speedtest_changes));
    setQuietHoursEnabled(Boolean(data.notification_quiet_hours_enabled));
    setQuietHoursStart(data.notification_quiet_hours_start || '22:00');
    setQuietHoursEnd(data.notification_quiet_hours_end || '07:00');
    setQuietHoursDays(
      Array.isArray(data.notification_quiet_hours_days)
        ? data.notification_quiet_hours_days
        : allQuietHoursDays
    );
  }

  function buildPayload() {
    const payload = {
      discord_enabled: discordEnabled,
      telegram_enabled: telegramEnabled,
      telegram_api_url: telegramApiUrl.trim(),
      telegram_user_id: telegramUserId,
      ntfy_enabled: ntfyEnabled,
      ntfy_server_url: ntfyServerUrl.trim(),
      ntfy_topic: ntfyTopic.trim(),
      ntfy_priority: Number(ntfyPriority),
      webhook_enabled: webhookEnabled,
      webhook_url: webhookUrl.trim(),
      notify_new_devices: notifyNewDevices,
      notify_device_online: notifyDeviceOnline,
      notify_device_offline: notifyDeviceOffline,
      notify_port_changes: notifyPortChanges,
      notify_version_updates: notifyVersionUpdates,
      version_check_interval: versionCheckIntervalHours * 3600,
      notify_speedtest_changes: notifySpeedtestChanges,
      notification_quiet_hours_enabled: quietHoursEnabled,
      notification_quiet_hours_start: quietHoursStart,
      notification_quiet_hours_end: quietHoursEnd,
      notification_quiet_hours_days: quietHoursDays,
    };
    if (discordWebhook.trim()) payload.discord_webhook = discordWebhook.trim();
    if (telegramToken.trim()) payload.telegram_token = telegramToken.trim();
    if (webhookSecret) payload.webhook_secret = webhookSecret;
    if (clearWebhookSecret) payload.clear_webhook_secret = true;
    return payload;
  }

  async function testNotificationChannel(channel) {
    setTestingChannel(channel);
    setError('');
    try {
      let body;
      if (channel === 'discord') {
        body = { channel };
        if (discordWebhook.trim()) body.discord_webhook = discordWebhook.trim();
      } else if (channel === 'telegram') {
        body = {
          channel,
          telegram_api_url: telegramApiUrl.trim(),
          telegram_user_id: telegramUserId.trim(),
        };
        if (telegramToken.trim()) body.telegram_token = telegramToken.trim();
      } else if (channel === 'ntfy') {
        body = {
          channel,
          ntfy_server_url: ntfyServerUrl.trim(),
          ntfy_topic: ntfyTopic.trim(),
          ntfy_priority: Number(ntfyPriority),
        };
      } else {
        body = {
          channel,
          webhook_url: webhookUrl.trim(),
          webhook_secret: webhookSecret,
        };
      }
      const payload = await apiRequest('notifications/test/', { method: 'POST', body });
      showServerNotification(payload);
    } catch (err) {
      setError(err.message);
      showErrorNotification(err);
    } finally {
      setTestingChannel('');
    }
  }

  return {
    hydrate,
    buildPayload,
    controller: {
      clearWebhookSecret, discordConfigured, discordEnabled, discordWebhook,
      notifyDeviceOffline, notifyDeviceOnline, notifyNewDevices, notifyPortChanges,
      notifySpeedtestChanges, notifyVersionUpdates, ntfyConfigured, ntfyEnabled,
      ntfyPriority, ntfyServerUrl, ntfyTopic, quietHoursDayOptions, quietHoursDays,
      quietHoursEnabled, quietHoursEnd, quietHoursStart, setClearWebhookSecret,
      setDiscordEnabled, setDiscordWebhook, setNotifyDeviceOffline,
      setNotifyDeviceOnline, setNotifyNewDevices, setNotifyPortChanges,
      setNotifySpeedtestChanges, setNotifyVersionUpdates, setNtfyEnabled,
      setNtfyPriority, setNtfyServerUrl, setNtfyTopic, setQuietHoursDays,
      setQuietHoursEnabled, setQuietHoursEnd, setQuietHoursStart, setTelegramApiUrl,
      setTelegramEnabled, setTelegramToken, setTelegramUserId,
      setVersionCheckIntervalHours, setWebhookEnabled, setWebhookSecret,
      setWebhookUrl, telegramApiUrl, telegramConfigured, telegramEnabled,
      telegramToken, telegramUserId, testNotificationChannel, testingChannel,
      versionCheckIntervalHours, webhookConfigured, webhookEnabled, webhookSecret,
      webhookSignatureConfigured, webhookUrl,
    },
  };
}
