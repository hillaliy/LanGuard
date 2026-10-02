'use client';

import { useEffect, useRef, useState } from 'react';
import {
  ActionIcon,
  Alert,
  Autocomplete,
  Badge,
  Box,
  Button,
  Divider,
  Group,
  LoadingOverlay,
  Loader,
  Modal,
  NumberInput,
  Paper,
  Progress,
  Select,
  SegmentedControl,
  SimpleGrid,
  ScrollArea,
  Stack,
  Switch,
  Table,
  Tabs,
  Text,
  TextInput,
  Textarea,
  Title,
  Tooltip,
  UnstyledButton,
} from '@mantine/core';
import { useDisclosure } from '@mantine/hooks';
import {
  IconAlertCircle,
  IconArchive,
  IconArchiveOff,
  IconArrowLeft,
  IconArrowUpRight,
  IconChevronDown,
  IconDeviceFloppy,
  IconEdit,
  IconExternalLink,
  IconHistory,
  IconNetwork,
  IconPlayerStop,
  IconPower,
  IconRadar,
  IconSearch,
  IconTrash,
  IconWorldSearch,
  IconX,
} from '@tabler/icons-react';

import { apiRequest } from '../api';
import {
  activityRecordLabel,
  appendUniqueById,
  hasNextActivityPage,
} from '../utils/activity';
import {
  DeviceClassificationBadge,
  GatewayBadge,
  RiskBadge,
} from '../components/DeviceBadges';
import DeviceIconStack, {
  DeviceIcon,
  deviceIconOptions,
  normalizeDeviceIcon,
} from '../components/DeviceIconStack';
import { PortGuidanceBadge } from '../components/PortGuidance';
import SummaryMetric from '../components/SummaryMetric';
import { formatDate } from '../utils/date';
import {
  buildRoomOptions,
  deviceStatus,
  displayDeviceName,
  externalUrlUsesIPv4,
  formatRoleLabel,
  resolveExternalUrl,
  validExternalUrl,
} from '../utils/device';

const deviceRoleOptions = [
  'device',
  'gateway',
  'router',
  'meshRouter',
  'hub',
  'camera',
  'gameConsole',
  'computer',
  'laptop',
  'server',
  'nas',
  'phone',
  'tablet',
  'tv',
  'streamer',
  'printer',
  'speaker',
  'light',
  'climate',
  'smartPlug',
  'smartRelay',
  'smartPowerStrip',
  'powerMeter',
  'controller',
  'lock',
  'intercom',
  'sensor',
  'robotVacuum',
  'watch',
  'unknown',
  'other',
].sort((left, right) =>
  formatRoleLabel(left).localeCompare(formatRoleLabel(right))
);

const deviceNotificationPreferenceOptions = [
  { value: 'inherit', label: 'Use global setting' },
  { value: 'always', label: 'Always notify' },
  { value: 'never', label: 'Never notify' },
];

function formatDeviceNotificationPreference(value) {
  return deviceNotificationPreferenceOptions.find((option) => option.value === value)?.label
    || 'Use global setting';
}

const devicePresenceExpectationOptions = [
  { value: 'automatic', label: 'Automatic' },
  { value: 'always', label: 'Always expected' },
  { value: 'occasional', label: 'Occasionally present' },
  { value: 'never', label: 'Do not monitor absence' },
];

function formatDevicePresenceExpectation(value) {
  return devicePresenceExpectationOptions.find((option) => option.value === value)?.label
    || 'Automatic';
}

function formatOfflineAttention(device) {
  const days = device?.offline_attention_effective_days;
  return Number.isInteger(days) ? `After ${days} days offline` : 'Disabled';
}

function formatAvailabilityDuration(seconds) {
  const value = Number(seconds);
  if (!Number.isFinite(value) || value < 0) {
    return '-';
  }
  const totalMinutes = Math.round(value / 60);
  const days = Math.floor(totalMinutes / 1440);
  const hours = Math.floor((totalMinutes % 1440) / 60);
  const minutes = totalMinutes % 60;
  if (days > 0) {
    return `${days}d ${hours}h`;
  }
  if (hours > 0) {
    return `${hours}h ${minutes}m`;
  }
  return `${minutes}m`;
}

function DeviceField({ label, value, editable = false, required = false, onChange }) {
  return (
    <Box className={`device-field ${editable ? 'editable' : ''}`}>
      <Group gap={4}>
        <Text size="xs" c="dimmed">{label}</Text>
        {required && <Text size="xs" c="red">*</Text>}
      </Group>
      {editable ? (
        <TextInput
          classNames={{ input: 'device-field-input' }}
          value={value}
          onChange={(event) => onChange(event.currentTarget.value)}
        />
      ) : (
        <Text size="sm" className="wrap-text">{value || '-'}</Text>
      )}
    </Box>
  );
}

function IdentityConfidenceField({ device }) {
  const confidence = String(device?.identity_confidence || 'low').toLowerCase();
  const evidence = Array.isArray(device?.identity_evidence) ? device.identity_evidence : [];
  const color = confidence === 'high' ? 'green' : confidence === 'medium' ? 'yellow' : 'gray';
  const label = confidence.charAt(0).toUpperCase() + confidence.slice(1);

  return (
    <Box className="device-field identity-confidence-field" mt="md">
      <Group justify="space-between" gap="xs" wrap="nowrap">
        <Text size="xs" c="dimmed">Identity confidence</Text>
        <Badge color={color} variant="light">{label}</Badge>
      </Group>
      {evidence.length > 0 ? (
        <Stack gap={2} mt={4}>
          {evidence.map((item) => (
            <Group key={item.field} justify="space-between" gap="xs" wrap="nowrap">
              <Text size="xs" className="wrap-text">
                {item.field === 'hostname' ? 'Hostname' : 'Vendor'}: {item.source_display || 'Unknown'}
              </Text>
              <Text size="xs" c="dimmed">
                {String(item.confidence || 'low').replace(/^./, (letter) => letter.toUpperCase())}
              </Text>
            </Group>
          ))}
        </Stack>
      ) : (
        <Text size="xs" c="dimmed" mt={4}>No identity evidence collected yet.</Text>
      )}
    </Box>
  );
}


function RoomField({ value, onChange, roomOptions = [] }) {
  return (
    <Box className="device-field editable">
      <Text size="xs" c="dimmed">Room</Text>
      <Group gap="xs" wrap="nowrap">
        <Autocomplete
          className="device-room-input"
          classNames={{ input: 'device-field-input' }}
          data={roomOptions}
          value={value || ''}
          onChange={onChange}
          placeholder="Unassigned"
        />
        {value ? (
          <Tooltip label="Clear room">
            <ActionIcon
              aria-label="Clear room"
              variant="subtle"
              color="gray"
              onClick={() => onChange('')}
            >
              <IconX size={16} />
            </ActionIcon>
          </Tooltip>
        ) : null}
      </Group>
    </Box>
  );
}

