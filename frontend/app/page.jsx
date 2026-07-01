'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import {
  ActionIcon,
  Alert,
  Badge,
  Box,
  Button,
  Card,
  Container,
  Divider,
  Group,
  Image,
  LoadingOverlay,
  Modal,
  NumberInput,
  Pagination,
  Paper,
  PasswordInput,
  Select,
  SegmentedControl,
  SimpleGrid,
  Stack,
  Switch,
  Table,
  Tabs,
  Text,
  TextInput,
  Title,
  Tooltip,
  useMantineColorScheme,
} from '@mantine/core';
import { useDisclosure } from '@mantine/hooks';
import { notifications } from '@mantine/notifications';
import {
  IconAlertCircle,
  IconAirConditioning,
  IconArrowsSort,
  IconBell,
  IconBlind,
  IconBulb,
  IconCast,
  IconClock,
  IconDeviceCctv,
  IconDeviceDesktop,
  IconDeviceLaptop,
  IconDeviceMobile,
  IconDeviceSpeaker,
  IconDeviceTablet,
  IconDeviceTv,
  IconHistory,
  IconLock,
  IconLogout,
  IconMoon,
  IconNetwork,
  IconPlugConnected,
  IconPrinter,
  IconQuestionMark,
  IconRefresh,
  IconRouter,
  IconSearch,
  IconServer,
  IconSettings,
  IconShieldCheck,
  IconShieldLock,
  IconSun,
  IconTemperature,
  IconTrash,
  IconUserPlus,
  IconUserMinus,
  IconUserEdit,
  IconVacuumCleaner,
  IconWifi,
  IconWifiOff,
  IconX,
} from '@tabler/icons-react';
import {
  apiRequest,
  clearStoredUser,
  getAdminUrl,
  getStoredUser,
  storeUser,
} from './api';
import { APP_VERSION, CHANGELOG_ENTRIES } from './version';

const changelogSeenStorageKey = 'languard_changelog_seen_version';
const versionCheckFallbackInterval = 6 * 60 * 60 * 1000;

const eventTypeOptions = [
  { value: 'new_device', label: 'New devices' },
  { value: 'device_online', label: 'Online events' },
  { value: 'device_offline', label: 'Offline events' },
  { value: 'port_opened', label: 'Opened ports' },
  { value: 'port_closed', label: 'Closed ports' },
];

const devicePageSizeOptions = ['10', '25', '50', '100'];

const deviceStatusOptions = [
  { value: 'online', label: 'Online' },
  { value: 'offline', label: 'Offline' },
  { value: 'new', label: 'New devices' },
];

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

function showSuccessNotification(title, message) {
  notifications.show({
    title,
    message,
    color: 'teal',
    icon: <IconShieldCheck size={18} />,
  });
}

function showErrorNotification(title, message) {
  notifications.show({
    title,
    message,
    color: 'red',
    icon: <IconAlertCircle size={18} />,
  });
}

function parseVersionParts(version) {
  return String(version || '')
    .replace(/^v/i, '')
    .split('.')
    .map((part) => Number.parseInt(part, 10) || 0);
}

function isNewerVersion(candidate, current) {
  const candidateParts = parseVersionParts(candidate);
  const currentParts = parseVersionParts(current);
  const length = Math.max(candidateParts.length, currentParts.length);

  for (let index = 0; index < length; index += 1) {
    const candidatePart = candidateParts[index] || 0;
    const currentPart = currentParts[index] || 0;
    if (candidatePart > currentPart) {
      return true;
    }
    if (candidatePart < currentPart) {
      return false;
    }
  }

  return false;
}

function useHydrated() {
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    setHydrated(true);
  }, []);

  return hydrated;
}

const deviceIconOptions = [
  { value: 'unknown', label: 'Unknown', icon: IconQuestionMark },
  { value: 'desktop', label: 'Desktop', icon: IconDeviceDesktop },
  { value: 'router', label: 'Router', icon: IconRouter },
  { value: 'phone', label: 'Phone', icon: IconDeviceMobile },
  { value: 'tablet', label: 'Tablet', icon: IconDeviceTablet },
  { value: 'laptop', label: 'Laptop', icon: IconDeviceLaptop },
  { value: 'tv', label: 'TV', icon: IconDeviceTv },
  { value: 'streamer', label: 'Streamer', icon: IconCast },
  { value: 'security-camera', label: 'Security camera', icon: IconDeviceCctv },
  { value: 'shutter', label: 'Shutter', icon: IconBlind },
  { value: 'light', label: 'Light', icon: IconBulb },
  { value: 'air-conditioner', label: 'Air conditioner', icon: IconAirConditioning },
  { value: 'thermostat', label: 'Thermostat', icon: IconTemperature },
  { value: 'speaker', label: 'Speaker', icon: IconDeviceSpeaker },
  { value: 'printer', label: 'Printer', icon: IconPrinter },
  { value: 'lock', label: 'Lock', icon: IconLock },
  { value: 'robot-vacuum', label: 'Robot vacuum', icon: IconVacuumCleaner },
  { value: 'server', label: 'Server', icon: IconServer },
];

function normalizeDeviceIcon(value) {
  const aliases = {
    plus: 'unknown',
    device: 'desktop',
    computer: 'desktop',
    mobile: 'phone',
    ipad: 'tablet',
    pad: 'tablet',
    television: 'tv',
    cast: 'streamer',
    streaming: 'streamer',
    camera: 'security-camera',
    cctv: 'security-camera',
    blind: 'shutter',
    blinds: 'shutter',
    shade: 'shutter',
    curtain: 'shutter',
    bulb: 'light',
    aircon: 'air-conditioner',
    ac: 'air-conditioner',
    hvac: 'air-conditioner',
    'thermometer-snow': 'thermostat',
    temperature: 'thermostat',
    audio: 'speaker',
    security: 'lock',
    smartlock: 'lock',
    'smart-lock': 'lock',
    vacuum: 'robot-vacuum',
    roomba: 'robot-vacuum',
    robot: 'robot-vacuum',
    'vacuum-cleaner': 'robot-vacuum',
    nas: 'server',
  };
  const normalized = aliases[value] || value || 'unknown';
  return deviceIconOptions.some((option) => option.value === normalized)
    ? normalized
    : 'unknown';
}

function DeviceIcon({ value, size = 18 }) {
  const normalized = normalizeDeviceIcon(value);
  const option =
    deviceIconOptions.find((item) => item.value === normalized) ||
    deviceIconOptions[0];
  const Icon = option.icon;
  return <Icon size={size} stroke={1.8} />;
}

function sortableOrdering(field, currentOrdering) {
  if (currentOrdering === field) {
    return `-${field}`;
  }
  if (currentOrdering === `-${field}`) {
    return '';
  }
  return field;
}

function SortableHeader({ field, label, ordering, onChange, className }) {
  const active = ordering === field || ordering === `-${field}`;
  const direction = ordering === field ? 'asc' : ordering === `-${field}` ? 'desc' : '';
  const title = active
    ? `${label} sorted ${direction === 'asc' ? 'ascending' : 'descending'}`
    : `Sort by ${label}`;

  return (
    <Table.Th className={className}>
      <button
        type="button"
        className={`sortable-header ${active ? 'active' : ''}`}
        onClick={() => onChange(sortableOrdering(field, ordering))}
        aria-label={title}
      >
        <span>{label}</span>
        <IconArrowsSort
          size={15}
          stroke={1.9}
          className={direction ? `sort-icon ${direction}` : 'sort-icon'}
        />
      </button>
    </Table.Th>
  );
}

