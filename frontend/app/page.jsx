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
  Pagination,
  Paper,
  PasswordInput,
  Select,
  SimpleGrid,
  Stack,
  Switch,
  Table,
  Tabs,
  Text,
  TextInput,
  Title,
  Tooltip,
} from '@mantine/core';
import { useDisclosure } from '@mantine/hooks';
import {
  IconAlertCircle,
  IconBell,
  IconClock,
  IconDeviceDesktop,
  IconHistory,
  IconLogout,
  IconNetwork,
  IconPlugConnected,
  IconRefresh,
  IconSearch,
  IconShieldCheck,
  IconTrash,
  IconUserPlus,
  IconWifi,
  IconWifiOff,
} from '@tabler/icons-react';
import {
  apiRequest,
  clearStoredUser,
  getStoredUser,
  storeUser,
} from './api';

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

function formatDate(value) {
  if (!value) {
    return '-';
  }
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value));
}

function AuthScreen({ onLogin }) {
  const [mode, setMode] = useState('login');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [passwordConfirm, setPasswordConfirm] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

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
      onLogin(user);
    } catch (err) {
      setError(err.message);
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

          <Button
            variant="subtle"
            leftSection={<IconUserPlus size={18} />}
            onClick={() => setMode(mode === 'login' ? 'register' : 'login')}
          >
            {mode === 'login' ? 'Create first user' : 'Use existing account'}
          </Button>
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

function DeviceModal({ device, opened, onClose, onSaved }) {
  const [name, setName] = useState('');
  const [known, setKnown] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (device) {
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
        body: { name, known },
      });
      await onSaved();
      onClose();
    } catch (err) {
      setError(err.message);
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
      await apiRequest(`device/?id=${device.id}`, { method: 'DELETE' });
      await onSaved();
      onClose();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal opened={opened} onClose={onClose} title={device?.name} centered>
      <Stack>
        {error && (
          <Alert color="red" icon={<IconAlertCircle size={18} />}>
            {error}
          </Alert>
        )}
        <TextInput label="Name" value={name} onChange={(e) => setName(e.currentTarget.value)} />
        <Switch label="Known device" checked={known} onChange={(e) => setKnown(e.currentTarget.checked)} />
        <Divider />
        <Group justify="space-between">
          <Button color="red" variant="light" leftSection={<IconTrash size={18} />} onClick={remove} loading={saving}>
            Delete
          </Button>
          <Button onClick={save} loading={saving}>
            Save
          </Button>
        </Group>
      </Stack>
    </Modal>
  );
}

function Dashboard({ user, onLogout }) {
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState('');
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
  const [search, setSearch] = useState('');
  const [deviceStatus, setDeviceStatus] = useState('');
  const [devicePage, setDevicePage] = useState(1);
  const [devicePageSize, setDevicePageSize] = useState('10');
  const [eventType, setEventType] = useState('');
  const [scanRange, setScanRange] = useState('');
  const [activeDevice, setActiveDevice] = useState(null);
  const [modalOpened, modal] = useDisclosure(false);
  const [logoutModalOpened, logoutModal] = useDisclosure(false);
  const tableStateRef = useRef({
    search: '',
    deviceStatus: '',
    eventType: '',
    deviceLimit: 10,
    deviceOffset: 0,
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

  useEffect(() => {
    tableStateRef.current = {
      search,
      deviceStatus,
      eventType,
      deviceLimit,
      deviceOffset,
    };
  }, [search, deviceStatus, eventType, deviceLimit, deviceOffset]);

  async function loadData({ quiet = false } = {}) {
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
      };
      const eventParams = {
        event_type: currentTableState.eventType || undefined,
        limit: 12,
      };

      const [deviceData, statusData, runData, eventData, notificationData] =
        await Promise.all([
          apiRequest('device/', { params: deviceParams }),
          apiRequest('scan/status/'),
          apiRequest('scan/runs/', { params: { limit: 8 } }),
          apiRequest('events/', { params: eventParams }),
          apiRequest('notifications/', { params: { limit: 8 } }),
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
    } catch (err) {
      setError(err.message);
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
    const timer = window.setTimeout(() => loadData({ quiet: true }), 250);
    return () => window.clearTimeout(timer);
  }, [search, deviceStatus, eventType, devicePage, devicePageSize]);

  useEffect(() => {
    setDevicePage(1);
  }, [search, deviceStatus, devicePageSize]);

  async function runScan() {
    setRefreshing(true);
    setError('');
    try {
      await apiRequest('scan/', {
        method: 'POST',
        body: scanRange ? { ip_range: scanRange } : {},
      });
      await loadData({ quiet: true });
    } catch (err) {
      setError(err.message);
    } finally {
      setRefreshing(false);
    }
  }

  function logout() {
    clearStoredUser();
    onLogout();
  }

  return (
    <main className="shell">
      <header className="topbar">
        <Container size="xl" py="sm">
          <Group justify="space-between">
            <Group gap="sm">
              <Image src="/logo.png" alt="LanGuard" w={42} h={42} radius="sm" />
              <Box>
                <Title order={3}>LanGuard</Title>
                <Text size="xs" c="dimmed">
                  Signed in as {user.username}
                </Text>
              </Box>
            </Group>
            <Group gap="xs">
              <Tooltip label="Refresh">
                <ActionIcon variant="light" size="lg" onClick={() => loadData({ quiet: true })} loading={refreshing}>
                  <IconRefresh size={19} />
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
              <Group justify="space-between" p="md">
                <Group>
                  <IconNetwork size={22} />
                  <Title order={4}>Devices</Title>
                </Group>
                <Group>
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
                          <Table.Th className="device-name-cell">Name</Table.Th>
                          <Table.Th className="device-ip-cell">IP</Table.Th>
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
                              <span className="truncate-cell" title={device.name}>
                                {device.name}
                              </span>
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
              <Divider />
              <Group justify="space-between" p="md">
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
                  placeholder="Use backend default"
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

          <Tabs defaultValue="events">
            <Tabs.List>
              <Tabs.Tab value="events" leftSection={<IconBell size={16} />}>Events</Tabs.Tab>
              <Tabs.Tab value="history" leftSection={<IconHistory size={16} />}>Scan history</Tabs.Tab>
              <Tabs.Tab value="notifications" leftSection={<IconBell size={16} />}>Notifications</Tabs.Tab>
            </Tabs.List>

            <Tabs.Panel value="events" pt="md">
              <Paper className="content-panel" radius="md" p="md">
                <Group justify="space-between" mb="md">
                  <Title order={4}>Network events</Title>
                  <Select
                    w={210}
                    placeholder="Event type"
                    clearable
                    data={eventTypeOptions}
                    value={eventType}
                    onChange={(value) => setEventType(value || '')}
                  />
                </Group>
                <Stack gap="xs">
                  {events.map((event) => (
                    <EventItem key={event.id} event={event} />
                  ))}
                </Stack>
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

function EventItem({ event }) {
  return (
    <Paper withBorder radius="md" p="sm">
      <Group justify="space-between" align="flex-start">
        <Box>
          <Text fw={600}>{event.message}</Text>
          <Text size="xs" c="dimmed">
            {event.event_type_display || event.event_type} · {formatDate(event.created_at)}
          </Text>
        </Box>
        <Badge color={event.notified ? 'teal' : 'gray'} variant="light">
          {event.notified ? 'Notified' : 'Pending'}
        </Badge>
      </Group>
    </Paper>
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

  return <Dashboard user={user} onLogout={() => setUser(null)} />;
}