function DeviceIconPicker({ value, onChange, label = 'Icon' }) {
  const selectedIcon = normalizeDeviceIcon(value);

  return (
    <Box className="device-field icon-picker-field">
      <Text size="xs" c="dimmed">{label}</Text>
      <div className="icon-picker-grid">
        {deviceIconOptions.map((option) => {
          const Icon = option.icon;
          const selected = option.value === selectedIcon;

          return (
            <Tooltip key={option.value} label={option.label}>
              <UnstyledButton
                className={`icon-picker-button ${selected ? 'selected' : ''}`}
                onClick={() => onChange(option.value)}
                aria-label={option.label}
              >
                <Icon size={18} stroke={1.8} />
              </UnstyledButton>
            </Tooltip>
          );
        })}
      </div>
    </Box>
  );
}

function HomeBoxItemPicker({ value, onChange }) {
  const [query, setQuery] = useState('');
  const [page, setPage] = useState(1);
  const [items, setItems] = useState([]);
  const [hasMore, setHasMore] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => {
    let cancelled = false;
    setBusy(true);
    const timer = setTimeout(async () => {
      try {
        const payload = await apiRequest('integrations/homebox/items/', { params: { q: query, page } });
        if (cancelled) return;
        setItems((old) => {
          const combined = page === 1 ? payload.data.items : [...old, ...payload.data.items];
          return [...new Map(combined.map((item) => [item.value, item])).values()];
        });
        setHasMore(payload.data.has_more);
        setError('');
      } catch (err) {
        if (!cancelled) { setError(err.message); setHasMore(false); }
      } finally {
        if (!cancelled) setBusy(false);
      }
    }, 300);
    return () => { cancelled = true; clearTimeout(timer); };
  }, [query, page]);
  const options = value && !items.some((item) => item.value === value)
    ? [{ value, label: value }, ...items] : items;
  return (
    <Stack gap="xs">
      <Select label="HomeBox item" placeholder="Search by name, description, or asset ID" searchable clearable
        data={options} value={value || null} onChange={onChange}
        searchValue={query} onSearchChange={(next) => { setQuery(next); setPage(1); }}
        filter={({ options: available }) => available}
        nothingFoundMessage={busy ? 'Loading...' : 'No items found'} error={error}
      />
      {hasMore && <Button variant="subtle" size="xs" leftSection={<IconChevronDown size={16} />} loading={busy} onClick={() => setPage((old) => old + 1)}>Load more</Button>}
    </Stack>
  );
}