function ColorSchemeControl() {
  const hydrated = useHydrated();
  const { colorScheme, setColorScheme } = useMantineColorScheme();

  return (
    <SegmentedControl
      className="color-scheme-control"
      size="xs"
      value={hydrated ? colorScheme : 'auto'}
      onChange={setColorScheme}
      data={[
        {
          value: 'light',
          label: (
            <Group component="span" gap={4} wrap="nowrap">
              <IconSun size={14} />
              <Box component="span" visibleFrom="lg">Light</Box>
            </Group>
          ),
        },
        {
          value: 'dark',
          label: (
            <Group component="span" gap={4} wrap="nowrap">
              <IconMoon size={14} />
              <Box component="span" visibleFrom="lg">Dark</Box>
            </Group>
          ),
        },
        {
          value: 'auto',
          label: (
            <Group component="span" gap={4} wrap="nowrap">
              <IconDeviceDesktop size={14} />
              <Box component="span" visibleFrom="lg">Auto</Box>
            </Group>
          ),
        },
      ]}
    />
  );
}

function formatDate(value) {
  if (!value) {
    return '-';
  }
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value));
}

function formatTopbarDate(value) {
  return new Intl.DateTimeFormat(undefined, {
    weekday: 'short',
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  }).format(value);
}

function formatTopbarTime(value) {
  return new Intl.DateTimeFormat(undefined, {
    hour: '2-digit',
    minute: '2-digit',
  }).format(value);
}

function userDisplayName(user) {
  const fullName = [user?.first_name, user?.last_name].filter(Boolean).join(' ').trim();
  return fullName || user?.username || 'User';
}

function userInitials(user) {
  const displayName = userDisplayName(user);
  const parts = displayName.split(/\s+/).filter(Boolean);
  const nameInitials =
    parts.length > 1
      ? `${parts[0][0]}${parts[parts.length - 1][0]}`
      : '';

  if (nameInitials) {
    return nameInitials.toUpperCase();
  }

  return (user?.username || 'U').trim().slice(0, 2).toUpperCase();
}

function capitalizeName(value) {
  return (value || '')
    .trim()
    .split(/\s+/)
    .filter(Boolean)
    .map((word) => word
      .split('-')
      .map((part) => part ? `${part[0].toUpperCase()}${part.slice(1).toLowerCase()}` : part)
      .join('-'))
    .join(' ');
}

