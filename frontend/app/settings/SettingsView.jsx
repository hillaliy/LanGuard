import { useEffect, useState } from 'react';
import {
  ActionIcon, Alert, Badge, Box, Button, Checkbox, Divider, FileButton, Group, Image,
  Loader, LoadingOverlay, Modal, NumberInput, Paper, PasswordInput, Select, SimpleGrid, Stack,
  Switch, Table, Tabs, Text, TextInput, Title, Tooltip,
} from '@mantine/core';
import { useDisclosure } from '@mantine/hooks';
import { notifications } from '@mantine/notifications';
import {
  IconAlertCircle, IconBell, IconBrandDiscord, IconBrandDocker, IconBrandTelegram,
  IconCheck, IconDeviceFloppy, IconDevices, IconDownload, IconEdit, IconNetwork,
  IconPlus, IconRefresh, IconSend, IconServer, IconSettings, IconTrash, IconUpload,
  IconWebhook, IconWorldSearch,
} from '@tabler/icons-react';
import { apiRequest } from '../api';
import PageIcon from '../components/PageIcon';
import { formatDate } from '../utils/date';
import { displayDeviceName } from '../utils/device';
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

const emptyDockerHostForm = {
  id: null,
  device: '',
  name: '',
  enabled: true,
  sync_interval: 5,
};