export default function DeviceDetailsView({
  deviceId,
  onBack,
  onSaved,
  onDeleted,
  timeZone,
  roomOptions,
  dnsActivityEnabled,
  canEditDevices,
  canRunScans,
  onError,
  onSuccess,
}) {
  const [device, setDevice] = useState(null);
  const [events, setEvents] = useState([]);
  const [eventPagination, setEventPagination] = useState(null);
  const [availabilityPeriod, setAvailabilityPeriod] = useState('week');
  const [availability, setAvailability] = useState(null);
  const [loadingAvailability, setLoadingAvailability] = useState(false);
  const [icon, setIcon] = useState('');
  const [secondaryIcon, setSecondaryIcon] = useState('');
  const [name, setName] = useState('');
  const [role, setRole] = useState('device');
  const [room, setRoom] = useState('');
  const [known, setKnown] = useState(false);
  const [isVisitor, setIsVisitor] = useState(false);
  const [onlineNotificationPreference, setOnlineNotificationPreference] = useState('inherit');
  const [offlineNotificationPreference, setOfflineNotificationPreference] = useState('inherit');
  const [presenceExpectation, setPresenceExpectation] = useState('automatic');
  const [offlineAttentionAfterDays, setOfflineAttentionAfterDays] = useState('');
  const [comments, setComments] = useState('');
  const [externalUrl, setExternalUrl] = useState('');
  const [externalUrlFollowDeviceIp, setExternalUrlFollowDeviceIp] = useState(false);
  const [homeboxItemId, setHomeboxItemId] = useState(null);
  const [detectedWebUrl, setDetectedWebUrl] = useState('');
  const [detectingWebUrl, setDetectingWebUrl] = useState(false);
  const [attentionAcknowledged, setAttentionAcknowledged] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loadingMoreEvents, setLoadingMoreEvents] = useState(false);
  const [activeDeviceTab, setActiveDeviceTab] = useState('overview');
  const [dnsActivity, setDnsActivity] = useState([]);
  const [dnsPagination, setDnsPagination] = useState(null);
  const [dnsSummary, setDnsSummary] = useState(null);
  const [dnsIntegration, setDnsIntegration] = useState(null);
  const [dnsSearch, setDnsSearch] = useState('');
  const [dnsFilter, setDnsFilter] = useState('all');
  const [dnsOrdering, setDnsOrdering] = useState('-last_seen');
  const [loadingDnsActivity, setLoadingDnsActivity] = useState(false);
  const [loadingMoreDnsActivity, setLoadingMoreDnsActivity] = useState(false);
  const [saving, setSaving] = useState(false);
  const [waking, setWaking] = useState(false);
  const [portScan, setPortScan] = useState(null);
  const [portScanSpec, setPortScanSpec] = useState('1-1024');
  const [portScanLoading, setPortScanLoading] = useState(false);
  const [portScanError, setPortScanError] = useState('');
  const [editing, setEditing] = useState(false);
  const [error, setError] = useState('');
  const [deleteConfirmOpened, deleteConfirm] = useDisclosure(false);
  const [archiveConfirmOpened, archiveConfirm] = useDisclosure(false);
  const [portScanOpened, portScanModal] = useDisclosure(false);
  const completedPortScanRef = useRef(null);

  function populateForm(nextDevice) {
    setIcon(nextDevice?.icon || '');
    setSecondaryIcon(nextDevice?.secondary_icon || '');
    setName(nextDevice?.name || '');
    setRole(nextDevice?.role || 'device');
    setRoom(nextDevice?.room || '');
    setKnown(Boolean(nextDevice?.known));
    setIsVisitor(Boolean(nextDevice?.is_visitor));
    setOnlineNotificationPreference(nextDevice?.online_notification_preference || 'inherit');
    setOfflineNotificationPreference(nextDevice?.offline_notification_preference || 'inherit');
    setPresenceExpectation(nextDevice?.presence_expectation || 'automatic');
    setOfflineAttentionAfterDays(nextDevice?.offline_attention_after_days ?? '');
    setComments(nextDevice?.comments || '');
    setExternalUrl(
      nextDevice?.external_url_follow_device_ip
        ? nextDevice?.effective_external_url || nextDevice?.external_url || ''
        : nextDevice?.external_url || ''
    );
    setExternalUrlFollowDeviceIp(Boolean(nextDevice?.external_url_follow_device_ip));
    setHomeboxItemId(nextDevice?.homebox_item_id || null);
    setAttentionAcknowledged(Boolean(nextDevice?.attention_acknowledged));
  }

  function startEditing() {
    setActiveDeviceTab('overview');
    if (!externalUrl.trim() && detectedWebUrl) {
      setExternalUrl(detectedWebUrl);
      setExternalUrlFollowDeviceIp(true);
    }
    setEditing(true);
  }

  async function loadDevice({ quiet = false } = {}) {
    if (!quiet) {
      setLoading(true);
    }
    setError('');
    try {
      const payload = await apiRequest('device/', { params: { id: deviceId } });
      const nextDevice = payload.data;
      setDevice(nextDevice);
      populateForm(nextDevice);
      return nextDevice;
    } catch (err) {
      setError(err.message);
      return null;
    } finally {
      if (!quiet) {
        setLoading(false);
      }
    }
  }

  async function loadDeviceEvents({ offset = 0, append = false } = {}) {
    const payload = await apiRequest('events/', {
      params: { device: deviceId, limit: 100, offset },
    });
    const nextEvents = payload.data || [];
    setEvents((current) => (append ? appendUniqueById(current, nextEvents) : nextEvents));
    setEventPagination(payload.pagination || null);
  }

  async function loadDnsActivity({ offset = 0, append = false, quiet = false } = {}) {
    if (!quiet) {
      setLoadingDnsActivity(true);
    }
    const params = {
      id: deviceId,
      limit: 100,
      offset,
      search: dnsSearch.trim(),
      ordering: dnsOrdering,
    };
    if (dnsFilter === 'blocked') {
      params.blocked = true;
    } else if (dnsFilter === 'allowed') {
      params.blocked = false;
    }
    try {
      const payload = await apiRequest('device/dns-activity/', { params });
      const nextActivity = payload.data || [];
      setDnsActivity((current) =>
        append ? appendUniqueById(current, nextActivity) : nextActivity
      );
      setDnsPagination(payload.pagination || null);
      setDnsSummary(payload.summary || null);
      setDnsIntegration(payload.integration || null);
    } finally {
      if (!quiet) {
        setLoadingDnsActivity(false);
      }
    }
  }

  useEffect(() => {
    let active = true;
    setLoading(true);
    Promise.all([
      apiRequest('device/', { params: { id: deviceId } }),
      apiRequest('events/', { params: { device: deviceId, limit: 100 } }),
    ])
      .then(([devicePayload, eventPayload]) => {
        if (!active) {
          return;
        }
        setDevice(devicePayload.data);
        populateForm(devicePayload.data);
        setEvents(eventPayload.data || []);
        setEventPagination(eventPayload.pagination || null);
        setError('');
      })
      .catch((err) => {
        if (active) {
          setError(err.message);
        }
      })
      .finally(() => {
        if (active) {
          setLoading(false);
        }
      });
    return () => {
      active = false;
    };
  }, [deviceId]);

  useEffect(() => {
    if (!portScanOpened) {
      return undefined;
    }
    let active = true;

    async function refreshPortScan() {
      try {
        const payload = await apiRequest('device/port-scan/', {
          params: { device: deviceId },
        });
        if (!active) {
          return;
        }
        const nextScan = payload.data || null;
        setPortScan(nextScan);
        setPortScanError('');
        if (
          nextScan?.status === 'success'
          && completedPortScanRef.current !== nextScan.id
        ) {
          completedPortScanRef.current = nextScan.id;
          const updatedDevice = await loadDevice({ quiet: true });
          if (updatedDevice) {
            await onSaved(updatedDevice);
          }
        }
      } catch (err) {
        if (active) {
          setPortScanError(err.message);
        }
      }
    }

    setPortScanLoading(true);
    refreshPortScan().finally(() => {
      if (active) {
        setPortScanLoading(false);
      }
    });
    const scanIsActive = portScan?.status === 'queued' || portScan?.status === 'running';
    const timer = scanIsActive ? window.setInterval(refreshPortScan, 1000) : null;
    return () => {
      active = false;
      if (timer) {
        window.clearInterval(timer);
      }
    };
  }, [deviceId, portScan?.id, portScan?.status, portScanOpened]);

  useEffect(() => {
    setActiveDeviceTab('overview');
    setAvailabilityPeriod('week');
    setAvailability(null);
    setDnsActivity([]);
    setDnsPagination(null);
    setDnsSummary(null);
    setDnsIntegration(null);
    setDnsSearch('');
    setDnsFilter('all');
    setDnsOrdering('-last_seen');
  }, [deviceId]);

  useEffect(() => {
    if (activeDeviceTab !== 'history') {
      return undefined;
    }
    let active = true;
    setLoadingAvailability(true);
    apiRequest('device/availability/', {
      params: { device: deviceId, period: availabilityPeriod },
    })
      .then((payload) => {
        if (active) {
          setAvailability(payload.data || null);
        }
      })
      .catch((err) => {
        if (active) {
          onError(err);
        }
      })
      .finally(() => {
        if (active) {
          setLoadingAvailability(false);
        }
      });
    return () => {
      active = false;
    };
  }, [activeDeviceTab, availabilityPeriod, deviceId]);

  useEffect(() => {
    if (activeDeviceTab !== 'dns') {
      return undefined;
    }
    const timer = window.setTimeout(() => {
      loadDnsActivity().catch((err) => {
        onError(err);
      });
    }, 250);
    return () => window.clearTimeout(timer);
  }, [activeDeviceTab, deviceId, dnsSearch, dnsFilter, dnsOrdering]);

  useEffect(() => {
    if (!dnsActivityEnabled && activeDeviceTab === 'dns') {
      setActiveDeviceTab('overview');
    }
  }, [activeDeviceTab, dnsActivityEnabled]);

  useEffect(() => {
    if (!device) {
      return undefined;
    }
    setDetectedWebUrl('');
    const webPorts = new Set([80, 443, 8000, 8080, 8443, 8888]);
    const hasWebPort = (device.open_ports || []).some((item) =>
      webPorts.has(Number(item?.port ?? item))
    );
    if (device.external_url || !hasWebPort) {
      setDetectingWebUrl(false);
      return undefined;
    }

    let active = true;
    setDetectingWebUrl(true);
    apiRequest('device/web-interface/', { params: { id: device.id } })
      .then((payload) => {
        if (active) {
          setDetectedWebUrl(payload?.url || '');
        }
      })
      .catch(() => {})
      .finally(() => {
        if (active) {
          setDetectingWebUrl(false);
        }
      });
    return () => {
      active = false;
    };
  }, [device]);

  async function changeArchiveState() {
    setSaving(true);
    setError('');
    try {
      const payload = await apiRequest(`device/?id=${device.id}`, {
        method: 'PUT', body: { archived: !device.archived },
      });
      const updatedDevice = await loadDevice({ quiet: true });
      await onSaved(updatedDevice);
      archiveConfirm.close();
      setEditing(false);
      onSuccess(payload);
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  async function save() {
    if (!device || !name.trim()) {
      if (!name.trim()) {
        setError('Device name is required.');
      }
      return;
    }
    setSaving(true);
    setError('');
    if (!validExternalUrl(externalUrl)) {
      const message = 'Enter a valid HTTP or HTTPS URL.';
      setError(message);
      onError('Could not save device', message);
      setSaving(false);
      return;
    }
    if (externalUrlFollowDeviceIp && !externalUrlUsesIPv4(externalUrl)) {
      const message = 'Follow device IP requires an External link with an IPv4 address.';
      setError(message);
      onError('Could not save device', message);
      setSaving(false);
      return;
    }
    try {
      const payload = await apiRequest(`device/?id=${device.id}`, {
        method: 'PUT',
        body: {
          icon,
          secondary_icon: secondaryIcon || '',
          name,
          role,
          room,
          known,
          is_visitor: isVisitor,
          online_notification_preference: onlineNotificationPreference,
          offline_notification_preference: offlineNotificationPreference,
          presence_expectation: presenceExpectation,
          offline_attention_after_days: ['always', 'occasional'].includes(presenceExpectation)
            ? offlineAttentionAfterDays || null
            : null,
          comments,
          external_url: externalUrl.trim(),
          external_url_follow_device_ip: externalUrlFollowDeviceIp,
          homebox_item_id: homeboxItemId,
          acknowledge_attention: known && attentionAcknowledged,
        },
      });
      const updatedDevice = await loadDevice({ quiet: true });
      await onSaved(updatedDevice);
      onSuccess(payload);
      setEditing(false);
    } catch (err) {
      setError(err.message);
      onError(err);
    } finally {
      setSaving(false);
    }
  }

  async function remove() {
    if (!device) {
      return;
    }
    setSaving(true);
    setError('');
    try {
      const payload = await apiRequest(`device/?id=${device.id}`, { method: 'DELETE' });
      onSuccess(payload);
      deleteConfirm.close();
      await onDeleted();
    } catch (err) {
      setError(err.message);
      onError(err);
    } finally {
      setSaving(false);
    }
  }

  async function wake() {
    if (!device) {
      return;
    }
    setWaking(true);
    try {
      const payload = await apiRequest('device/wake/', {
        method: 'POST',
        body: { id: device.id },
      });
      onSuccess(payload);
    } catch (err) {
      onError(err);
    } finally {
      setWaking(false);
    }
  }

  async function startDetailedPortScan() {
    setPortScanLoading(true);
    setPortScanError('');
    try {
      const payload = await apiRequest('device/port-scan/', {
        method: 'POST',
        body: { device: device.id, ports: portScanSpec },
      });
      setPortScan(payload.data || null);
      onSuccess(payload);
    } catch (err) {
      setPortScanError(err.message);
      onError(err);
    } finally {
      setPortScanLoading(false);
    }
  }

  async function cancelDetailedPortScan() {
    if (!portScan) {
      return;
    }
    setPortScanLoading(true);
    setPortScanError('');
    try {
      const payload = await apiRequest('device/port-scan/cancel/', {
        method: 'POST',
        body: { id: portScan.id },
      });
      setPortScan(payload.data || portScan);
      onSuccess(payload);
    } catch (err) {
      setPortScanError(err.message);
      onError(err);
    } finally {
      setPortScanLoading(false);
    }
  }

  function cancelEditing() {
    populateForm(device);
    setError('');
    setEditing(false);
  }

  async function loadMoreEvents() {
    if (!hasNextActivityPage(eventPagination) || loadingMoreEvents) {
      return;
    }
    setLoadingMoreEvents(true);
    try {
      await loadDeviceEvents({ offset: eventPagination.next_offset, append: true });
    } catch (err) {
      onError(err);
    } finally {
      setLoadingMoreEvents(false);
    }
  }

  async function loadMoreDnsActivity() {
    if (!hasNextActivityPage(dnsPagination) || loadingMoreDnsActivity) {
      return;
    }
    setLoadingMoreDnsActivity(true);
    try {
      await loadDnsActivity({
        offset: dnsPagination.next_offset,
        append: true,
        quiet: true,
      });
    } catch (err) {
      onError(err);
    } finally {
      setLoadingMoreDnsActivity(false);
    }
  }

  const currentStatus = device ? deviceStatus(device) : null;
  const externalUrlCandidate = externalUrl.trim() || detectedWebUrl;
  const activeUrl = resolveExternalUrl(
    externalUrlCandidate,
    device?.ip || '',
    externalUrl.trim() ? externalUrlFollowDeviceIp : Boolean(detectedWebUrl)
  );

  return (
    <Paper className="device-detail-page" radius="md">
      <LoadingOverlay visible={loading} />
      <Stack gap="lg">
        <div className="device-detail-header">
          <Group className="device-detail-summary" gap="sm" align="flex-start" wrap="nowrap">
            <Tooltip label="Back to devices">
              <ActionIcon variant="subtle" color="gray" onClick={onBack} aria-label="Back to devices">
                <IconArrowLeft size={20} />
              </ActionIcon>
            </Tooltip>
            {device && (
              <span className="device-detail-icon">
                <DeviceIconStack device={device} size={26} />
              </span>
            )}
            <Box className="device-detail-identity">
              <Group className="device-detail-title-row" gap="xs" wrap="wrap">
                <Title order={2}>{device ? displayDeviceName(device) : 'Device'}</Title>
                {(device?.archived || device?.is_visitor) && (
                  <DeviceClassificationBadge device={device} compact />
                )}
                {device && <GatewayBadge device={device} compact />}
                {device && <RiskBadge device={device} compact />}
              </Group>
              {device && (
                <Stack className="device-detail-subtitle" gap={0}>
                  {String(device.hostname || '').trim() && (
                    <Text c="dimmed">{device.hostname}</Text>
                  )}
                  {String(device.vendor || '').trim() && (
                    <Text c="dimmed">{device.vendor}</Text>
                  )}
                  {!String(device.hostname || '').trim() && !String(device.vendor || '').trim() && (
                    <Text c="dimmed">-</Text>
                  )}
                </Stack>
              )}
              {currentStatus && (
                <Group gap="xs" mt={4}>
                  <span className={`status-dot ${currentStatus.dot}`} />
                  <Text size="sm">{currentStatus.label}</Text>
                  {device?.status_source_display && (
                    <Text size="sm" c="dimmed">via {device.status_source_display}</Text>
                  )}
                </Group>
              )}
            </Box>
          </Group>
          {device && (canEditDevices || canRunScans) && (
            editing && canEditDevices ? (
              <Group className="device-detail-actions" gap="xs" wrap="nowrap">
                <Button variant="default" onClick={cancelEditing} disabled={saving}>Cancel</Button>
                <Button leftSection={<IconDeviceFloppy size={18} />} onClick={save} loading={saving}>
                  Save
                </Button>
              </Group>
            ) : (
              <Group className="device-detail-actions" gap="xs" wrap="nowrap">
              {(canEditDevices || canRunScans) && !device.archived && device.status === 'online' && (
                <Button
                  variant="light"
                  leftSection={<IconRadar size={18} />}
                  onClick={portScanModal.open}
                >
                  Detailed port scan
                </Button>
              )}
              {canRunScans && !device.archived && (
                <Button
                  variant="light"
                  leftSection={<IconPower size={18} />}
                  loading={waking}
                  onClick={wake}
                >
                  Wake device
                </Button>
              )}
              {canEditDevices && (
                <>
                  <Button variant="default" leftSection={device.archived ? <IconArchiveOff size={18} /> : <IconArchive size={18} />}
                    onClick={archiveConfirm.open}>
                    {device.archived ? 'Restore device' : 'Archive device'}
                  </Button>
                  <Button leftSection={<IconEdit size={18} />} onClick={startEditing}>
                    Edit device
                  </Button>
                </>
              )}
              </Group>
            )
          )}
        </div>

        {error && (
          <Alert color="red" icon={<IconAlertCircle size={18} />}>
            {error}
          </Alert>
        )}
        {device && (
          <Tabs value={activeDeviceTab} onChange={setActiveDeviceTab} keepMounted={false}>
            <Tabs.List>
              <Tabs.Tab value="overview" leftSection={<IconNetwork size={17} />}>Overview</Tabs.Tab>
              {!editing && (
                <Tabs.Tab value="history" leftSection={<IconHistory size={17} />}>History</Tabs.Tab>
              )}
              {!editing && dnsActivityEnabled && (
                <Tabs.Tab value="dns" leftSection={<IconWorldSearch size={17} />}>DNS activity</Tabs.Tab>
              )}
            </Tabs.List>

            <Tabs.Panel value="overview" pt="lg">
              {!editing && device.homebox_link && (
                <Button component="a" href={device.homebox_link} target="_blank" rel="noopener noreferrer"
                  variant="default" leftSection={<IconExternalLink size={18} />} mb="md">
                  Open in HomeBox
                </Button>
              )}
              {editing ? (
                <Stack gap="lg">
                  <SimpleGrid cols={{ base: 1, md: 2 }}>
                    <DeviceField label="Name" value={name} editable required onChange={setName} />
                    <RoomField
                      value={room}
                      onChange={setRoom}
                      roomOptions={buildRoomOptions([], room).concat(
                        roomOptions.filter((option) => option.value !== room)
                      )}
                    />
                    <Box className="device-field editable">
                      <Text size="xs" c="dimmed">Role</Text>
                      <Select
                        classNames={{ input: 'device-field-input' }}
                        data={deviceRoleOptions.map((value) => ({ value, label: formatRoleLabel(value) }))}
                        value={role}
                        onChange={(value) => setRole(value || 'device')}
                      />
                    </Box>
                    <Stack gap="xs">
                      <TextInput
                        label="External link"
                        placeholder="https://192.168.0.20"
                        value={externalUrl}
                        error={!validExternalUrl(externalUrl) ? 'Enter a valid HTTP or HTTPS URL without embedded credentials.' : null}
                        onChange={(event) => {
                          const nextExternalUrl = event.currentTarget.value;
                          setExternalUrl(nextExternalUrl);
                          if (!nextExternalUrl.trim()) {
                            setExternalUrlFollowDeviceIp(false);
                          }
                        }}
                      />
                      {detectedWebUrl && !externalUrl.trim() && (
                        <Button
                          variant="subtle"
                          size="compact-sm"
                          w="fit-content"
                          onClick={() => {
                            setExternalUrl(detectedWebUrl);
                            setExternalUrlFollowDeviceIp(true);
                          }}
                        >
                          Use detected web interface
                        </Button>
                      )}
                      <Switch
                        label="Follow device IP"
                        description="Replace only the link hostname when this device's IPv4 address changes."
                        checked={externalUrlFollowDeviceIp}
                        disabled={!externalUrlUsesIPv4(externalUrl)}
                        onChange={(event) => setExternalUrlFollowDeviceIp(event.currentTarget.checked)}
                      />
                      {externalUrlFollowDeviceIp
                        && activeUrl
                        && activeUrl !== externalUrl.trim() && (
                        <Text size="xs" c="dimmed" className="wrap-text">
                          Opens: {activeUrl}
                        </Text>
                      )}
                    </Stack>
                    {device.homebox_available ? (
                      <HomeBoxItemPicker value={homeboxItemId} onChange={setHomeboxItemId} />
                    ) : homeboxItemId && (
                      <Button variant="default" leftSection={<IconX size={16} />} onClick={() => setHomeboxItemId(null)}>Unlink HomeBox item</Button>
                    )}
                  </SimpleGrid>
                  <SimpleGrid cols={{ base: 1, md: 2 }}>
                    <DeviceIconPicker value={icon} onChange={setIcon} />
                    <DeviceIconPicker label="Secondary icon" value={secondaryIcon} onChange={setSecondaryIcon} />
                  </SimpleGrid>
                  <Textarea
                    label="Comments"
                    placeholder="Add notes about this device"
                    value={comments}
                    onChange={(event) => setComments(event.currentTarget.value)}
                    autosize
                    minRows={3}
                    maxRows={8}
                  />
                  <Divider label="Presence notifications" labelPosition="left" />
                  <Box>
                    <Text size="sm" c="dimmed" mb="sm">
                      Override the global Online and Offline rules for this device. Quiet hours and
                      configured notification channels still apply.
                    </Text>
                    <SimpleGrid cols={{ base: 1, md: 2 }}>
                      <Select
                        label="When device comes online"
                        description="Controls Online notifications for this device."
                        data={deviceNotificationPreferenceOptions}
                        value={onlineNotificationPreference}
                        onChange={(value) => setOnlineNotificationPreference(value || 'inherit')}
                      />
                      <Select
                        label="When device goes offline"
                        description="Controls Offline notifications for this device."
                        data={deviceNotificationPreferenceOptions}
                        value={offlineNotificationPreference}
                        onChange={(value) => setOfflineNotificationPreference(value || 'inherit')}
                      />
                    </SimpleGrid>
                  </Box>
                  <Divider label="Presence expectations" labelPosition="left" />
                  <Box>
                    <Text size="sm" c="dimmed" mb="sm">
                      Decide when a prolonged absence should appear under Needs Attention.
                      Visitor devices are always excluded.
                    </Text>
                    <SimpleGrid cols={{ base: 1, md: 2 }}>
                      <Select
                        label="Presence expectation"
                        description="Automatic allows more time for portable devices."
                        data={devicePresenceExpectationOptions}
                        value={presenceExpectation}
                        onChange={(value) => {
                          const nextValue = value || 'automatic';
                          setPresenceExpectation(nextValue);
                          if (!['always', 'occasional'].includes(nextValue)) {
                            setOfflineAttentionAfterDays('');
                          }
                        }}
                      />
                      {['always', 'occasional'].includes(presenceExpectation) && (
                        <NumberInput
                          label="Alert after days offline"
                          description={`Leave empty to use ${presenceExpectation === 'occasional' ? 21 : 7} days.`}
                          placeholder={presenceExpectation === 'occasional' ? '21' : '7'}
                          min={1}
                          max={3650}
                          allowDecimal={false}
                          value={offlineAttentionAfterDays}
                          onChange={setOfflineAttentionAfterDays}
                        />
                      )}
                    </SimpleGrid>
                    {presenceExpectation === 'automatic' && (
                      <Text size="xs" c="dimmed" mt="sm">
                        Uses 21 days for phones, tablets, watches, and laptops; 7 days for other devices.
                      </Text>
                    )}
                    {presenceExpectation === 'never' && (
                      <Text size="xs" c="dimmed" mt="sm">
                        This device will not need attention because it has been offline for a long time.
                      </Text>
                    )}
                  </Box>
                  <Group align="flex-start">
                    <Switch
                      label="Known device"
                      checked={known}
                      onChange={(event) => {
                        const nextKnown = event.currentTarget.checked;
                        setKnown(nextKnown);
                        if (!nextKnown) {
                          setIsVisitor(false);
                          setAttentionAcknowledged(false);
                        }
                      }}
                    />
                    <Switch
                      label="Visitor device"
                      description="Keeps this device recognized while treating its presence as temporary."
                      checked={isVisitor}
                      onChange={(event) => {
                        const nextVisitor = event.currentTarget.checked;
                        setIsVisitor(nextVisitor);
                        if (nextVisitor) {
                          setKnown(true);
                        }
                      }}
                    />
                    <Switch
                      label="This device does not need attention"
                      description="Acknowledges the current risk. Risk changes will require attention again."
                      checked={attentionAcknowledged}
                      disabled={!known || (!device.needs_attention && !device.attention_acknowledged)}
                      onChange={(event) => setAttentionAcknowledged(event.currentTarget.checked)}
                    />
                  </Group>
                  {canEditDevices && <Group>
                    <Button
                      color="red"
                      variant="light"
                      leftSection={<IconTrash size={18} />}
                      onClick={deleteConfirm.open}
                    >
                      Delete device
                    </Button>
                  </Group>}
                </Stack>
              ) : (
                <Stack gap="xl">
                  <SimpleGrid cols={{ base: 1, md: 2 }} spacing="xl">
                    <section className="device-detail-section">
                      <Title order={4}>Identity</Title>
                      <SimpleGrid cols={{ base: 1, sm: 2 }} mt="md">
                        <DeviceField label="Vendor" value={device.vendor || '-'} />
                        <DeviceField label="Hostname" value={device.hostname || '-'} />
                        <DeviceField label="MAC address" value={device.mac || '-'} />
                      </SimpleGrid>
                      <IdentityConfidenceField device={device} />
                    </section>
                    <section className="device-detail-section">
                      <Title order={4}>Network</Title>
                      <SimpleGrid cols={{ base: 1, sm: 2 }} mt="md">
                        <DeviceField label="IP address" value={device.ip || '-'} />
                        <DeviceField label="Last port scan" value={formatDate(device.last_port_scan, timeZone)} />
                        <DeviceField label="Missed scans" value={String(device.missed_scans ?? 0)} />
                        <DeviceField label="Status source" value={device.status_source_display || '-'} />
                      </SimpleGrid>
                      <Text size="xs" c="dimmed" mt="md">Open ports</Text>
                      <Group gap={6} mt={6}>
                        {(device.open_ports || []).length ? (
                          device.open_ports.map((port) => (
                            <PortGuidanceBadge key={`${port.protocol}-${port.port}`} port={port} />
                          ))
                        ) : <Text size="sm">-</Text>}
                      </Group>
                    </section>
                  </SimpleGrid>

                  <Divider />
                  <SimpleGrid cols={{ base: 1, md: 2 }} spacing="xl">
                    <section className="device-detail-section">
                      <Title order={4}>Profile</Title>
                      <SimpleGrid cols={{ base: 1, sm: 2 }} mt="md">
                        <DeviceField label="Room" value={device.room || 'Unassigned'} />
                        <DeviceField label="Role" value={formatRoleLabel(device.role)} />
                        <DeviceField
                          label="Online notifications"
                          value={formatDeviceNotificationPreference(
                            device.online_notification_preference
                          )}
                        />
                        <DeviceField
                          label="Offline notifications"
                          value={formatDeviceNotificationPreference(
                            device.offline_notification_preference
                          )}
                        />
                        <DeviceField
                          label="Presence expectation"
                          value={formatDevicePresenceExpectation(device.presence_expectation)}
                        />
                        <DeviceField
                          label="Absence attention"
                          value={formatOfflineAttention(device)}
                        />
                        <DeviceField label="First seen" value={formatDate(device.firstseen, timeZone)} />
                        <DeviceField label="Last seen" value={formatDate(device.lastseen, timeZone)} />
                      </SimpleGrid>
                    </section>
                    <section className="device-detail-section">
                      <Title order={4}>Notes and access</Title>
                      <Text size="sm" mt="md" className="wrap-text">
                        {device.comments || 'No notes added.'}
                      </Text>
                      {detectingWebUrl && (
                        <Group gap="xs" mt="md"><Loader size="xs" /><Text size="sm" c="dimmed">Checking web interface...</Text></Group>
                      )}
                      {activeUrl && validExternalUrl(activeUrl) && (
                        <Button
                          component="a"
                          href={activeUrl}
                          target="_blank"
                          rel="noopener noreferrer"
                          variant="light"
                          mt="md"
                          leftSection={<IconArrowUpRight size={17} />}
                        >
                          Open device interface
                        </Button>
                      )}
                    </section>
                  </SimpleGrid>
                  {currentStatus?.reason && <Alert color="gray">{currentStatus.reason}</Alert>}
                </Stack>
              )}
            </Tabs.Panel>

            <Tabs.Panel value="history" pt="lg">
              <Stack gap="md">
                <section className="device-availability-section">
                  <Group justify="space-between" align="flex-start" wrap="wrap" gap="md">
                    <Box>
                      <Title order={4}>Availability</Title>
                      <Text size="sm" c="dimmed">
                        Online and offline time from retained device status history.
                      </Text>
                    </Box>
                    <SegmentedControl
                      value={availabilityPeriod}
                      onChange={setAvailabilityPeriod}
                      data={[
                        { value: 'day', label: 'Day' },
                        { value: 'week', label: 'Week' },
                        { value: 'month', label: 'Month' },
                        { value: 'year', label: 'Year' },
                      ]}
                    />
                  </Group>

                  <Box pos="relative" mt="lg" mih={116}>
                    <LoadingOverlay visible={loadingAvailability} />
                    {availability && (
                      <Stack gap="md">
                        <SimpleGrid cols={{ base: 1, xs: 3 }}>
                          <SummaryMetric
                            label="Availability"
                            value={
                              availability.availability_percent == null
                                ? 'No data'
                                : `${availability.availability_percent}%`
                            }
                          />
                          <SummaryMetric
                            label="Online time"
                            value={formatAvailabilityDuration(availability.online_seconds)}
                          />
                          <SummaryMetric
                            label="Status changes"
                            value={Number(availability.status_changes || 0).toLocaleString()}
                          />
                        </SimpleGrid>

                        <div className="availability-timeline" aria-label="Device availability timeline">
                          {(availability.segments || []).map((segment, index) => (
                            <Tooltip
                              key={`${segment.started_at}-${index}`}
                              label={`${formatRoleLabel(segment.status)}: ${formatDate(segment.started_at, timeZone)} to ${formatDate(segment.ended_at, timeZone)}`}
                            >
                              <span
                                className={`availability-segment ${segment.status}`}
                                style={{ flexGrow: Math.max(Number(segment.duration_seconds || 0), 1) }}
                              />
                            </Tooltip>
                          ))}
                        </div>
                        <Group justify="space-between" wrap="nowrap">
                          <Text size="xs" c="dimmed">
                            {availability.period === 'day'
                              ? '24 hours ago'
                              : availability.period === 'week'
                                ? '7 days ago'
                              : availability.period === 'month'
                                ? '30 days ago'
                                : '1 year ago'}
                          </Text>
                          <Text size="xs" c="dimmed">Now</Text>
                        </Group>
                        <Group gap="md" wrap="wrap" className="availability-legend">
                          <Text size="xs"><span className="availability-key online" />Online</Text>
                          <Text size="xs"><span className="availability-key offline" />Offline</Text>
                          <Text size="xs"><span className="availability-key unknown" />No data</Text>
                        </Group>
                        {Number(availability.coverage_percent || 0) < 100 && (
                          <Text size="xs" c="dimmed">
                            History coverage: {availability.coverage_percent}%. Missing time is not included in the availability calculation.
                          </Text>
                        )}
                      </Stack>
                    )}
                  </Box>
                </section>

                <Divider />
                <Group justify="space-between">
                  <Box>
                    <Title order={4}>Device history</Title>
                    <Text size="sm" c="dimmed">{activityRecordLabel(eventPagination, events.length)}</Text>
                  </Box>
                </Group>
                <ScrollArea.Autosize mah={520} type="auto" className="activity-table-scroll">
                  <Table striped highlightOnHover verticalSpacing="sm">
                    <Table.Thead>
                      <Table.Tr>
                        <Table.Th>Time</Table.Th>
                        <Table.Th>Event</Table.Th>
                        <Table.Th>Details</Table.Th>
                      </Table.Tr>
                    </Table.Thead>
                    <Table.Tbody>
                      {events.map((event) => (
                        <Table.Tr key={event.id}>
                          <Table.Td className="device-history-time">{formatDate(event.created_at, timeZone)}</Table.Td>
                          <Table.Td><Badge variant="light">{event.event_type_display || formatRoleLabel(event.event_type)}</Badge></Table.Td>
                          <Table.Td>{event.message || '-'}</Table.Td>
                        </Table.Tr>
                      ))}
                    </Table.Tbody>
                  </Table>
                </ScrollArea.Autosize>
                {!events.length && <Text c="dimmed">No history recorded for this device.</Text>}
                {hasNextActivityPage(eventPagination) && (
                  <Group justify="center">
                    <Button variant="default" onClick={loadMoreEvents} loading={loadingMoreEvents}>
                      Load older events
                    </Button>
                  </Group>
                )}
              </Stack>
            </Tabs.Panel>

            {dnsActivityEnabled && <Tabs.Panel value="dns" pt="lg">
              <Stack gap="md">
                <Group justify="space-between" align="flex-start" wrap="wrap">
                  <Box>
                    <Title order={4}>DNS activity</Title>
                    <Text size="sm" c="dimmed">
                      Aggregated {dnsIntegration?.provider_name || 'DNS provider'} destinations for this device.
                    </Text>
                  </Box>
                  {dnsIntegration?.last_sync_at && (
                    <Text size="sm" c="dimmed">
                      Last synced {formatDate(dnsIntegration.last_sync_at, timeZone)}
                    </Text>
                  )}
                </Group>

                {dnsIntegration && !dnsIntegration.configured && (
                  <Alert color="blue" icon={<IconWorldSearch size={18} />}>
                    Configure a DNS provider in Settings to collect DNS activity.
                  </Alert>
                )}
                {dnsIntegration?.configured && !dnsIntegration.enabled && (
                  <Alert color="gray">DNS activity synchronization is currently disabled.</Alert>
                )}
                {dnsIntegration?.last_error && (
                  <Alert color="red" icon={<IconAlertCircle size={18} />}>
                    Last sync failed: {dnsIntegration.last_error}
                  </Alert>
                )}

                <SimpleGrid cols={{ base: 1, sm: 3 }}>
                  <DeviceField
                    label="Unique domains"
                    value={Number(dnsSummary?.unique_domains || 0).toLocaleString()}
                  />
                  <DeviceField
                    label="DNS queries"
                    value={Number(dnsSummary?.total_queries || 0).toLocaleString()}
                  />
                  <DeviceField
                    label="Blocked queries"
                    value={Number(dnsSummary?.blocked_queries || 0).toLocaleString()}
                  />
                </SimpleGrid>

                <Group align="flex-end" wrap="wrap">
                  <TextInput
                    label="Search domains"
                    placeholder="api.example.com"
                    value={dnsSearch}
                    onChange={(event) => setDnsSearch(event.currentTarget.value)}
                    leftSection={<IconSearch size={16} />}
                    style={{ flex: '1 1 260px' }}
                  />
                  <SegmentedControl
                    value={dnsFilter}
                    onChange={setDnsFilter}
                    data={[
                      { value: 'all', label: 'All' },
                      { value: 'allowed', label: 'Allowed' },
                      { value: 'blocked', label: 'Blocked' },
                    ]}
                  />
                  <Select
                    label="Sort by"
                    value={dnsOrdering}
                    onChange={(value) => setDnsOrdering(value || '-last_seen')}
                    data={[
                      { value: '-last_seen', label: 'Recently seen' },
                      { value: '-query_count', label: 'Most queries' },
                      { value: '-blocked_count', label: 'Most blocked' },
                      { value: 'domain', label: 'Domain name' },
                    ]}
                    w={180}
                  />
                </Group>

                <Box pos="relative">
                  <LoadingOverlay visible={loadingDnsActivity} />
                  <ScrollArea.Autosize mah={520} type="auto" className="activity-table-scroll">
                    <Table striped highlightOnHover verticalSpacing="sm">
                      <Table.Thead>
                        <Table.Tr>
                          <Table.Th>Domain</Table.Th>
                          <Table.Th>Type</Table.Th>
                          <Table.Th>Queries</Table.Th>
                          <Table.Th>Blocked</Table.Th>
                          <Table.Th>Last seen</Table.Th>
                        </Table.Tr>
                      </Table.Thead>
                      <Table.Tbody>
                        {dnsActivity.map((activity) => (
                          <Table.Tr key={activity.id}>
                            <Table.Td>
                              <Text size="sm" fw={600} className="wrap-text">
                                {activity.domain}
                              </Text>
                              {activity.last_service_name && (
                                <Text size="xs" c="dimmed">{activity.last_service_name}</Text>
                              )}
                            </Table.Td>
                            <Table.Td>{activity.query_type || '-'}</Table.Td>
                            <Table.Td>{Number(activity.query_count || 0).toLocaleString()}</Table.Td>
                            <Table.Td>
                              {activity.blocked_count > 0 ? (
                                <Tooltip label={activity.last_reason || `Blocked by ${dnsIntegration?.provider_name || 'DNS provider'}`}>
                                  <Badge color="red" variant="light">
                                    {Number(activity.blocked_count).toLocaleString()}
                                  </Badge>
                                </Tooltip>
                              ) : (
                                <Text size="sm" c="dimmed">0</Text>
                              )}
                            </Table.Td>
                            <Table.Td className="device-history-time">
                              {formatDate(activity.last_seen, timeZone)}
                            </Table.Td>
                          </Table.Tr>
                        ))}
                      </Table.Tbody>
                    </Table>
                  </ScrollArea.Autosize>
                </Box>
                {!loadingDnsActivity && !dnsActivity.length && (
                  <Text c="dimmed">No DNS activity recorded for this device.</Text>
                )}
                {hasNextActivityPage(dnsPagination) && (
                  <Group justify="center">
                    <Button
                      variant="default"
                      onClick={loadMoreDnsActivity}
                      loading={loadingMoreDnsActivity}
                    >
                      Load more domains
                    </Button>
                  </Group>
                )}
              </Stack>
            </Tabs.Panel>}
          </Tabs>
        )}
      </Stack>
      <Modal
        opened={deleteConfirmOpened}
        onClose={deleteConfirm.close}
        title="Delete device"
        centered
      >
        <Stack>
          <Text>Are you sure you want to delete this device?</Text>
          <Text size="sm" c="dimmed">
            {device?.name} will be removed from the inventory.
          </Text>
          <Group justify="flex-end">
            <Button variant="default" onClick={deleteConfirm.close}>
              Cancel
            </Button>
            <Button
              color="red"
              leftSection={<IconTrash size={18} />}
              onClick={remove}
              loading={saving}
            >
              Delete
            </Button>
          </Group>
        </Stack>
      </Modal>
      <Modal opened={archiveConfirmOpened} onClose={archiveConfirm.close}
        title={device?.archived ? 'Restore device' : 'Archive device'} centered>
        <Stack>
          <Text>{device?.archived
            ? `Restore ${device.name} to the active inventory?`
            : `Archive ${device?.name}? Its history will be kept. It will return automatically if detected by a future scan.`}</Text>
          <Group justify="flex-end">
            <Button variant="default" onClick={archiveConfirm.close} disabled={saving}>Cancel</Button>
            <Button leftSection={device?.archived ? <IconArchiveOff size={18} /> : <IconArchive size={18} />}
              onClick={changeArchiveState} loading={saving}>{device?.archived ? 'Restore' : 'Archive'}</Button>
          </Group>
        </Stack>
      </Modal>
      <Modal
        opened={portScanOpened}
        onClose={portScanModal.close}
        title="Detailed port scan"
        centered
        size="lg"
      >
        <Stack gap="md">
          <Text size="sm" c="dimmed">
            Scan up to 1,024 TCP ports on {device?.name}. Use commas to combine
            individual ports and ranges.
          </Text>
          <TextInput
            label="TCP ports"
            description="Examples: 1-1024 or 22, 80, 443, 8000-8100"
            value={portScanSpec}
            onChange={(event) => setPortScanSpec(event.currentTarget.value)}
            disabled={portScan?.status === 'queued' || portScan?.status === 'running'}
            error={portScanError || null}
          />

          {portScan && (
            <Paper withBorder p="md" radius="sm">
              <Stack gap="sm">
                <Group justify="space-between">
                  <Group gap="xs">
                    <Text fw={600}>Scan status</Text>
                    <Badge
                      color={
                        portScan.status === 'success' ? 'green'
                          : portScan.status === 'failed' ? 'red'
                            : portScan.status === 'cancelled' ? 'gray'
                              : 'blue'
                      }
                      variant="light"
                    >
                      {formatRoleLabel(portScan.status)}
                    </Badge>
                  </Group>
                  <Text size="sm" c="dimmed">
                    {portScan.scanned_ports} / {portScan.total_ports} ports
                  </Text>
                </Group>
                <Progress
                  value={portScan.progress_percent || 0}
                  animated={portScan.status === 'running'}
                />
                <Box>
                  <Text size="xs" c="dimmed">Open ports found</Text>
                  <Group gap={6} mt={6}>
                    {portScan.open_ports?.length ? (
                      portScan.open_ports.map((port) => (
                        <PortGuidanceBadge key={`${port.protocol}-${port.port}`} port={port} />
                      ))
                    ) : <Text size="sm">None yet</Text>}
                  </Group>
                </Box>
                {portScan.error && (
                  <Alert color="red" icon={<IconAlertCircle size={18} />}>
                    {portScan.error}
                  </Alert>
                )}
                {portScan.cancel_requested && portScan.status === 'running' && (
                  <Text size="sm" c="dimmed">Stopping after the current port...</Text>
                )}
              </Stack>
            </Paper>
          )}

          <Group justify="flex-end">
            {(portScan?.status === 'queued' || portScan?.status === 'running') ? (
              <Button
                color="red"
                variant="light"
                leftSection={<IconPlayerStop size={18} />}
                onClick={cancelDetailedPortScan}
                loading={portScanLoading}
                disabled={portScan.cancel_requested}
              >
                Cancel scan
              </Button>
            ) : (
              <Button
                leftSection={<IconRadar size={18} />}
                onClick={startDetailedPortScan}
                loading={portScanLoading}
                disabled={!portScanSpec.trim()}
              >
                Start scan
              </Button>
            )}
          </Group>
        </Stack>
      </Modal>
    </Paper>
  );
}