function AuthScreen({ onLogin }) {
  const [mode, setMode] = useState('login');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [passwordConfirm, setPasswordConfirm] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [registrationOpen, setRegistrationOpen] = useState(false);

  useEffect(() => {
    let mounted = true;

    async function loadSetupStatus() {
      try {
        const payload = await apiRequest('setup/');
        if (mounted) {
          setRegistrationOpen(Boolean(payload.registration_open));
          if (!payload.registration_open) {
            setMode('login');
          }
        }
      } catch {
        if (mounted) {
          setRegistrationOpen(false);
          setMode('login');
        }
      }
    }

    loadSetupStatus();
    return () => {
      mounted = false;
    };
  }, []);

  async function submit(event) {
    event.preventDefault();
    setError('');
    setLoading(true);

    try {
      if (mode === 'register') {
        await apiRequest('register/', {
          method: 'POST',
          body: {
            username,
            password,
            password_confirm: passwordConfirm,
          },
        });
      }

      const user = await apiRequest('login/', {
        method: 'POST',
        body: { username, password },
      });
      storeUser(user);
      showSuccessNotification(
        mode === 'register' ? 'Account created' : 'Signed in',
        `Welcome, ${user.username}.`
      );
      onLogin(user);
    } catch (err) {
      setError(err.message);
      showErrorNotification('Authentication failed', err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="auth-shell">
      <Paper className="auth-panel" radius="md" p="xl">
        <LoadingOverlay visible={loading} />
        <Stack gap="lg">
          <Group gap="sm">
            <Image src="/logo.png" alt="LanGuard" w={48} h={48} radius="sm" />
            <Box>
              <Title order={2}>LanGuard</Title>
              <Text size="sm" c="dimmed">
                Home network visibility
              </Text>
            </Box>
          </Group>

          {error && (
            <Alert color="red" icon={<IconAlertCircle size={18} />}>
              {error}
            </Alert>
          )}

          <form onSubmit={submit}>
            <Stack>
              <TextInput
                label="Username"
                value={username}
                onChange={(event) => setUsername(event.currentTarget.value)}
                leftSection={<IconShieldCheck size={18} />}
                required
              />
              <PasswordInput
                label="Password"
                value={password}
                onChange={(event) => setPassword(event.currentTarget.value)}
                required
              />
              {mode === 'register' && (
                <PasswordInput
                  label="Confirm password"
                  value={passwordConfirm}
                  onChange={(event) =>
                    setPasswordConfirm(event.currentTarget.value)
                  }
                  required
                />
              )}
              <Button type="submit" leftSection={<IconShieldCheck size={18} />}>
                {mode === 'login' ? 'Sign in' : 'Create account'}
              </Button>
            </Stack>
          </form>

          {registrationOpen && (
            <Button
              variant="subtle"
              leftSection={<IconUserPlus size={18} />}
              onClick={() => setMode(mode === 'login' ? 'register' : 'login')}
            >
              {mode === 'login' ? 'Create first user' : 'Use existing account'}
            </Button>
          )}
        </Stack>
      </Paper>
    </main>
  );
}

function MetricCard({ icon, label, value, color }) {
  return (
    <Card className="metric-card" radius="md" padding="lg">
      <Group justify="space-between" align="flex-start">
        <Stack gap={4}>
          <Text size="sm" c="dimmed">
            {label}
          </Text>
          <Title order={2}>{value ?? 0}</Title>
        </Stack>
        <ThemeIconLike color={color}>{icon}</ThemeIconLike>
      </Group>
    </Card>
  );
}

function ThemeIconLike({ children, color }) {
  return (
    <Box
      style={{
        width: 42,
        height: 42,
        borderRadius: 8,
        display: 'grid',
        placeItems: 'center',
        background: `var(--mantine-color-${color}-1)`,
        color: `var(--mantine-color-${color}-7)`,
      }}
    >
      {children}
    </Box>
  );
}

function PortSummary({ ports = [] }) {
  const visiblePorts = ports.slice(0, 2);
  const hiddenPortCount = Math.max(0, ports.length - visiblePorts.length);
  const portLabel = ports
    .map((port) => `${port.protocol || 'tcp'}/${port.port}`)
    .join(', ');

  if (!ports.length) {
    return (
      <Text size="sm" c="dimmed">
        -
      </Text>
    );
  }

  return (
    <Tooltip label={portLabel} disabled={!portLabel}>
      <div className="ports-list">
        {visiblePorts.map((port) => (
          <Badge
            className="port-badge"
            key={`${port.protocol}-${port.port}`}
            variant="light"
          >
            {port.port}
          </Badge>
        ))}
        {hiddenPortCount > 0 && (
          <Badge className="port-badge port-overflow-badge" color="gray" variant="light">
            +{hiddenPortCount}
          </Badge>
        )}
      </div>
    </Tooltip>
  );
}

function DeviceField({ label, value, editable = false, required = false, onChange }) {
  return (
    <Box className={`device-field ${editable ? 'editable' : ''}`}>
      <Group gap={4}>
        <Text size="xs" c="dimmed">{label}</Text>
        {required && <Text size="xs" c="red">*</Text>}
      </Group>
      {editable ? (
        <input
          className="device-field-input"
          value={value}
          onChange={(event) => onChange(event.currentTarget.value)}
        />
      ) : (
        <Text size="sm" className="wrap-text">{value || '-'}</Text>
      )}
    </Box>
  );
}

function DeviceIconPicker({ value, onChange }) {
  const selectedIcon = normalizeDeviceIcon(value);

  return (
    <Box className="device-field icon-picker-field">
      <Text size="xs" c="dimmed">Icon</Text>
      <div className="icon-picker-grid">
        {deviceIconOptions.map((option) => {
          const Icon = option.icon;
          const selected = option.value === selectedIcon;

          return (
            <Tooltip key={option.value} label={option.label}>
              <button
                type="button"
                className={`icon-picker-button ${selected ? 'selected' : ''}`}
                onClick={() => onChange(option.value)}
                aria-label={option.label}
              >
                <Icon size={18} stroke={1.8} />
              </button>
            </Tooltip>
          );
        })}
      </div>
    </Box>
  );
}

function DeviceModal({ device, opened, onClose, onSaved }) {
  const [icon, setIcon] = useState('');
  const [name, setName] = useState('');
  const [known, setKnown] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [deleteConfirmOpened, deleteConfirm] = useDisclosure(false);

  useEffect(() => {
    if (device) {
      setIcon(device.icon || '');
      setName(device.name || '');
      setKnown(Boolean(device.known));
      setError('');
    }
  }, [device]);

  async function save() {
    if (!device) {
      return;
    }
    setSaving(true);
    setError('');
    try {
      await apiRequest(`device/?id=${device.id}`, {
        method: 'PUT',
        body: {
          icon,
          name,
          known,
        },
      });
      await onSaved();
      showSuccessNotification('Device saved', `${name || device.name} was updated.`);
      onClose();
    } catch (err) {
      setError(err.message);
      showErrorNotification('Could not save device', err.message);
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
    const deletedName = device.name;
    try {
      await apiRequest(`device/?id=${device.id}`, { method: 'DELETE' });
      await onSaved();
      showSuccessNotification('Device deleted', `${deletedName} was removed.`);
      deleteConfirm.close();
      onClose();
    } catch (err) {
      setError(err.message);
      showErrorNotification('Could not delete device', err.message);
    } finally {
      setSaving(false);
    }
  }

  function closeModal() {
    deleteConfirm.close();
    onClose();
  }

  return (
    <Modal
      opened={opened}
      onClose={closeModal}
      title={device?.name || 'Device'}
      centered
      size="lg"
    >
      <Stack>
        {error && (
          <Alert color="red" icon={<IconAlertCircle size={18} />}>
            {error}
          </Alert>
        )}

        <SimpleGrid cols={{ base: 1, sm: 2 }}>
          <DeviceField
            label="Name"
            value={name}
            editable
            required
            onChange={setName}
          />
          <DeviceField
            label="Vendor"
            value={device?.vendor || '-'}
          />
          <DeviceField
            label="IP address"
            value={device?.ip || '-'}
          />
          <DeviceField
            label="MAC address"
            value={device?.mac || '-'}
          />
          <DeviceIconPicker value={icon} onChange={setIcon} />
        </SimpleGrid>

        <Group>
          <Switch
            label="Known device"
            checked={known}
            onChange={(event) => setKnown(event.currentTarget.checked)}
          />
          <Group gap="xs">
            <span className={`status-dot ${device?.online ? 'online' : 'offline'}`} />
            <Text size="sm">{device?.online ? 'Online' : 'Offline'}</Text>
            <Text size="sm" c="dimmed">Missed scans: {device?.missed_scans ?? 0}</Text>
          </Group>
        </Group>

        <Divider />

        <SimpleGrid cols={{ base: 1, sm: 2 }}>
          <Box>
            <Text size="xs" c="dimmed">First seen</Text>
            <Text size="sm">{formatDate(device?.firstseen)}</Text>
          </Box>
          <Box>
            <Text size="xs" c="dimmed">Last seen</Text>
            <Text size="sm">{formatDate(device?.lastseen)}</Text>
          </Box>
          <Box>
            <Text size="xs" c="dimmed">Last port scan</Text>
            <Text size="sm">{formatDate(device?.last_port_scan)}</Text>
          </Box>
          <Box>
            <Text size="xs" c="dimmed">Open ports</Text>
            <Group gap={4} mt={4}>
              {(device?.open_ports || []).length ? (
                (device?.open_ports || []).map((port) => (
                  <Badge key={`${port.protocol}-${port.port}`} variant="light">
                    {port.protocol}/{port.port}
                  </Badge>
                ))
              ) : (
                <Text size="sm">-</Text>
              )}
            </Group>
          </Box>
        </SimpleGrid>

        <Divider />
        <Group justify="space-between">
          <Button
            color="red"
            variant="light"
            leftSection={<IconTrash size={18} />}
            onClick={deleteConfirm.open}
            loading={saving}
          >
            Delete
          </Button>
          <Button onClick={save} loading={saving}>
            Save
          </Button>
        </Group>
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
    </Modal>
  );
}

function UserManagementModal({ opened, onClose, currentUser, onCurrentUserUpdated }) {
  const [users, setUsers] = useState([]);
  const [selectedUserId, setSelectedUserId] = useState('new');
  const [username, setUsername] = useState('');
  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
  const [password, setPassword] = useState('');
  const [passwordConfirm, setPasswordConfirm] = useState('');
  const [isActive, setIsActive] = useState(true);
  const [isStaff, setIsStaff] = useState(false);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [deleteTarget, setDeleteTarget] = useState(null);

  const selectedUser = selectedUserId === 'new'
    ? null
    : users.find((item) => String(item.id) === String(selectedUserId));
  const canManageUsers = Boolean(currentUser?.is_staff || currentUser?.is_superuser);
  const adminUserCount = users.filter((item) => item.is_staff).length;
  const selectedUserIsLastAdmin = Boolean(selectedUser?.is_staff && adminUserCount <= 1);

  async function loadUsers() {
    setLoading(true);
    setError('');
    try {
      const payload = await apiRequest('users/');
      const nextUsers = payload.data || [];
      setUsers(nextUsers);
      if (!canManageUsers && nextUsers[0]) {
        setSelectedUserId(String(nextUsers[0].id));
      } else if (selectedUserId !== 'new' && !nextUsers.some((item) => String(item.id) === String(selectedUserId))) {
        setSelectedUserId('new');
      }
    } catch (err) {
      setError(err.message);
      showErrorNotification('Could not load users', err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (opened) {
      loadUsers();
    }
  }, [opened]);

  useEffect(() => {
    if (selectedUser) {
      setUsername(selectedUser.username || '');
      setFirstName(selectedUser.first_name || '');
      setLastName(selectedUser.last_name || '');
      setIsActive(Boolean(selectedUser.is_active));
      setIsStaff(Boolean(selectedUser.is_staff));
    } else {
      setUsername('');
      setFirstName('');
      setLastName('');
      setIsActive(true);
      setIsStaff(false);
    }
    setPassword('');
    setPasswordConfirm('');
    setError('');
  }, [selectedUserId, selectedUser?.id]);

  async function saveUser() {
    setSaving(true);
    setError('');
    try {
      const body = {
        username,
        first_name: capitalizeName(firstName),
        last_name: capitalizeName(lastName),
        is_active: isActive,
        is_staff: isStaff,
        ...(password ? { password, password_confirm: passwordConfirm } : {}),
      };
      const saved = selectedUser
        ? await apiRequest(`users/?id=${selectedUser.id}`, { method: 'PUT', body })
        : await apiRequest('users/', { method: 'POST', body });
      const savedUser = saved.data;

      await loadUsers();
      setSelectedUserId(String(savedUser.id));
      showSuccessNotification(
        selectedUser ? 'User saved' : 'User created',
        `${savedUser.username} was ${selectedUser ? 'updated' : 'created'}.`
      );

      if (currentUser?.username === selectedUser?.username) {
        if (savedUser.is_active) {
          onCurrentUserUpdated({
            ...currentUser,
            id: savedUser.id,
            username: savedUser.username,
            first_name: savedUser.first_name,
            last_name: savedUser.last_name,
            is_staff: savedUser.is_staff,
          });
        } else {
          clearStoredUser();
          onCurrentUserUpdated(null);
        }
      }
    } catch (err) {
      setError(err.message);
      showErrorNotification('Could not save user', err.message);
    } finally {
      setSaving(false);
    }
  }

  async function deleteUser() {
    if (!deleteTarget) {
      return;
    }
    setSaving(true);
    setError('');
    try {
      await apiRequest(`users/?id=${deleteTarget.id}`, { method: 'DELETE' });
      await loadUsers();
      setSelectedUserId('new');
      showSuccessNotification('User deleted', `${deleteTarget.username} was removed.`);
      if (currentUser?.username === deleteTarget.username) {
        clearStoredUser();
        onCurrentUserUpdated(null);
      }
      setDeleteTarget(null);
    } catch (err) {
      setError(err.message);
      showErrorNotification('Could not delete user', err.message);
    } finally {
      setSaving(false);
    }
  }

  function closeModal() {
    setDeleteTarget(null);
    onClose();
  }

  return (
    <>
      <Modal opened={opened} onClose={closeModal} title={canManageUsers ? 'Users' : 'My account'} centered size="lg">
        <LoadingOverlay visible={loading} />
        <Stack>
          {error && (
            <Alert color="red" icon={<IconAlertCircle size={18} />}>
              {error}
            </Alert>
          )}
          <SimpleGrid cols={{ base: 1, sm: canManageUsers ? 2 : 1 }}>
            {canManageUsers && (
              <Box className="user-list-panel">
                <Group justify="space-between" mb="sm">
                  <Text fw={700}>Accounts</Text>
                  <Button
                    size="xs"
                    variant="light"
                    leftSection={<IconUserPlus size={15} />}
                    onClick={() => setSelectedUserId('new')}
                  >
                    New
                  </Button>
                </Group>
                <Stack gap="xs">
                  {users.map((item) => (
                    <button
                      key={item.id}
                      type="button"
                      className={`user-list-button ${String(item.id) === String(selectedUserId) ? 'active' : ''}`}
                      onClick={() => setSelectedUserId(String(item.id))}
                    >
                      <Group gap="xs" wrap="nowrap">
                        <IconUserEdit size={17} />
                        <Box ta="start" className="truncate-cell">
                          <Text size="sm" fw={700}>{userDisplayName(item)}</Text>
                          <Text size="xs" c="dimmed">
                            {item.username} · {item.is_active ? 'Active' : 'Inactive'}{item.is_staff ? ' · Admin' : ''}
                          </Text>
                        </Box>
                      </Group>
                    </button>
                  ))}
                </Stack>
              </Box>
            )}

            <Stack>
              <Text fw={700}>{selectedUser ? (canManageUsers ? 'Edit user' : 'Edit account') : 'Create user'}</Text>
              <TextInput
                label="Username"
                value={username}
                onChange={(event) => setUsername(event.currentTarget.value)}
                required
              />
              <SimpleGrid cols={{ base: 1, sm: 2 }}>
                <TextInput
                  label="First name"
                  value={firstName}
                  onChange={(event) => setFirstName(event.currentTarget.value)}
                />
                <TextInput
                  label="Last name"
                  value={lastName}
                  onChange={(event) => setLastName(event.currentTarget.value)}
                />
              </SimpleGrid>
              <PasswordInput
                label={selectedUser ? 'New password' : 'Password'}
                description={selectedUser ? 'Leave blank to keep current password.' : undefined}
                value={password}
                onChange={(event) => setPassword(event.currentTarget.value)}
                required={!selectedUser}
              />
              <PasswordInput
                label="Confirm password"
                value={passwordConfirm}
                onChange={(event) => setPasswordConfirm(event.currentTarget.value)}
                required={!selectedUser || Boolean(password)}
              />
              {canManageUsers && (
                <>
                  <Switch
                    label="Active user"
                    checked={isActive}
                    onChange={(event) => setIsActive(event.currentTarget.checked)}
                  />
                  <Switch
                    label="Admin/staff user"
                    checked={isStaff}
                    onChange={(event) => setIsStaff(event.currentTarget.checked)}
                  />
                </>
              )}
            </Stack>
          </SimpleGrid>

          <Divider />
          <Group justify="space-between">
            {canManageUsers ? (
              <Stack gap={4}>
                <Button
                  color="red"
                  variant="light"
                  leftSection={<IconUserMinus size={18} />}
                  disabled={!selectedUser || selectedUserIsLastAdmin}
                  onClick={() => setDeleteTarget(selectedUser)}
                >
                  Delete
                </Button>
                {selectedUserIsLastAdmin && (
                  <Text size="xs" c="dimmed">
                    The only admin user cannot be deleted.
                  </Text>
                )}
              </Stack>
            ) : <Box />}
            <Group>
              <Button variant="default" onClick={closeModal}>
                Close
              </Button>
              <Button onClick={saveUser} loading={saving} disabled={!selectedUser && !canManageUsers}>
                Save
              </Button>
            </Group>
          </Group>
        </Stack>
      </Modal>

      <Modal
        opened={Boolean(deleteTarget)}
        onClose={() => setDeleteTarget(null)}
        title="Delete user"
        centered
      >
        <Stack>
          <Text>Are you sure you want to delete this user?</Text>
          <Text size="sm" c="dimmed">
            {deleteTarget?.username} will no longer be able to sign in.
          </Text>
          <Group justify="flex-end">
            <Button variant="default" onClick={() => setDeleteTarget(null)}>
              Cancel
            </Button>
            <Button
              color="red"
              leftSection={<IconUserMinus size={18} />}
              onClick={deleteUser}
              loading={saving}
            >
              Delete
            </Button>
          </Group>
        </Stack>
      </Modal>
    </>
  );
}

function SettingsModal({ opened, onClose, onSaved }) {
  const [ipRange, setIpRange] = useState('');
  const [scanInterval, setScanInterval] = useState(10);
  const [timeZone, setTimeZone] = useState('UTC');
  const [discordEnabled, setDiscordEnabled] = useState(true);
  const [telegramEnabled, setTelegramEnabled] = useState(true);
  const [discordConfigured, setDiscordConfigured] = useState(false);
  const [telegramConfigured, setTelegramConfigured] = useState(false);
  const [discordWebhook, setDiscordWebhook] = useState('');
  const [telegramToken, setTelegramToken] = useState('');
  const [telegramUserId, setTelegramUserId] = useState('');
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  async function loadSettings() {
    setLoading(true);
    setError('');
    try {
      const payload = await apiRequest('settings/');
      const data = payload.data || {};
      setIpRange(data.ip_range || '');
      setScanInterval(data.scan_interval || 10);
      setTimeZone(data.time_zone || 'UTC');
      setDiscordEnabled(Boolean(data.discord_enabled));
      setTelegramEnabled(Boolean(data.telegram_enabled));
      setDiscordConfigured(Boolean(data.discord_configured));
      setTelegramConfigured(Boolean(data.telegram_configured));
      setDiscordWebhook(data.discord_webhook || '');
      setTelegramToken(data.telegram_token || '');
      setTelegramUserId(data.telegram_user_id || '');
    } catch (err) {
      setError(err.message);
      showErrorNotification('Could not load settings', err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (opened) {
      loadSettings();
    }
  }, [opened]);

  async function saveSettings() {
    setSaving(true);
    setError('');
    try {
      const body = {
        ip_range: ipRange,
        scan_interval: scanInterval,
        time_zone: timeZone,
        discord_enabled: discordEnabled,
        telegram_enabled: telegramEnabled,
      };
      body.discord_webhook = discordWebhook;
      body.telegram_token = telegramToken;
      body.telegram_user_id = telegramUserId;

      await apiRequest('settings/', { method: 'PUT', body });
      await loadSettings();
      await onSaved();
      showSuccessNotification('Settings saved', 'Scanner and notification settings were updated.');
      onClose();
    } catch (err) {
      setError(err.message);
      showErrorNotification('Could not save settings', err.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal opened={opened} onClose={onClose} title="Settings" centered size="lg">
      <LoadingOverlay visible={loading} />
      <Stack>
        {error && (
          <Alert color="red" icon={<IconAlertCircle size={18} />}>
            {error}
          </Alert>
        )}

        <SimpleGrid cols={{ base: 1, sm: 3 }}>
          <TextInput
            label="Default scan range"
            value={ipRange}
            onChange={(event) => setIpRange(event.currentTarget.value)}
            placeholder="192.168.1.0/24"
            required
          />
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
          Restart the scanner container after changing scan interval or timezone.
        </Text>

        <Divider />

        <Stack gap="sm">
          <Group justify="space-between">
            <Group gap="sm">
              <Text fw={700}>Discord</Text>
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
          <TextInput
            label="Discord webhook"
            description={
              discordConfigured
                ? 'Discord messages are configured with this webhook.'
                : 'Paste a Discord channel webhook URL to enable Discord messages.'
            }
            placeholder="https://discord.com/api/webhooks/..."
            value={discordWebhook}
            onChange={(event) => setDiscordWebhook(event.currentTarget.value)}
          />
        </Stack>

        <Stack gap="sm">
          <Group justify="space-between">
            <Group gap="sm">
              <Text fw={700}>Telegram</Text>
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
          <SimpleGrid cols={{ base: 1, sm: 2 }}>
            <TextInput
              label="Telegram bot token"
              placeholder="123456:bot-token"
              value={telegramToken}
              onChange={(event) => setTelegramToken(event.currentTarget.value)}
            />
            <TextInput
              label="Telegram user ID"
              placeholder="123456789"
              value={telegramUserId}
              onChange={(event) => setTelegramUserId(event.currentTarget.value)}
            />
          </SimpleGrid>
        </Stack>

        <Divider />
        <Group justify="flex-end">
          <Button variant="default" onClick={onClose}>
            Close
          </Button>
          <Button onClick={saveSettings} loading={saving}>
            Save
          </Button>
        </Group>
      </Stack>
    </Modal>
  );
}

function Dashboard({ user, onLogout, onUserUpdated }) {
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState('');
  const [currentTime, setCurrentTime] = useState(() => new Date());
  const [devices, setDevices] = useState([]);
  const [devicePagination, setDevicePagination] = useState({
    count: 0,
    limit: 10,
    offset: 0,
    next_offset: null,
    previous_offset: null,
  });
  const [counters, setCounters] = useState({});
  const [scanStatus, setScanStatus] = useState(null);
  const [scanRuns, setScanRuns] = useState([]);
  const [events, setEvents] = useState([]);
  const [notifications, setNotifications] = useState([]);
  const [appSettings, setAppSettings] = useState(null);
  const [search, setSearch] = useState('');
  const [deviceStatus, setDeviceStatus] = useState('');
  const [devicePage, setDevicePage] = useState(1);
  const [devicePageSize, setDevicePageSize] = useState('10');
  const [deviceOrdering, setDeviceOrdering] = useState('');
  const [activeTab, setActiveTab] = useState('events');
  const [eventType, setEventType] = useState('');
  const [scanRange, setScanRange] = useState('');
  const [activeDevice, setActiveDevice] = useState(null);
  const [changelogOpened, setChangelogOpened] = useState(false);
  const [seenChangelogVersion, setSeenChangelogVersion] = useState(APP_VERSION);
  const [latestVersion, setLatestVersion] = useState(APP_VERSION);
  const [versionCheckInterval, setVersionCheckInterval] = useState(
    versionCheckFallbackInterval
  );
  const [modalOpened, modal] = useDisclosure(false);
  const [logoutModalOpened, logoutModal] = useDisclosure(false);
  const [usersModalOpened, usersModal] = useDisclosure(false);
  const [settingsModalOpened, settingsModal] = useDisclosure(false);
  const tableStateRef = useRef({
    search: '',
    deviceStatus: '',
    eventType: '',
    deviceLimit: 10,
    deviceOffset: 0,
    deviceOrdering: '',
  });

  const filteredDevices = useMemo(() => devices, [devices]);
  const deviceLimit = Number(devicePageSize);
  const devicePageCount = Math.max(
    1,
    Math.ceil((devicePagination.count || 0) / deviceLimit)
  );
  const deviceOffset = (devicePage - 1) * deviceLimit;
  const deviceStart = devicePagination.count === 0 ? 0 : deviceOffset + 1;
  const deviceEnd = Math.min(deviceOffset + devices.length, devicePagination.count);
  const selectedDeviceStatus =
    deviceStatusOptions.find((option) => option.value === deviceStatus) || null;
  const canManageUsers = Boolean(user?.is_staff || user?.is_superuser);
  const hasUnreadChangelog = seenChangelogVersion !== APP_VERSION;
  const hasVersionUpdate = isNewerVersion(latestVersion, APP_VERSION);
  const hasVersionIndicator = hasUnreadChangelog || hasVersionUpdate;
  const versionTooltip = hasVersionUpdate
    ? `New version v${latestVersion} is available`
    : 'Version history';

  useEffect(() => {
    tableStateRef.current = {
      search,
      deviceStatus,
      eventType,
      deviceLimit,
      deviceOffset,
      deviceOrdering,
    };
  }, [search, deviceStatus, eventType, deviceLimit, deviceOffset, deviceOrdering]);

  async function loadData({ quiet = false, notifyOnError = false, notifyOnSuccess = false } = {}) {
    if (quiet) {
      setRefreshing(true);
    } else {
      setLoading(true);
    }
    setError('');

    try {
      const currentTableState = tableStateRef.current;
      const deviceParams = {
        search: currentTableState.search,
        online:
          currentTableState.deviceStatus === 'online'
            ? 'true'
            : currentTableState.deviceStatus === 'offline'
              ? 'false'
              : undefined,
        known: currentTableState.deviceStatus === 'new' ? 'false' : undefined,
        limit: currentTableState.deviceLimit,
        offset: currentTableState.deviceOffset,
        ordering: currentTableState.deviceOrdering || undefined,
      };
      const eventParams = {
        event_type: currentTableState.eventType || undefined,
        limit: 8,
      };

      const settingsRequest = canManageUsers
        ? apiRequest('settings/')
        : Promise.resolve({ data: null });
      const [deviceData, statusData, runData, eventData, notificationData, settingsData] =
        await Promise.all([
          apiRequest('device/', { params: deviceParams }),
          apiRequest('scan/status/'),
          apiRequest('scan/runs/', { params: { limit: 8 } }),
          apiRequest('events/', { params: eventParams }),
          apiRequest('notifications/', { params: { limit: 8 } }),
          settingsRequest,
        ]);

      setDevices(deviceData.data || []);
      setDevicePagination(
        deviceData.pagination || {
          count: 0,
          limit: currentTableState.deviceLimit,
          offset: currentTableState.deviceOffset,
          next_offset: null,
          previous_offset: null,
        }
      );
      setCounters(deviceData.counters || {});
      setScanStatus((previous) => statusData.data || previous);
      setScanRuns(runData.data || []);
      setEvents(eventData.data || []);
      setNotifications(notificationData.data || []);
      if (settingsData.data) {
        setAppSettings(settingsData.data);
      }
      if (notifyOnSuccess) {
        showSuccessNotification('Dashboard refreshed', 'Latest device and scan data loaded.');
      }
    } catch (err) {
      setError(quiet ? '' : err.message);
      if (notifyOnError) {
        showErrorNotification('Refresh failed', err.message);
      } else if (quiet) {
        showErrorNotification('Backend unavailable', err.message);
      }
      if (err.message.toLowerCase().includes('credential')) {
        clearStoredUser();
        onLogout();
      }
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }

  useEffect(() => {
    loadData();
    const timer = window.setInterval(() => loadData({ quiet: true }), 60000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    const storedVersion = window.localStorage.getItem(changelogSeenStorageKey) || '';
    setSeenChangelogVersion(storedVersion);
    if (storedVersion !== APP_VERSION) {
      setChangelogOpened(true);
    }
  }, []);

  useEffect(() => {
    async function checkVersion() {
      try {
        const payload = await apiRequest('version/');
        const versionData = payload.data || {};
        if (versionData.latest_version) {
          setLatestVersion(versionData.latest_version);
        }
        if (versionData.check_interval_seconds) {
          setVersionCheckInterval(versionData.check_interval_seconds * 1000);
        }
      } catch (err) {
        setLatestVersion(APP_VERSION);
      }
    }

    checkVersion();
    const timer = window.setInterval(checkVersion, versionCheckInterval);
    return () => window.clearInterval(timer);
  }, [versionCheckInterval]);

  useEffect(() => {
    const timer = window.setInterval(() => setCurrentTime(new Date()), 30000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => loadData({ quiet: true }), 250);
    return () => window.clearTimeout(timer);
  }, [search, deviceStatus, eventType, devicePage, devicePageSize, deviceOrdering]);

  useEffect(() => {
    setDevicePage(1);
  }, [search, deviceStatus, devicePageSize, deviceOrdering]);

  async function runScan() {
    setRefreshing(true);
    setError('');
    try {
      await apiRequest('scan/', {
        method: 'POST',
        body: scanRange ? { ip_range: scanRange } : {},
      });
      await loadData({ quiet: true });
      showSuccessNotification('Scan started', 'LanGuard is scanning the selected network range.');
    } catch (err) {
      setError(err.message);
      showErrorNotification('Scan failed', err.message);
    } finally {
      setRefreshing(false);
    }
  }

  function logout() {
    showSuccessNotification('Signed out', 'Your LanGuard session has ended.');
    clearStoredUser();
    onLogout();
  }

  function updateCurrentUser(nextUser) {
    if (!nextUser) {
      onLogout();
      return;
    }
    storeUser(nextUser);
    onUserUpdated(nextUser);
  }

  function closeChangelog() {
    window.localStorage.setItem(changelogSeenStorageKey, APP_VERSION);
    setSeenChangelogVersion(APP_VERSION);
    setChangelogOpened(false);
  }

  return (
    <main className="shell">
      <header className="topbar">
        <Container size="xl" py="sm">
          <Group justify="space-between">
            <Group gap="sm">
              <Image src="/logo.png" alt="LanGuard" w={42} h={42} radius="sm" />
              <Box>
                <Group gap="xs" wrap="nowrap">
                  <Title order={3}>LanGuard</Title>
                  <Tooltip label={versionTooltip}>
                    <button
                      type="button"
                      className={`version-pill ${hasVersionIndicator ? 'has-update' : ''}`}
                      onClick={() => setChangelogOpened(true)}
                      aria-label={`LanGuard version ${APP_VERSION}`}
                    >
                      v{APP_VERSION}
                      {hasVersionIndicator && <span className="version-dot" aria-hidden="true" />}
                    </button>
                  </Tooltip>
                </Group>
                <Text size="xs" c="dimmed">
                  Signed in as {userDisplayName(user)}
                </Text>
              </Box>
            </Group>
            <Group gap="xs">
              <Group className="topbar-clock" gap="xs" wrap="nowrap">
                <IconClock size={18} />
                <Box>
                  <Text size="xs" c="dimmed" lh={1.1}>
                    {formatTopbarDate(currentTime)}
                  </Text>
                  <Text size="sm" fw={700} lh={1.15}>
                    {formatTopbarTime(currentTime)}
                  </Text>
                </Box>
              </Group>
              <ColorSchemeControl />
              {canManageUsers && (
                <Button
                  component="a"
                  href={getAdminUrl()}
                  target="_blank"
                  rel="noreferrer"
                  variant="light"
                  size="sm"
                  leftSection={<IconShieldLock size={17} />}
                  className="topbar-admin-button"
                >
                  Admin site
                </Button>
              )}
              <Tooltip label="Refresh">
                <ActionIcon
                  variant="light"
                  size="lg"
                  onClick={() => loadData({ quiet: true, notifyOnError: true, notifyOnSuccess: true })}
                  loading={refreshing}
                >
                  <IconRefresh size={19} />
                </ActionIcon>
              </Tooltip>
              {canManageUsers && (
                <Tooltip label="Settings">
                  <ActionIcon
                    variant="light"
                    size="lg"
                    onClick={settingsModal.open}
                    aria-label="Settings"
                  >
                    <IconSettings size={19} />
                  </ActionIcon>
                </Tooltip>
              )}
              <Tooltip label={canManageUsers ? 'Manage users' : 'Edit account'}>
                <ActionIcon
                  variant="light"
                  size="lg"
                  className="user-initials-button"
                  onClick={usersModal.open}
                  aria-label={canManageUsers ? 'Manage users' : 'Edit account'}
                >
                  {userInitials(user)}
                </ActionIcon>
              </Tooltip>
              <Tooltip label="Sign out">
                <ActionIcon variant="light" color="gray" size="lg" onClick={logoutModal.open}>
                  <IconLogout size={19} />
                </ActionIcon>
              </Tooltip>
            </Group>
          </Group>
        </Container>
      </header>

      <Container size="xl" py="xl">
        <LoadingOverlay visible={loading} />
        <Stack gap="lg">
          {error && (
            <Alert color="red" icon={<IconAlertCircle size={18} />} withCloseButton onClose={() => setError('')}>
              {error}
            </Alert>
          )}

          <SimpleGrid cols={{ base: 1, sm: 2, lg: 4 }}>
            <MetricCard icon={<IconDeviceDesktop size={24} />} label="Inventory devices" value={counters.all_devices} color="indigo" />
            <MetricCard icon={<IconWifi size={24} />} label="Online" value={counters.online_devices} color="teal" />
            <MetricCard icon={<IconWifiOff size={24} />} label="Offline" value={counters.offline_devices} color="gray" />
            <MetricCard icon={<IconPlugConnected size={24} />} label="Open ports now" value={counters.open_ports} color="orange" />
          </SimpleGrid>

          <Paper className="content-panel" radius="md">
            <Stack gap={0}>
              <Group className="devices-panel-header" justify="space-between" p="md">
                <Group>
                  <IconNetwork size={22} />
                  <Title order={4}>Devices</Title>
                </Group>
                <Group className="devices-panel-controls">
                  <Select
                    w={140}
                    placeholder="Status"
                    clearable
                    data={deviceStatusOptions}
                    value={deviceStatus}
                    aria-label={selectedDeviceStatus?.label || 'Status'}
                    onChange={(value) => setDeviceStatus(value || '')}
                  />
                  <Select
                    w={115}
                    aria-label="Rows per page"
                    data={devicePageSizeOptions}
                    value={devicePageSize}
                    onChange={(value) => setDevicePageSize(value || '10')}
                  />
                  <TextInput
                    w={{ base: 180, sm: 260 }}
                    placeholder="Search"
                    leftSection={<IconSearch size={17} />}
                    rightSection={
                      search ? (
                        <ActionIcon
                          aria-label="Clear device search"
                          color="gray"
                          size="sm"
                          variant="subtle"
                          onClick={() => setSearch('')}
                        >
                          <IconX size={16} />
                        </ActionIcon>
                      ) : null
                    }
                    value={search}
                    onChange={(event) => setSearch(event.currentTarget.value)}
                  />
                </Group>
              </Group>
              <Divider />
              <Table className="devices-table" highlightOnHover verticalSpacing="sm">
                <Table.Thead>
                  <Table.Tr>
                    <Table.Th className="device-status-cell">Status</Table.Th>
                    <SortableHeader
                      field="name"
                      label="Name"
                      ordering={deviceOrdering}
                      onChange={setDeviceOrdering}
                      className="device-name-cell"
                    />
                    <SortableHeader
                      field="ip"
                      label="IP"
                      ordering={deviceOrdering}
                      onChange={setDeviceOrdering}
                      className="device-ip-cell"
                    />
                    <Table.Th className="device-mac-cell">MAC</Table.Th>
                    <Table.Th className="device-ports-cell">Ports</Table.Th>
                    <Table.Th className="device-lastseen-cell">Last seen</Table.Th>
                    <Table.Th className="device-known-cell">Known</Table.Th>
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {filteredDevices.map((device) => (
                    <Table.Tr
                      className="device-row"
                      key={device.id}
                      onClick={() => {
                        setActiveDevice(device);
                        modal.open();
                      }}
                      style={{ cursor: 'pointer' }}
                    >
                      <Table.Td className="device-status-cell">
                        <Group gap="xs">
                          <span className={`status-dot ${device.online ? 'online' : 'offline'}`} />
                          {device.online ? 'Online' : 'Offline'}
                        </Group>
                      </Table.Td>
                      <Table.Td className="device-name-cell" fw={600}>
                        <Group gap="xs" wrap="nowrap">
                          <span className="device-table-icon">
                            <DeviceIcon value={device.icon} size={17} />
                          </span>
                          <span className="truncate-cell" title={device.name}>
                            {device.name}
                          </span>
                        </Group>
                      </Table.Td>
                      <Table.Td className="device-ip-cell">{device.ip}</Table.Td>
                      <Table.Td className="device-mac-cell">{device.mac}</Table.Td>
                      <Table.Td className="device-ports-cell">
                        <PortSummary ports={device.open_ports || []} />
                      </Table.Td>
                      <Table.Td className="device-lastseen-cell">{formatDate(device.lastseen)}</Table.Td>
                      <Table.Td className="device-known-cell">
                        <Badge
                          className="device-known-badge"
                          color={device.known ? 'teal' : 'yellow'}
                          variant="light"
                        >
                          {device.known ? 'Known' : 'New'}
                        </Badge>
                      </Table.Td>
                    </Table.Tr>
                  ))}
                </Table.Tbody>
              </Table>
              <Stack className="device-mobile-list" gap={0}>
                {filteredDevices.map((device) => (
                  <button
                    type="button"
                    className="device-mobile-row"
                    key={device.id}
                    onClick={() => {
                      setActiveDevice(device);
                      modal.open();
                    }}
                  >
                    <Group justify="space-between" align="flex-start" wrap="nowrap">
                      <Group gap="sm" align="flex-start" wrap="nowrap" className="device-mobile-main">
                        <span className="device-mobile-icon">
                          <DeviceIcon value={device.icon} size={19} />
                        </span>
                        <Box className="device-mobile-title">
                          <Text fw={700} className="truncate-cell">{device.name}</Text>
                          <Group gap="xs" wrap="nowrap">
                            <span className={`status-dot ${device.online ? 'online' : 'offline'}`} />
                            <Text size="sm" c="dimmed">{device.online ? 'Online' : 'Offline'}</Text>
                          </Group>
                        </Box>
                      </Group>
                      <Badge
                        className="device-known-badge"
                        color={device.known ? 'teal' : 'yellow'}
                        variant="light"
                      >
                        {device.known ? 'Known' : 'New'}
                      </Badge>
                    </Group>
                    <SimpleGrid cols={2} spacing="xs" mt="sm">
                      <Box>
                        <Text size="xs" c="dimmed">IP</Text>
                        <Text size="sm" className="mobile-mono-value">{device.ip}</Text>
                      </Box>
                      <Box>
                        <Text size="xs" c="dimmed">Last seen</Text>
                        <Text size="sm">{formatDate(device.lastseen)}</Text>
                      </Box>
                      <Box className="device-mobile-wide">
                        <Text size="xs" c="dimmed">MAC</Text>
                        <Text size="sm" className="mobile-mono-value">{device.mac}</Text>
                      </Box>
                      <Box className="device-mobile-wide">
                        <Text size="xs" c="dimmed">Ports</Text>
                        <PortSummary ports={device.open_ports || []} />
                      </Box>
                    </SimpleGrid>
                  </button>
                ))}
              </Stack>
              <Divider />
              <Group className="devices-pagination" justify="space-between" p="md">
                <Text size="sm" c="dimmed">
                  Showing {deviceStart}-{deviceEnd} of {devicePagination.count} devices
                </Text>
                <Pagination
                  total={devicePageCount}
                  value={devicePage}
                  onChange={setDevicePage}
                  size="sm"
                  withEdges
                />
              </Group>
            </Stack>
          </Paper>

          <SimpleGrid cols={{ base: 1, md: 2 }}>
            <Paper className="content-panel" radius="md" p="md">
              <Stack>
                <Group>
                  <IconShieldCheck size={22} />
                  <Title order={4}>Scan control</Title>
                </Group>
                <Text size="sm" c="dimmed">
                  Last scan: {scanStatus ? formatDate(scanStatus.finished_at || scanStatus.started_at) : '-'}
                </Text>
                <TextInput
                  label="CIDR range"
                  placeholder={
                    appSettings?.ip_range
                      ? `Use saved default (${appSettings.ip_range})`
                      : 'Use saved default'
                  }
                  value={scanRange}
                  onChange={(event) => setScanRange(event.currentTarget.value)}
                />
                <Button leftSection={<IconRefresh size={18} />} onClick={runScan} loading={refreshing}>
                  Run scan
                </Button>
              </Stack>
            </Paper>

            <Paper className="content-panel" radius="md" p="md">
              <Group mb="sm">
                <IconClock size={22} />
                <Title order={4}>Latest scan</Title>
              </Group>
              <SimpleGrid cols={2}>
                <NumberReadout label="Seen" value={scanStatus?.devices_seen} />
                <NumberReadout label="New" value={scanStatus?.new_devices} />
                <NumberReadout label="Opened" value={scanStatus?.ports_opened} />
                <NumberReadout label="Closed" value={scanStatus?.ports_closed} />
              </SimpleGrid>
            </Paper>
          </SimpleGrid>

          <Tabs value={activeTab} onChange={(value) => setActiveTab(value || 'events')}>
            <Group justify="space-between" align="flex-end">
              <Tabs.List>
                <Tabs.Tab value="events" leftSection={<IconBell size={16} />}>Events</Tabs.Tab>
                <Tabs.Tab value="history" leftSection={<IconHistory size={16} />}>Scan history</Tabs.Tab>
                <Tabs.Tab value="notifications" leftSection={<IconBell size={16} />}>Notifications</Tabs.Tab>
              </Tabs.List>
              {activeTab === 'events' && (
                <Select
                  w={210}
                  placeholder="Event type"
                  clearable
                  data={eventTypeOptions}
                  value={eventType}
                  onChange={(value) => setEventType(value || '')}
                />
              )}
            </Group>

            <Tabs.Panel value="events" pt="md">
              <Paper className="content-panel" radius="md">
                <Table verticalSpacing="sm">
                  <Table.Thead>
                    <Table.Tr>
                      <Table.Th>Type</Table.Th>
                      <Table.Th>Message</Table.Th>
                      <Table.Th>Created</Table.Th>
                      <Table.Th>Status</Table.Th>
                    </Table.Tr>
                  </Table.Thead>
                  <Table.Tbody>
                    {events.map((event) => (
                      <Table.Tr key={event.id}>
                        <Table.Td>
                          <Badge variant="light">
                            {event.event_type_display || event.event_type}
                          </Badge>
                        </Table.Td>
                        <Table.Td>{event.message}</Table.Td>
                        <Table.Td>{formatDate(event.created_at)}</Table.Td>
                        <Table.Td>
                          <Badge color={event.notified ? 'teal' : 'gray'} variant="light">
                            {event.notified ? 'Handled' : 'Pending'}
                          </Badge>
                        </Table.Td>
                      </Table.Tr>
                    ))}
                  </Table.Tbody>
                </Table>
              </Paper>
            </Tabs.Panel>

            <Tabs.Panel value="history" pt="md">
              <Paper className="content-panel" radius="md">
                <Table verticalSpacing="sm">
                  <Table.Thead>
                    <Table.Tr>
                      <Table.Th>Status</Table.Th>
                      <Table.Th>Range</Table.Th>
                      <Table.Th>Started</Table.Th>
                      <Table.Th>Seen</Table.Th>
                      <Table.Th>Port changes</Table.Th>
                    </Table.Tr>
                  </Table.Thead>
                  <Table.Tbody>
                    {scanRuns.map((run) => (
                      <Table.Tr key={run.id}>
                        <Table.Td>
                          <Badge color={run.status === 'success' ? 'teal' : run.status === 'failed' ? 'red' : 'blue'} variant="light">
                            {run.status}
                          </Badge>
                        </Table.Td>
                        <Table.Td>{run.ip_range}</Table.Td>
                        <Table.Td>{formatDate(run.started_at)}</Table.Td>
                        <Table.Td>{run.devices_seen}</Table.Td>
                        <Table.Td>{run.ports_opened} / {run.ports_closed}</Table.Td>
                      </Table.Tr>
                    ))}
                  </Table.Tbody>
                </Table>
              </Paper>
            </Tabs.Panel>

            <Tabs.Panel value="notifications" pt="md">
              <Paper className="content-panel" radius="md">
                <Table verticalSpacing="sm">
                  <Table.Thead>
                    <Table.Tr>
                      <Table.Th>Channel</Table.Th>
                      <Table.Th>Status</Table.Th>
                      <Table.Th>Attempts</Table.Th>
                      <Table.Th>Created</Table.Th>
                    </Table.Tr>
                  </Table.Thead>
                  <Table.Tbody>
                    {notifications.map((delivery) => (
                      <Table.Tr key={delivery.id}>
                        <Table.Td>{delivery.channel_display || delivery.channel}</Table.Td>
                        <Table.Td>
                          <Badge color={delivery.status === 'sent' ? 'teal' : delivery.status === 'failed' ? 'red' : 'gray'} variant="light">
                            {delivery.status_display || delivery.status}
                          </Badge>
                        </Table.Td>
                        <Table.Td>{delivery.attempts}</Table.Td>
                        <Table.Td>{formatDate(delivery.created_at)}</Table.Td>
                      </Table.Tr>
                    ))}
                  </Table.Tbody>
                </Table>
              </Paper>
            </Tabs.Panel>
          </Tabs>
        </Stack>
      </Container>

      <DeviceModal
        device={activeDevice}
        opened={modalOpened}
        onClose={modal.close}
        onSaved={() => loadData({ quiet: true })}
      />
      <UserManagementModal
        opened={usersModalOpened}
        onClose={usersModal.close}
        currentUser={user}
        onCurrentUserUpdated={updateCurrentUser}
      />
      {canManageUsers && (
        <SettingsModal
          opened={settingsModalOpened}
          onClose={settingsModal.close}
          onSaved={() => loadData({ quiet: true })}
        />
      )}
      <Modal opened={logoutModalOpened} onClose={logoutModal.close} title="Log off" centered>
        <Stack>
          <Text>Are you sure you want to log off?</Text>
          <Group justify="flex-end">
            <Button variant="default" onClick={logoutModal.close}>
              Cancel
            </Button>
            <Button color="red" leftSection={<IconLogout size={18} />} onClick={logout}>
              Log off
            </Button>
          </Group>
        </Stack>
      </Modal>
      <Modal opened={changelogOpened} onClose={closeChangelog} title={`What's new in v${APP_VERSION}`} centered>
        <Stack>
          {hasVersionUpdate && (
            <Alert color="blue" icon={<IconRefresh size={18} />}>
              Version v{latestVersion} is available. Pull the latest Docker images and restart
              the containers to update.
            </Alert>
          )}
          {CHANGELOG_ENTRIES.map((entry) => (
            <Box key={entry.version}>
              <Group justify="space-between" mb="xs">
                <Text fw={700}>Version {entry.version}</Text>
                <Text size="sm" c="dimmed">{entry.date}</Text>
              </Group>
              <Stack gap={6}>
                {entry.items.map((item) => (
                  <Group key={item} gap="xs" align="flex-start" wrap="nowrap">
                    <span className="changelog-bullet" />
                    <Text size="sm">{item}</Text>
                  </Group>
                ))}
              </Stack>
            </Box>
          ))}
          <Group justify="flex-end">
            <Button onClick={closeChangelog}>Done</Button>
          </Group>
        </Stack>
      </Modal>
    </main>
  );
}

function NumberReadout({ label, value }) {
  return (
    <Box>
      <Text size="xs" c="dimmed">
        {label}
      </Text>
      <Text fw={700} size="xl">
        {value ?? 0}
      </Text>
    </Box>
  );
}

export default function Home() {
  const [user, setUser] = useState(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    setUser(getStoredUser());
    setReady(true);
  }, []);

  if (!ready) {
    return null;
  }

  if (!user) {
    return <AuthScreen onLogin={setUser} />;
  }

  return (
    <Dashboard
      user={user}
      onLogout={() => setUser(null)}
      onUserUpdated={setUser}
    />
  );
}
