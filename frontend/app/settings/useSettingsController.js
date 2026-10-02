import { useEffect, useState } from 'react';
import { useDisclosure } from '@mantine/hooks';
import { notifications } from '@mantine/notifications';
import { apiRequest } from '../api';
import { showErrorNotification, showServerNotification } from '../utils/notifications';

const fallbackTimeZoneOptions = [
  'UTC',
  'Asia/Jerusalem',
  'Europe/London',
  'Europe/Paris',
  'Europe/Berlin',
  'America/New_York',
  'America/Chicago',
  'America/Denver',
  'America/Los_Angeles',
  'Asia/Dubai',
  'Asia/Tokyo',
  'Australia/Sydney',
];

const timeZoneOptions =
  typeof Intl !== 'undefined' && typeof Intl.supportedValuesOf === 'function'
    ? Intl.supportedValuesOf('timeZone')
    : fallbackTimeZoneOptions;

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

export default function useSettingsController({ onSaved }) {
  const [scanNetworks, setScanNetworks] = useState([
    { name: 'Primary network', cidr: '' },
  ]);
  const [scanMaxHosts, setScanMaxHosts] = useState(1024);
  const [scanInterval, setScanInterval] = useState(10);
  const [timeZone, setTimeZone] = useState('UTC');
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
  const [adguardEnabled, setAdguardEnabled] = useState(false);
  const [adguardConfigured, setAdguardConfigured] = useState(false);
  const [adguardUrl, setAdguardUrl] = useState('');
  const [adguardUsername, setAdguardUsername] = useState('');
  const [adguardPassword, setAdguardPassword] = useState('');
  const [adguardSyncInterval, setAdguardSyncInterval] = useState(5);
  const [adguardRetentionDays, setAdguardRetentionDays] = useState(90);
  const [adguardLastSyncAt, setAdguardLastSyncAt] = useState(null);
  const [adguardLastError, setAdguardLastError] = useState('');
  const [piholeEnabled, setPiholeEnabled] = useState(false);
  const [piholeConfigured, setPiholeConfigured] = useState(false);
  const [piholeUrl, setPiholeUrl] = useState('');
  const [piholePassword, setPiholePassword] = useState('');
  const [piholeSyncInterval, setPiholeSyncInterval] = useState(5);
  const [piholeRetentionDays, setPiholeRetentionDays] = useState(90);
  const [piholeLastSyncAt, setPiholeLastSyncAt] = useState(null);
  const [piholeLastError, setPiholeLastError] = useState('');
  const [speedtestTrackerEnabled, setSpeedtestTrackerEnabled] = useState(false);
  const [homeboxEnabled, setHomeboxEnabled] = useState(false);
  const [homeboxUrl, setHomeboxUrl] = useState('');
  const [homeboxToken, setHomeboxToken] = useState('');
  const [homeboxConfigured, setHomeboxConfigured] = useState(false);
  const [testingHomebox, setTestingHomebox] = useState(false);
  const [speedtestTrackerConfigured, setSpeedtestTrackerConfigured] = useState(false);
  const [speedtestTrackerUrl, setSpeedtestTrackerUrl] = useState('');
  const [speedtestTrackerApiToken, setSpeedtestTrackerApiToken] = useState('');
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
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [testingChannel, setTestingChannel] = useState('');
  const [testingAdguard, setTestingAdguard] = useState(false);
  const [syncingAdguard, setSyncingAdguard] = useState(false);
  const [testingPihole, setTestingPihole] = useState(false);
  const [syncingPihole, setSyncingPihole] = useState(false);
  const [testingSpeedtestTracker, setTestingSpeedtestTracker] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [exportingDiagnostics, setExportingDiagnostics] = useState(false);
  const [importing, setImporting] = useState(false);
  const [importingNetAlertX, setImportingNetAlertX] = useState(false);
  const [importingWatchYourLan, setImportingWatchYourLan] = useState(false);
  const [cleanupDays, setCleanupDays] = useState(90);
  const [savedCleanupDays, setSavedCleanupDays] = useState(90);
  const [cleanupRetentionStatus, setCleanupRetentionStatus] = useState('');
  const [cleanupTarget, setCleanupTarget] = useState(null);
  const [cleaningActivity, setCleaningActivity] = useState('');
  const [error, setError] = useState('');
  const [settingsCategory, setSettingsCategory] = useState('scanning');
  const [integrationCategory, setIntegrationCategory] = useState('network-services');
  const [cleanupConfirmOpened, cleanupConfirm] = useDisclosure(false);

  const showSettingsSave =
    settingsCategory === 'scanning'
    || settingsCategory === 'notifications'
    || (settingsCategory === 'integrations' && integrationCategory === 'network-services');
  const settingsSaveLabel = settingsCategory === 'integrations'
    ? 'Save integration settings'
    : 'Save changes';

  async function loadSettings() {
    setLoading(true);
    setError('');
    try {
      const payload = await apiRequest('settings/');
      const data = payload.data || {};
      const loadedRanges =
        Array.isArray(data.scan_ranges) && data.scan_ranges.length
          ? data.scan_ranges
          : data.ip_range
            ? [data.ip_range]
            : [];
      const loadedLabels = data.scan_range_labels || {};
      setScanNetworks(
        loadedRanges.map((cidr, index) => ({
          cidr,
          name:
            loadedLabels[cidr]
            || (index === 0 ? 'Primary network' : `Network ${index + 1}`),
        }))
      );
      setScanMaxHosts(Number(data.scan_max_hosts || 1024));
      setScanInterval(data.scan_interval || 10);
      setTimeZone(data.time_zone || 'UTC');
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
      setAdguardEnabled(Boolean(data.adguard_enabled));
      setAdguardConfigured(Boolean(data.adguard_configured));
      setAdguardUrl(data.adguard_url || '');
      setAdguardUsername(data.adguard_username || '');
      setAdguardPassword('');
      setAdguardSyncInterval(Number(data.adguard_sync_interval || 5));
      setAdguardRetentionDays(Number(data.adguard_retention_days || 90));
      setAdguardLastSyncAt(data.adguard_last_sync_at || null);
      setAdguardLastError(data.adguard_last_error || '');
      setPiholeEnabled(Boolean(data.pihole_enabled));
      setPiholeConfigured(Boolean(data.pihole_configured));
      setPiholeUrl(data.pihole_url || '');
      setPiholePassword('');
      setPiholeSyncInterval(Number(data.pihole_sync_interval || 5));
      setPiholeRetentionDays(Number(data.pihole_retention_days || 90));
      setPiholeLastSyncAt(data.pihole_last_sync_at || null);
      setPiholeLastError(data.pihole_last_error || '');
      setSpeedtestTrackerEnabled(Boolean(data.speedtest_tracker_enabled));
      setHomeboxEnabled(Boolean(data.homebox_enabled));
      setHomeboxUrl(data.homebox_url || '');
      setHomeboxToken('');
      setHomeboxConfigured(Boolean(data.homebox_configured));
      setSpeedtestTrackerConfigured(Boolean(data.speedtest_tracker_configured));
      setSpeedtestTrackerUrl(data.speedtest_tracker_url || '');
      setSpeedtestTrackerApiToken('');
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
      const loadedCleanupDays = Number(data.activity_cleanup_retention_days ?? 90);
      setCleanupDays(loadedCleanupDays);
      setSavedCleanupDays(loadedCleanupDays);
      setCleanupRetentionStatus('');
    } catch (err) {
      setError(err.message);
      showErrorNotification(err);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadSettings();
  }, []);

  async function saveSettings() {
    setSaving(true);
    setError('');
    try {
      const normalizedScanNetworks = scanNetworks.map(({ name, cidr }) => ({
        name: name.trim(),
        cidr: cidr.trim(),
      }));
      const body = {
        scan_ranges: normalizedScanNetworks.map(({ cidr }) => cidr),
        scan_range_labels: Object.fromEntries(
          normalizedScanNetworks.map(({ cidr, name }) => [cidr, name])
        ),
        scan_interval: scanInterval,
        time_zone: timeZone,
        discord_enabled: discordEnabled,
        telegram_enabled: telegramEnabled,
        telegram_api_url: telegramApiUrl.trim(),
        ntfy_enabled: ntfyEnabled,
        ntfy_server_url: ntfyServerUrl.trim(),
        ntfy_topic: ntfyTopic.trim(),
        ntfy_priority: Number(ntfyPriority),
        webhook_enabled: webhookEnabled,
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
        activity_cleanup_retention_days: cleanupDays,
        adguard_enabled: adguardEnabled,
        adguard_url: adguardUrl.trim(),
        adguard_username: adguardUsername.trim(),
        adguard_sync_interval: adguardSyncInterval,
        adguard_retention_days: adguardRetentionDays,
        pihole_enabled: piholeEnabled,
        pihole_url: piholeUrl.trim(),
        pihole_sync_interval: piholeSyncInterval,
        pihole_retention_days: piholeRetentionDays,
        speedtest_tracker_enabled: speedtestTrackerEnabled,
        homebox_enabled: homeboxEnabled,
        homebox_url: homeboxUrl.trim(),
        ...(homeboxToken ? { homebox_api_token: homeboxToken } : {}),
        speedtest_tracker_url: speedtestTrackerUrl.trim(),
      };
      if (discordWebhook.trim()) {
        body.discord_webhook = discordWebhook.trim();
      }
      body.telegram_user_id = telegramUserId;
      if (telegramToken.trim()) {
        body.telegram_token = telegramToken.trim();
      }
      body.webhook_url = webhookUrl.trim();
      if (webhookSecret) {
        body.webhook_secret = webhookSecret;
      }
      if (clearWebhookSecret) {
        body.clear_webhook_secret = true;
      }
      if (adguardPassword) {
        body.adguard_password = adguardPassword;
      }
      if (piholePassword) {
        body.pihole_password = piholePassword;
      }
      if (speedtestTrackerApiToken) {
        body.speedtest_tracker_api_token = speedtestTrackerApiToken;
      }

      const savedSettings = await apiRequest('settings/', { method: 'PUT', body });
      await loadSettings();
      await onSaved(savedSettings.data || {});
      showServerNotification(savedSettings);
    } catch (err) {
      setError(err.message);
      showErrorNotification(err);
    } finally {
      setSaving(false);
    }
  }

  function updateScanNetwork(index, field, value) {
    setScanNetworks((current) =>
      current.map((network, networkIndex) =>
        networkIndex === index ? { ...network, [field]: value } : network
      )
    );
  }

  function addScanNetwork() {
    setScanNetworks((current) => {
      if (current.length >= 16) {
        return current;
      }
      return [
        ...current,
        { name: `Network ${current.length + 1}`, cidr: '' },
      ];
    });
  }

  function removeScanNetwork(index) {
    setScanNetworks((current) =>
      current.length > 1
        ? current.filter((_, networkIndex) => networkIndex !== index)
        : current
    );
  }

  async function testNotificationChannel(channel) {
    setTestingChannel(channel);
    setError('');
    try {
      let body;
      if (channel === 'discord') {
        body = { channel };
        if (discordWebhook.trim()) {
          body.discord_webhook = discordWebhook.trim();
        }
      } else if (channel === 'telegram') {
        body = {
          channel,
          telegram_api_url: telegramApiUrl.trim(),
          telegram_user_id: telegramUserId.trim(),
        };
        if (telegramToken.trim()) {
          body.telegram_token = telegramToken.trim();
        }
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

  async function testAdguardConnection() {
    setTestingAdguard(true);
    setError('');
    try {
      const body = {
        url: adguardUrl.trim(),
        username: adguardUsername.trim(),
      };
      if (adguardPassword) {
        body.password = adguardPassword;
      }
      const payload = await apiRequest('integrations/adguard/test/', {
        method: 'POST',
        body,
      });
      showServerNotification(payload);
    } catch (err) {
      setError(err.message);
      showErrorNotification(err);
    } finally {
      setTestingAdguard(false);
    }
  }

  async function syncAdguardNow() {
    setSyncingAdguard(true);
    setError('');
    try {
      const payload = await apiRequest('integrations/adguard/sync/', { method: 'POST' });
      await loadSettings();
      showServerNotification(payload);
    } catch (err) {
      setError(err.message);
      showErrorNotification(err);
    } finally {
      setSyncingAdguard(false);
    }
  }

  async function testPiholeConnection() {
    setTestingPihole(true);
    setError('');
    try {
      const body = { url: piholeUrl.trim() };
      if (piholePassword) {
        body.password = piholePassword;
      }
      const payload = await apiRequest('integrations/pihole/test/', {
        method: 'POST',
        body,
      });
      showServerNotification(payload);
    } catch (err) {
      setError(err.message);
      showErrorNotification(err);
    } finally {
      setTestingPihole(false);
    }
  }

  async function syncPiholeNow() {
    setSyncingPihole(true);
    setError('');
    try {
      const payload = await apiRequest('integrations/pihole/sync/', { method: 'POST' });
      await loadSettings();
      showServerNotification(payload);
    } catch (err) {
      setError(err.message);
      showErrorNotification(err);
    } finally {
      setSyncingPihole(false);
    }
  }

  async function testSpeedtestTrackerConnection() {
    setTestingSpeedtestTracker(true);
    setError('');
    try {
      const body = { url: speedtestTrackerUrl.trim() };
      if (speedtestTrackerApiToken) {
        body.api_token = speedtestTrackerApiToken;
      }
      const payload = await apiRequest('integrations/speedtest-tracker/test/', {
        method: 'POST',
        body,
      });
      showServerNotification(payload);
    } catch (err) {
      setError(err.message);
      showErrorNotification(err);
    } finally {
      setTestingSpeedtestTracker(false);
    }
  }

  async function testHomeboxConnection() {
    setTestingHomebox(true);
    setError('');
    try {
      await apiRequest('integrations/homebox/test/', {
        method: 'POST', body: { url: homeboxUrl.trim(), api_token: homeboxToken },
      });
      notifications.show({ title: 'HomeBox', message: 'Connection successful', color: 'teal' });
    } catch (err) {
      setError(err.message);
    } finally {
      setTestingHomebox(false);
    }
  }

  async function exportInventory() {
    setExporting(true);
    setError('');
    try {
      const payload = await apiRequest('devices/export/');
      const { notification: exportNotification, ...inventory } = payload;
      const json = JSON.stringify(inventory, null, 2);
      const blob = new Blob([json], { type: 'application/json' });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      const date = new Date().toISOString().slice(0, 10);
      link.href = url;
      link.download = `languard-inventory-${date}.json`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      showServerNotification({ notification: exportNotification });
    } catch (err) {
      setError(err.message);
      showErrorNotification(err);
    } finally {
      setExporting(false);
    }
  }

  async function exportDiagnostics() {
    setExportingDiagnostics(true);
    setError('');
    try {
      const payload = await apiRequest('diagnostics/export/');
      const data = payload.data || {};
      const json = JSON.stringify(data.report || {}, null, 2);
      const blob = new Blob([json], { type: 'application/json' });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = data.filename || 'languard-diagnostics.json';
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      showServerNotification(payload);
    } catch (err) {
      setError(err.message);
      showErrorNotification(err);
    } finally {
      setExportingDiagnostics(false);
    }
  }

  async function importInventoryFile(file) {
    if (!file) {
      return;
    }

    setImporting(true);
    setError('');
    try {
      const text = await file.text();
      const payload = JSON.parse(text);
      const result = await apiRequest('devices/import/', {
        method: 'POST',
        body: payload,
      });
      await onSaved({});
      showServerNotification(result);
    } catch (err) {
      const message = err instanceof SyntaxError ? 'Choose a valid LanGuard JSON inventory file.' : err.message;
      setError(message);
      showErrorNotification('Could not import inventory', message);
    } finally {
      setImporting(false);
    }
  }

  async function importWatchYourLanFile(file) {
    if (!file) {
      return;
    }

    setImportingWatchYourLan(true);
    setError('');
    try {
      const text = await file.text();
      const payload = JSON.parse(text);
      const result = await apiRequest('devices/import/watchyourlan/', {
        method: 'POST',
        body: payload,
      });
      await onSaved({});
      showServerNotification(result);
    } catch (err) {
      const message =
        err instanceof SyntaxError
          ? 'Choose a valid JSON file downloaded from the WatchYourLAN /api/all endpoint.'
          : err.message;
      setError(message);
      showErrorNotification('Could not import WatchYourLAN devices', message);
    } finally {
      setImportingWatchYourLan(false);
    }
  }

  async function importNetAlertXFile(file) {
    if (!file) {
      return;
    }

    setImportingNetAlertX(true);
    setError('');
    try {
      const content = await file.text();
      const result = await apiRequest('devices/import/netalertx/', {
        method: 'POST',
        body: { content },
      });
      await onSaved({});
      showServerNotification(result);
    } catch (err) {
      setError(err.message);
      showErrorNotification('Could not import NetAlertX devices', err.message);
    } finally {
      setImportingNetAlertX(false);
    }
  }

  const cleanupTargetLabels = {
    events: 'Events',
    scan_runs: 'Scan history',
    notifications: 'Notifications',
    dns_activity: 'DNS activity',
  };

  async function cleanupActivity(cleanAll = false) {
    if (!cleanupTarget) {
      return false;
    }

    setCleaningActivity(cleanupTarget);
    setError('');
    try {
      const result = await apiRequest('maintenance/cleanup/', {
        method: 'POST',
        body: cleanAll
          ? { target: cleanupTarget, clean_all: true }
          : { target: cleanupTarget, older_than_days: cleanupDays },
      });
      await onSaved({});
      showServerNotification(result);
      return true;
    } catch (err) {
      setError(err.message);
      showErrorNotification(err);
      return false;
    } finally {
      setCleaningActivity('');
    }
  }

  function openCleanupConfirm(target) {
    setCleanupTarget(target);
    cleanupConfirm.open();
  }

  async function saveCleanupRetention() {
    const normalizedDays = Math.min(3650, Math.max(1, Number(cleanupDays) || 90));
    setCleanupDays(normalizedDays);
    if (normalizedDays === savedCleanupDays) {
      setCleanupRetentionStatus('');
      return;
    }

    setCleanupRetentionStatus('saving');
    try {
      await apiRequest('settings/', {
        method: 'PUT',
        body: { activity_cleanup_retention_days: normalizedDays },
      });
      setSavedCleanupDays(normalizedDays);
      setCleanupRetentionStatus('saved');
    } catch (err) {
      setCleanupRetentionStatus('error');
      setError(err.message);
      showErrorNotification(err);
    }
  }

  const scanningSettings = {
    addScanNetwork,
    removeScanNetwork,
    scanInterval,
    scanMaxHosts,
    scanNetworks,
    setScanInterval,
    setTimeZone,
    timeZone,
    timeZoneOptions,
    updateScanNetwork,
  };

  const notificationSettings = {
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
  };

  const integrationSettings = {
    adguardConfigured,
    adguardEnabled,
    adguardLastError,
    adguardLastSyncAt,
    adguardPassword,
    adguardRetentionDays,
    adguardSyncInterval,
    adguardUrl,
    adguardUsername,
    homeboxConfigured,
    homeboxEnabled,
    homeboxToken,
    homeboxUrl,
    integrationCategory,
    onSaved,
    piholeConfigured,
    piholeEnabled,
    piholeLastError,
    piholeLastSyncAt,
    piholePassword,
    piholeRetentionDays,
    piholeSyncInterval,
    piholeUrl,
    setAdguardEnabled,
    setAdguardPassword,
    setAdguardRetentionDays,
    setAdguardSyncInterval,
    setAdguardUrl,
    setAdguardUsername,
    setHomeboxEnabled,
    setHomeboxToken,
    setHomeboxUrl,
    setIntegrationCategory,
    setPiholeEnabled,
    setPiholePassword,
    setPiholeRetentionDays,
    setPiholeSyncInterval,
    setPiholeUrl,
    setSpeedtestTrackerApiToken,
    setSpeedtestTrackerEnabled,
    setSpeedtestTrackerUrl,
    speedtestTrackerApiToken,
    speedtestTrackerConfigured,
    speedtestTrackerEnabled,
    speedtestTrackerUrl,
    syncAdguardNow,
    syncPiholeNow,
    syncingAdguard,
    syncingPihole,
    testAdguardConnection,
    testHomeboxConnection,
    testPiholeConnection,
    testSpeedtestTrackerConnection,
    testingAdguard,
    testingHomebox,
    testingPihole,
    testingSpeedtestTracker,
    timeZone,
  };

  const maintenanceSettings = {
    cleaningActivity,
    cleanupActivity,
    cleanupConfirm,
    cleanupConfirmOpened,
    cleanupDays,
    cleanupRetentionStatus,
    cleanupTarget,
    cleanupTargetLabels,
    exportDiagnostics,
    exportingDiagnostics,
    openCleanupConfirm,
    saveCleanupRetention,
    setCleanupDays,
    setCleanupRetentionStatus,
  };

  const dataMigrationSettings = {
    exportInventory,
    exporting,
    importInventoryFile,
    importNetAlertXFile,
    importWatchYourLanFile,
    importing,
    importingNetAlertX,
    importingWatchYourLan,
  };

  return {
    loading,
    error,
    settingsCategory,
    setSettingsCategory,
    scanningSettings,
    notificationSettings,
    integrationSettings,
    maintenanceSettings,
    dataMigrationSettings,
    showSettingsSave,
    saveSettings,
    saving,
    settingsSaveLabel,
  };
}