function DockerIntegrationSettings({
  timeZone,
  onChanged,
}) {
  const [hosts, setHosts] = useState([]);
  const [devices, setDevices] = useState([]);
  const [form, setForm] = useState(emptyDockerHostForm);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [syncing, setSyncing] = useState(null);
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [error, setError] = useState('');

  async function loadDockerData() {
    setLoading(true);
    setError('');
    try {
      async function loadAllDevices() {
        const results = [];
        let offset = 0;
        while (true) {
          const payload = await apiRequest('device/', {
            params: { limit: 100, offset, ordering: 'name' },
          });
          results.push(...(payload.data || []));
          if (payload.pagination?.next_offset == null) {
            return results;
          }
          offset = payload.pagination.next_offset;
        }
      }

      const [hostPayload, allDevices] = await Promise.all([
        apiRequest('integrations/docker/hosts/'),
        loadAllDevices(),
      ]);
      const loadedHosts = hostPayload.data || [];
      setHosts(loadedHosts);
      setDevices(allDevices);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadDockerData();
  }, []);

  function updateForm(field, value) {
    setForm((current) => ({ ...current, [field]: value }));
  }

  function editHost(host) {
    setForm({
      id: host.id,
      device: String(host.device),
      name: host.name,
      enabled: host.enabled,
      sync_interval: host.sync_interval,
    });
    setError('');
  }

  function resetForm() {
    setForm(emptyDockerHostForm);
    setError('');
  }

  async function saveHost() {
    setSaving(true);
    setError('');
    try {
      const body = {
        device: Number(form.device),
        name: form.name.trim(),
        enabled: form.enabled,
        sync_interval: Number(form.sync_interval) || 5,
      };
      await apiRequest(
        form.id ? `integrations/docker/hosts/${form.id}/` : 'integrations/docker/hosts/',
        { method: form.id ? 'PUT' : 'POST', body }
      );
      await loadDockerData();
      await onChanged?.();
      resetForm();
      notifications.show({ title: 'Docker inventory', message: 'Host saved.', color: 'teal' });
    } catch (err) {
      setError(err.message);
      showErrorNotification(err);
    } finally {
      setSaving(false);
    }
  }

  async function syncHost(hostId) {
    setSyncing(hostId);
    try {
      const payload = await apiRequest(`integrations/docker/hosts/${hostId}/sync/`, {
        method: 'POST',
      });
      await loadDockerData();
      notifications.show({
        title: 'Docker inventory',
        message: payload.notification || 'Sync queued. The scheduler will run it shortly.',
        color: 'blue',
      });
    } catch (err) {
      showErrorNotification(err);
    } finally {
      setSyncing(null);
    }
  }

  async function deleteHost() {
    if (!deleteTarget) return;
    setSaving(true);
    try {
      await apiRequest(`integrations/docker/hosts/${deleteTarget.id}/`, { method: 'DELETE' });
      setDeleteTarget(null);
      resetForm();
      await loadDockerData();
      await onChanged?.();
      notifications.show({ title: 'Docker inventory', message: 'Host removed.', color: 'teal' });
    } catch (err) {
      showErrorNotification(err);
    } finally {
      setSaving(false);
    }
  }

  const deviceOptions = devices
    .filter((device) => !device.archived)
    .map((device) => ({
      value: String(device.id),
      label: `${displayDeviceName(device)} (${device.ip || 'No IP'})`,
    }));
  return (
    <Stack className="settings-subsection docker-integration" gap="md" pos="relative">
      <LoadingOverlay visible={loading} />
      <Group justify="space-between" align="flex-start">
        <Box>
          <Group gap="sm">
            <IconBrandDocker size={24} />
            <Text fw={700}>Docker inventory</Text>
          </Group>
          <Text size="sm" c="dimmed" mt={4}>
            Read-only container metadata from the Docker engine running LanGuard.
          </Text>
        </Box>
        <Badge color={hosts.some((host) => host.enabled) ? 'teal' : 'gray'} variant="light">
          {hosts.length ? 'Configured' : 'Not configured'}
        </Badge>
      </Group>

      {hosts.length > 0 && (
        <Table.ScrollContainer minWidth={680}>
          <Table verticalSpacing="sm" highlightOnHover>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Host</Table.Th>
                <Table.Th>Docker</Table.Th>
                <Table.Th>Containers</Table.Th>
                <Table.Th>Last sync</Table.Th>
                <Table.Th w={132} />
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {hosts.map((host) => (
                <Table.Tr key={host.id}>
                  <Table.Td>
                    <Text size="sm" fw={600}>{host.name}</Text>
                    <Text size="xs" c="dimmed">{host.device_name} · {host.device_ip}</Text>
                  </Table.Td>
                  <Table.Td>{host.docker_version || 'Not synced'}</Table.Td>
                  <Table.Td>{host.container_count}</Table.Td>
                  <Table.Td>
                    <Text size="sm">{host.sync_requested ? 'Sync queued' : (host.last_sync_at ? formatDate(host.last_sync_at, timeZone) : 'Never')}</Text>
                    {host.last_error && <Text size="xs" c="red">{host.last_error}</Text>}
                  </Table.Td>
                  <Table.Td>
                    <Group gap={4} justify="flex-end" wrap="nowrap">
                      <Tooltip label="Sync now">
                        <ActionIcon variant="subtle" loading={syncing === host.id} onClick={() => syncHost(host.id)}>
                          <IconRefresh size={17} />
                        </ActionIcon>
                      </Tooltip>
                      <Tooltip label="Edit host">
                        <ActionIcon variant="subtle" onClick={() => editHost(host)}>
                          <IconEdit size={17} />
                        </ActionIcon>
                      </Tooltip>
                      <Tooltip label="Remove host">
                        <ActionIcon color="red" variant="subtle" onClick={() => setDeleteTarget(host)}>
                          <IconTrash size={17} />
                        </ActionIcon>
                      </Tooltip>
                    </Group>
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
      )}

      {(!hosts.length || form.id) && (
        <>
          <Divider label={form.id ? `Edit ${form.name}` : 'Configure local Docker host'} labelPosition="left" />
          {error && <Alert color="red" icon={<IconAlertCircle size={18} />}>{error}</Alert>}
          <SimpleGrid cols={{ base: 1, md: 2 }}>
            <Select
              label="LanGuard device"
              description="The device that represents this Docker host."
              data={deviceOptions}
              value={form.device}
              onChange={(value) => updateForm('device', value || '')}
              searchable
              required
            />
            <TextInput
              label="Display name"
              description="The name shown for this Docker host."
              value={form.name}
              onChange={(event) => updateForm('name', event.currentTarget.value)}
              required
            />
            <NumberInput label="Sync interval" suffix=" min" min={1} max={1440} value={form.sync_interval} onChange={(value) => updateForm('sync_interval', Number(value) || 5)} />
            <Group justify="space-between" align="center" mt={27} wrap="wrap">
              <Switch label="Sync enabled" checked={form.enabled} onChange={(event) => updateForm('enabled', event.currentTarget.checked)} />
              <Group gap="xs">
                {form.id && <Button variant="subtle" onClick={resetForm}>Cancel</Button>}
                <Button variant="default" leftSection={<IconDeviceFloppy size={18} />} loading={saving} disabled={!form.device || !form.name.trim()} onClick={saveHost}>Save host</Button>
              </Group>
            </Group>
          </SimpleGrid>
        </>
      )}

      <Modal opened={Boolean(deleteTarget)} onClose={() => setDeleteTarget(null)} title="Remove Docker host" centered>
        <Stack>
          <Text>Remove {deleteTarget?.name} and its stored container inventory?</Text>
          <Text size="sm" c="dimmed">The Docker host and its containers are not changed.</Text>
          <Group justify="flex-end">
            <Button variant="default" onClick={() => setDeleteTarget(null)}>Cancel</Button>
            <Button color="red" loading={saving} onClick={deleteHost}>Remove</Button>
          </Group>
        </Stack>
      </Modal>
    </Stack>
  );
}

export default function SettingsView({
  onSaved,
}) {
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

  return (
    <Paper className="content-panel settings-page" radius="md" p="lg">
      <LoadingOverlay visible={loading} />
      <Stack>
        <Group justify="space-between" align="flex-start">
          <Group gap="sm">
            <PageIcon>
              <IconSettings size={26} />
            </PageIcon>
            <Box>
              <Title order={2}>Settings</Title>
              <Text c="dimmed">Scanner, notifications, and inventory tools</Text>
            </Box>
          </Group>
        </Group>

        {error && (
          <Alert color="red" icon={<IconAlertCircle size={18} />}>
            {error}
          </Alert>
        )}

        <Tabs
          value={settingsCategory}
          onChange={(value) => setSettingsCategory(value || 'scanning')}
          orientation="vertical"
          className="settings-layout"
        >
          <Tabs.List className="settings-category-nav">
            <Tabs.Tab value="scanning" leftSection={<IconNetwork size={18} />}>Scanning</Tabs.Tab>
            <Tabs.Tab value="notifications" leftSection={<IconBell size={18} />}>Notifications</Tabs.Tab>
            <Tabs.Tab value="integrations" leftSection={<IconWorldSearch size={18} />}>Integrations</Tabs.Tab>
            <Tabs.Tab value="data" leftSection={<IconDownload size={18} />}>Data & migration</Tabs.Tab>
            <Tabs.Tab value="maintenance" leftSection={<IconTrash size={18} />}>Maintenance</Tabs.Tab>
          </Tabs.List>

          <Tabs.Panel value="scanning" className="settings-category-panel">
        <Stack gap="lg">
          <Box>
            <Title order={3}>Network scanning</Title>
            <Text c="dimmed">Configure network ranges and scheduled scan timing.</Text>
          </Box>
        <Stack gap="sm">
          <Group justify="space-between">
            <Text fw={700}>Network ranges</Text>
            <Button
              size="xs"
              variant="light"
              leftSection={<IconPlus size={16} />}
              onClick={addScanNetwork}
              disabled={scanNetworks.length >= 16}
            >
              Add network
            </Button>
          </Group>
          <Table.ScrollContainer minWidth={560}>
            <Table withTableBorder verticalSpacing="xs">
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>Network name</Table.Th>
                  <Table.Th>CIDR range</Table.Th>
                  <Table.Th w={48} />
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {scanNetworks.map((network, index) => (
                  <Table.Tr key={index}>
                    <Table.Td>
                      <TextInput
                        value={network.name}
                        onChange={(event) =>
                          updateScanNetwork(index, 'name', event.currentTarget.value)
                        }
                        placeholder={index === 0 ? 'Primary network' : `Network ${index + 1}`}
                        aria-label={`Name for network ${index + 1}`}
                        maxLength={64}
                        required
                      />
                    </Table.Td>
                    <Table.Td>
                      <TextInput
                        value={network.cidr}
                        onChange={(event) =>
                          updateScanNetwork(index, 'cidr', event.currentTarget.value)
                        }
                        placeholder="192.168.1.0/24"
                        aria-label={`CIDR for network ${index + 1}`}
                        required
                      />
                    </Table.Td>
                    <Table.Td>
                      <Tooltip label="Remove network">
                        <ActionIcon
                          color="red"
                          variant="subtle"
                          onClick={() => removeScanNetwork(index)}
                          disabled={scanNetworks.length === 1}
                          aria-label={`Remove network ${index + 1}`}
                        >
                          <IconTrash size={17} />
                        </ActionIcon>
                      </Tooltip>
                    </Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </Table.ScrollContainer>
        </Stack>
        <SimpleGrid cols={{ base: 1, sm: 2 }}>
          <NumberInput
            label="Scan interval"
            value={scanInterval}
            onChange={(value) => setScanInterval(Number(value) || 10)}
            min={1}
            max={1440}
            suffix=" min"
            required
          />
          <Select
            label="Time zone"
            data={timeZoneOptions}
            value={timeZone}
            onChange={(value) => setTimeZone(value || 'UTC')}
            placeholder="Asia/Jerusalem"
            searchable
            maxDropdownHeight={260}
            required
          />
        </SimpleGrid>

        <Text size="xs" c="dimmed">
          Each range can contain up to {scanMaxHosts.toLocaleString()} addresses. The interval starts after each scan completes. Network range and interval changes apply automatically on the next scheduler cycle.
        </Text>
        </Stack>
          </Tabs.Panel>

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

          <Tabs.Panel value="integrations" className="settings-category-panel">
        <Stack gap="xl">
          <Group justify="space-between" align="flex-start">
            <Box>
              <Title order={3}>Integrations</Title>
              <Text c="dimmed">Connect external services that extend LanGuard network visibility.</Text>
            </Box>
            <Badge variant="light">5 available</Badge>
          </Group>
        <Tabs
          value={integrationCategory}
          onChange={(value) => setIntegrationCategory(value || 'network-services')}
          variant="pills"
          keepMounted={false}
        >
          <Tabs.List>
            <Tabs.Tab value="network-services" leftSection={<IconWorldSearch size={17} />}>
              Network services
            </Tabs.Tab>
            <Tabs.Tab value="infrastructure" leftSection={<IconServer size={17} />}>
              Infrastructure
            </Tabs.Tab>
          </Tabs.List>
          <Tabs.Panel value="network-services" pt="lg">
            <Stack gap="xl">
              <Text size="sm" c="dimmed">
                Connect services that add DNS, performance, and inventory context to LanGuard.
              </Text>
        <Stack className="settings-subsection" gap="sm">
          <Group justify="space-between" align="flex-start">
            <Box>
              <Group gap="sm">
                <Image
                  src="/integrations/adguard-home.svg"
                  alt=""
                  aria-hidden="true"
                  w={24}
                  h={24}
                  fit="contain"
                />
                <Text fw={700}>AdGuard Home</Text>
                <Switch
                  label="Enabled"
                  checked={adguardEnabled}
                  onChange={(event) => {
                    const enabled = event.currentTarget.checked;
                    setAdguardEnabled(enabled);
                    if (enabled) setPiholeEnabled(false);
                  }}
                />
              </Group>
              <Text size="sm" c="dimmed" mt={4}>
                Sync aggregated DNS destinations to device pages. LanGuard stores domain counters, not raw DNS responses.
              </Text>
            </Box>
            <Badge color={adguardConfigured && adguardEnabled ? 'teal' : 'gray'} variant="light">
              {adguardConfigured ? 'Configured' : 'Not configured'}
            </Badge>
          </Group>

          <SimpleGrid className="adguard-connection-fields" cols={{ base: 1, md: 3 }}>
            <TextInput
              label="AdGuard Home URL"
              placeholder="http://192.168.1.2:3000"
              value={adguardUrl}
              onChange={(event) => setAdguardUrl(event.currentTarget.value)}
              disabled={!adguardEnabled}
            />
            <TextInput
              label="Username"
              placeholder="admin"
              value={adguardUsername}
              onChange={(event) => setAdguardUsername(event.currentTarget.value)}
              disabled={!adguardEnabled}
            />
            <PasswordInput
              label="Password"
              placeholder={adguardConfigured ? 'Saved password' : 'Password'}
              value={adguardPassword}
              onChange={(event) => setAdguardPassword(event.currentTarget.value)}
              disabled={!adguardEnabled}
            />
          </SimpleGrid>
          {adguardConfigured && (
            <Text size="xs" c="dimmed">Leave the password blank to keep the saved password.</Text>
          )}

          <Group className="adguard-sync-controls" justify="space-between" align="flex-end" wrap="wrap">
            <Group className="adguard-sync-fields" align="flex-end" wrap="wrap">
              <NumberInput
                w={170}
                label="Sync interval"
                value={adguardSyncInterval}
                onChange={(value) => setAdguardSyncInterval(Number(value) || 5)}
                min={1}
                max={1440}
                suffix=" min"
                disabled={!adguardEnabled}
              />
              <NumberInput
                w={170}
                label="Activity retention"
                value={adguardRetentionDays}
                onChange={(value) => setAdguardRetentionDays(Number(value) || 90)}
                min={1}
                max={3650}
                suffix=" days"
                disabled={!adguardEnabled}
              />
              <Box className="adguard-sync-status" pb={6}>
                <Text size="xs" c="dimmed">
                  {adguardLastSyncAt
                    ? `Last sync: ${formatDate(adguardLastSyncAt, timeZone)}`
                    : 'Not synced yet'}
                </Text>
                {adguardLastError && (
                  <Text size="xs" c="red" maw={420} className="wrap-text">
                    Last error: {adguardLastError}
                  </Text>
                )}
              </Box>
            </Group>
            <Group className="adguard-sync-actions" gap="sm">
              <Button
                variant="default"
                leftSection={<IconSend size={18} />}
                onClick={testAdguardConnection}
                loading={testingAdguard}
                disabled={!adguardEnabled || !adguardUrl.trim() || syncingAdguard}
              >
                Test connection
              </Button>
              <Button
                variant="light"
                leftSection={<IconRefresh size={18} />}
                onClick={syncAdguardNow}
                loading={syncingAdguard}
                disabled={!adguardEnabled || !adguardConfigured || testingAdguard}
              >
                Sync now
              </Button>
            </Group>
          </Group>
        </Stack>
        <Stack className="settings-subsection" gap="sm">
          <Group justify="space-between" align="flex-start">
            <Box>
              <Group gap="sm">
                <Image
                  src="/integrations/pi-hole.svg"
                  alt=""
                  aria-hidden="true"
                  w={24}
                  h={24}
                  fit="contain"
                />
                <Text fw={700}>Pi-hole</Text>
                <Switch
                  label="Enabled"
                  checked={piholeEnabled}
                  onChange={(event) => {
                    const enabled = event.currentTarget.checked;
                    setPiholeEnabled(enabled);
                    if (enabled) setAdguardEnabled(false);
                  }}
                />
              </Group>
              <Text size="sm" c="dimmed" mt={4}>
                Sync aggregated DNS activity and discover clients from Pi-hole v6 DHCP leases.
                Only one DNS provider can be active at a time.
              </Text>
            </Box>
            <Badge color={piholeConfigured && piholeEnabled ? 'teal' : 'gray'} variant="light">
              {piholeConfigured ? 'Configured' : 'Not configured'}
            </Badge>
          </Group>

          <SimpleGrid cols={{ base: 1, md: 2 }}>
            <TextInput
              label="Pi-hole URL"
              placeholder="http://192.168.1.2"
              value={piholeUrl}
              onChange={(event) => setPiholeUrl(event.currentTarget.value)}
              disabled={!piholeEnabled}
            />
            <PasswordInput
              label="Application password"
              placeholder={piholeConfigured ? 'Saved application password' : 'Application password'}
              value={piholePassword}
              onChange={(event) => setPiholePassword(event.currentTarget.value)}
              disabled={!piholeEnabled}
            />
          </SimpleGrid>
          {piholeConfigured && (
            <Text size="xs" c="dimmed">
              Leave the application password blank to keep the saved password.
            </Text>
          )}

          <Group justify="space-between" align="flex-end" wrap="wrap">
            <Group align="flex-end" wrap="wrap">
              <NumberInput
                w={170}
                label="Sync interval"
                value={piholeSyncInterval}
                onChange={(value) => setPiholeSyncInterval(Number(value) || 5)}
                min={1}
                max={1440}
                suffix=" min"
                disabled={!piholeEnabled}
              />
              <NumberInput
                w={170}
                label="Activity retention"
                value={piholeRetentionDays}
                onChange={(value) => setPiholeRetentionDays(Number(value) || 90)}
                min={1}
                max={3650}
                suffix=" days"
                disabled={!piholeEnabled}
              />
              <Box pb={6}>
                <Text size="xs" c="dimmed">
                  {piholeLastSyncAt
                    ? `Last sync: ${formatDate(piholeLastSyncAt, timeZone)}`
                    : 'Not synced yet'}
                </Text>
                {piholeLastError && (
                  <Text size="xs" c="red" maw={420} className="wrap-text">
                    Last error: {piholeLastError}
                  </Text>
                )}
              </Box>
            </Group>
            <Group gap="sm">
              <Button
                variant="default"
                leftSection={<IconSend size={18} />}
                onClick={testPiholeConnection}
                loading={testingPihole}
                disabled={!piholeEnabled || !piholeUrl.trim() || syncingPihole}
              >
                Test connection
              </Button>
              <Button
                variant="light"
                leftSection={<IconRefresh size={18} />}
                onClick={syncPiholeNow}
                loading={syncingPihole}
                disabled={!piholeEnabled || !piholeConfigured || testingPihole}
              >
                Sync now
              </Button>
            </Group>
          </Group>
        </Stack>
        <Stack className="settings-subsection" gap="sm">
          <Group justify="space-between" align="flex-start">
            <Box>
              <Group gap="sm">
                <Image
                  src="/integrations/speedtest-tracker.svg"
                  alt=""
                  aria-hidden="true"
                  w={24}
                  h={24}
                  fit="contain"
                />
                <Text fw={700}>Speedtest Tracker</Text>
                <Switch
                  label="Enabled"
                  checked={speedtestTrackerEnabled}
                  onChange={(event) => setSpeedtestTrackerEnabled(event.currentTarget.checked)}
                />
              </Group>
              <Text size="sm" c="dimmed" mt={4}>
                Show the latest internet performance result on the dashboard.
              </Text>
            </Box>
            <Badge color={speedtestTrackerConfigured && speedtestTrackerEnabled ? 'teal' : 'gray'} variant="light">
              {speedtestTrackerConfigured ? 'Configured' : 'Not configured'}
            </Badge>
          </Group>
          <Stack className="speedtest-connection-controls" gap="sm">
          <SimpleGrid className="speedtest-connection-fields" cols={{ base: 1, md: 2 }}>
            <TextInput
              label="Speedtest Tracker URL"
              placeholder="http://192.168.1.2:8080"
              value={speedtestTrackerUrl}
              onChange={(event) => setSpeedtestTrackerUrl(event.currentTarget.value)}
              disabled={!speedtestTrackerEnabled}
            />
            <PasswordInput
              label="API token"
              placeholder={speedtestTrackerConfigured ? 'Saved API token' : 'API token'}
              value={speedtestTrackerApiToken}
              onChange={(event) => setSpeedtestTrackerApiToken(event.currentTarget.value)}
              disabled={!speedtestTrackerEnabled}
            />
          </SimpleGrid>
          {speedtestTrackerConfigured && (
            <Text className="speedtest-connection-hint" size="xs" c="dimmed">Leave the API token blank to keep the saved token.</Text>
          )}
          <Group className="speedtest-connection-actions" justify="flex-end">
            <Button
              variant="default"
              leftSection={<IconSend size={18} />}
              onClick={testSpeedtestTrackerConnection}
              loading={testingSpeedtestTracker}
              disabled={!speedtestTrackerEnabled || !speedtestTrackerUrl.trim()}
            >
              Test connection
            </Button>
          </Group>
          </Stack>
        </Stack>
        <Stack className="settings-subsection" gap="sm">
          <Group justify="space-between">
            <Group>
              <Image
                src="/integrations/homebox.svg"
                alt=""
                aria-hidden="true"
                w={24}
                h={24}
                fit="contain"
              />
              <Text fw={700}>HomeBox</Text>
              <Switch
                label="Enabled"
                checked={homeboxEnabled}
                onChange={(event) => setHomeboxEnabled(event.currentTarget.checked)}
              />
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
        </Stack>
          </Tabs.Panel>
          <Tabs.Panel value="infrastructure" pt="lg">
            <Stack gap="xl">
              <Text size="sm" c="dimmed">
                Add runtime context from the infrastructure that hosts LanGuard.
              </Text>
              <DockerIntegrationSettings
                timeZone={timeZone}
                onChanged={onSaved}
              />
            </Stack>
          </Tabs.Panel>
        </Tabs>
        </Stack>
          </Tabs.Panel>

          <Tabs.Panel value="maintenance" className="settings-category-panel">
        <Stack gap="xl">
          <Box>
            <Title order={3}>Maintenance</Title>
            <Text c="dimmed">Manage retained activity without changing device inventory.</Text>
          </Box>
        <Group justify="space-between" align="center" wrap="wrap">
          <Box>
            <Text fw={700}>Diagnostics report</Text>
            <Text size="sm" c="dimmed">
              Export a sanitized report for support without credentials or device identifiers.
            </Text>
          </Box>
          <Button
            variant="default"
            leftSection={<IconDownload size={18} />}
            onClick={exportDiagnostics}
            loading={exportingDiagnostics}
          >
            Export diagnostics
          </Button>
        </Group>
        <Divider />
        <Group justify="space-between" align="flex-start" wrap="wrap">
          <Box>
            <Text fw={700}>Activity cleanup</Text>
            <Text size="sm" c="dimmed">
              Scheduled cleanup runs every 24 hours using this retention period. Use clean all only for manual resets.
            </Text>
          </Box>
          <Group className="activity-cleanup-controls" gap="sm" align="flex-end">
            <NumberInput
              w={150}
              label="Older than"
              value={cleanupDays}
              description="Saved automatically"
              onChange={(value) => {
                setCleanupDays(value === '' || value === null ? 90 : Number(value));
                setCleanupRetentionStatus('pending');
              }}
              onBlur={saveCleanupRetention}
              onKeyDown={(event) => {
                if (event.key === 'Enter') {
                  event.currentTarget.blur();
                }
              }}
              min={1}
              max={3650}
              suffix=" days"
            />
            {cleanupRetentionStatus === 'saving' && (
              <Group gap={6} pb={8} wrap="nowrap">
                <Loader size="xs" />
                <Text size="xs" c="dimmed">Saving</Text>
              </Group>
            )}
            {cleanupRetentionStatus === 'saved' && (
              <Group gap={6} pb={8} wrap="nowrap">
                <IconCheck size={15} color="var(--mantine-color-teal-6)" />
                <Text size="xs" c="teal">Saved</Text>
              </Group>
            )}
            <Button
              color="red"
              variant="light"
              leftSection={<IconTrash size={18} />}
              onClick={() => openCleanupConfirm('events')}
              loading={cleaningActivity === 'events'}
            >
              Clean events
            </Button>
            <Button
              color="red"
              variant="light"
              leftSection={<IconTrash size={18} />}
              onClick={() => openCleanupConfirm('scan_runs')}
              loading={cleaningActivity === 'scan_runs'}
            >
              Clean history
            </Button>
            <Button
              color="red"
              variant="light"
              leftSection={<IconTrash size={18} />}
              onClick={() => openCleanupConfirm('notifications')}
              loading={cleaningActivity === 'notifications'}
            >
              Clean notifications
            </Button>
            <Button
              color="red"
              variant="light"
              leftSection={<IconTrash size={18} />}
              onClick={() => openCleanupConfirm('dns_activity')}
              loading={cleaningActivity === 'dns_activity'}
            >
              Clean DNS activity
            </Button>
          </Group>
        </Group>
        </Stack>
          </Tabs.Panel>

          <Tabs.Panel value="data" className="settings-category-panel">
        <Stack gap="xl">
          <Box>
            <Title order={3}>Data & migration</Title>
            <Text c="dimmed">Move device inventory into or out of LanGuard.</Text>
          </Box>
        <Group justify="space-between" align="flex-start" wrap="wrap">
          <Box>
            <Group gap="xs">
              <IconDevices size={24} aria-hidden="true" />
              <Text fw={700}>Device inventory</Text>
            </Group>
            <Text size="sm" c="dimmed">
              Export or import known devices, names, icons, vendors, IPs, and open ports.
            </Text>
          </Box>
          <Group gap="sm">
            <Button
              variant="default"
              leftSection={<IconDownload size={18} />}
              onClick={exportInventory}
              loading={exporting}
            >
              Export
            </Button>
            <FileButton onChange={importInventoryFile} accept="application/json,.json">
              {(props) => (
                <Button
                  {...props}
                  variant="light"
                  leftSection={<IconUpload size={18} />}
                  loading={importing}
                >
                  Import
                </Button>
              )}
            </FileButton>
          </Group>
        </Group>

        <Divider />

        <Group justify="space-between" align="flex-start" wrap="wrap">
          <Box>
            <Group gap="xs">
              <Image
                src="/integrations/netalertx.svg"
                alt=""
                aria-hidden="true"
                w={24}
                h={24}
                fit="contain"
              />
              <Text fw={700}>NetAlertX migration</Text>
            </Group>
            <Text size="sm" c="dimmed">
              Import devices from the <code>devices.csv</code> export created by NetAlertX.
            </Text>
          </Box>
          <FileButton onChange={importNetAlertXFile} accept="text/csv,.csv">
            {(props) => (
              <Button
                {...props}
                variant="light"
                leftSection={<IconUpload size={18} />}
                loading={importingNetAlertX}
              >
                Import from NetAlertX
              </Button>
            )}
          </FileButton>
        </Group>

        <Divider />

        <Group className="watchyourlan-migration-row" justify="space-between" align="flex-start" wrap="wrap">
          <Box className="watchyourlan-migration-description">
            <Group gap="xs">
              <Image
                src="/integrations/watchyourlan.png"
                alt=""
                aria-hidden="true"
                w={24}
                h={24}
                fit="contain"
              />
              <Text fw={700}>WatchYourLAN migration</Text>
            </Group>
            <Text size="sm" c="dimmed">
              Import devices from the JSON returned by the WatchYourLAN <code>/api/all</code> endpoint.
            </Text>
          </Box>
          <FileButton onChange={importWatchYourLanFile} accept="application/json,.json">
            {(props) => (
              <Button
                {...props}
                variant="light"
                leftSection={<IconUpload size={18} />}
                loading={importingWatchYourLan}
              >
                Import from WatchYourLAN
              </Button>
            )}
          </FileButton>
        </Group>
        </Stack>
          </Tabs.Panel>
        </Tabs>

        {showSettingsSave && (
          <Group justify="flex-end" className="settings-page-actions">
            <Button onClick={saveSettings} loading={saving}>
              {settingsSaveLabel}
            </Button>
          </Group>
        )}
      </Stack>
      <Modal
        opened={cleanupConfirmOpened}
        onClose={cleanupConfirm.close}
        title={`Clean ${cleanupTargetLabels[cleanupTarget] || 'activity'}`}
        centered
      >
        <Stack>
          <Text>
            Delete {cleanupTargetLabels[cleanupTarget] || 'activity'} records older than {cleanupDays} days?
          </Text>
          <Text size="sm" c="dimmed">
            Device inventory and current device data will not be deleted.
            {cleanupTarget === 'events'
              ? ' Notifications linked to deleted events will be kept, but their event link will be cleared.'
              : ''}
            {cleanupTarget === 'scan_runs'
              ? ' Running scans are never deleted.'
              : ''}
            {cleanupTarget === 'dns_activity'
              ? ' Both device DNS aggregates and unmatched-client diagnostics are included.'
              : ''}
            {' '}Clean all deletes every record of this type and cannot be undone.
          </Text>
          <Group justify="flex-end">
            <Button
              color="red"
              leftSection={<IconTrash size={18} />}
              loading={Boolean(cleaningActivity)}
              onClick={async () => {
                const cleaned = await cleanupActivity(true);
                if (cleaned) {
                  cleanupConfirm.close();
                }
              }}
            >
              Clean all
            </Button>
            <Button variant="default" onClick={cleanupConfirm.close}>
              Cancel
            </Button>
            <Button
              color="red"
              variant="light"
              leftSection={<IconTrash size={18} />}
              loading={Boolean(cleaningActivity)}
              onClick={async () => {
                const cleaned = await cleanupActivity(false);
                if (cleaned) {
                  cleanupConfirm.close();
                }
              }}
            >
              Clean
            </Button>
          </Group>
        </Stack>
      </Modal>
    </Paper>
  );
}
