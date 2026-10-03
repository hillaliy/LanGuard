import { useEffect, useState } from 'react';
import {
  ActionIcon, Autocomplete, Badge, Box, Button, Group, Select, Stack, Text,
  TextInput, Tooltip, UnstyledButton,
} from '@mantine/core';
import { IconChevronDown, IconX } from '@tabler/icons-react';

import { apiRequest } from '../api';
import {
  deviceIconOptions,
  normalizeDeviceIcon,
} from '../components/DeviceIconStack';
import { formatRoleLabel } from '../utils/device';

export const deviceRoleOptions = [
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

export const deviceNotificationPreferenceOptions = [
  { value: 'inherit', label: 'Use global setting' },
  { value: 'always', label: 'Always notify' },
  { value: 'never', label: 'Never notify' },
];

export function formatDeviceNotificationPreference(value) {
  return deviceNotificationPreferenceOptions.find((option) => option.value === value)?.label
    || 'Use global setting';
}

export const devicePresenceExpectationOptions = [
  { value: 'automatic', label: 'Automatic' },
  { value: 'always', label: 'Always expected' },
  { value: 'occasional', label: 'Occasionally present' },
  { value: 'never', label: 'Do not monitor absence' },
];

export function formatDevicePresenceExpectation(value) {
  return devicePresenceExpectationOptions.find((option) => option.value === value)?.label
    || 'Automatic';
}

export function formatOfflineAttention(device) {
  const days = device?.offline_attention_effective_days;
  return Number.isInteger(days) ? `After ${days} days offline` : 'Disabled';
}

export function formatAvailabilityDuration(seconds) {
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

export function DeviceField({ label, value, editable = false, required = false, onChange }) {
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

export function IdentityConfidenceField({ device }) {
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

export function RoomField({ value, onChange, roomOptions = [] }) {
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

export function DeviceIconPicker({ value, onChange, label = 'Icon' }) {
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

export function HomeBoxItemPicker({ value, onChange }) {
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
        const payload = await apiRequest('integrations/homebox/items/', {
          params: { q: query, page },
        });
        if (cancelled) return;
        setItems((old) => {
          const combined = page === 1 ? payload.data.items : [...old, ...payload.data.items];
          return [...new Map(combined.map((item) => [item.value, item])).values()];
        });
        setHasMore(payload.data.has_more);
        setError('');
      } catch (err) {
        if (!cancelled) {
          setError(err.message);
          setHasMore(false);
        }
      } finally {
        if (!cancelled) setBusy(false);
      }
    }, 300);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [query, page]);

  const options = value && !items.some((item) => item.value === value)
    ? [{ value, label: value }, ...items]
    : items;

  return (
    <Stack gap="xs">
      <Select
        label="HomeBox item"
        placeholder="Search by name, description, or asset ID"
        searchable
        clearable
        data={options}
        value={value || null}
        onChange={onChange}
        searchValue={query}
        onSearchChange={(next) => {
          setQuery(next);
          setPage(1);
        }}
        filter={({ options: available }) => available}
        nothingFoundMessage={busy ? 'Loading...' : 'No items found'}
        error={error}
      />
      {hasMore && (
        <Button
          variant="subtle"
          size="xs"
          leftSection={<IconChevronDown size={16} />}
          loading={busy}
          onClick={() => setPage((old) => old + 1)}
        >
          Load more
        </Button>
      )}
    </Stack>
  );
}
