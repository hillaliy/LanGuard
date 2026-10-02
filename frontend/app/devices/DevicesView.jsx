'use client';

import {
  ActionIcon,
  Badge,
  Box,
  Button,
  Checkbox,
  Divider,
  Group,
  MultiSelect,
  Paper,
  SegmentedControl,
  Select,
  SimpleGrid,
  Stack,
  Text,
  TextInput,
  Title,
  Tooltip,
  UnstyledButton,
} from '@mantine/core';
import {
  IconArrowLeft,
  IconArrowRight,
  IconCheck,
  IconEdit,
  IconExternalLink,
  IconNetwork,
  IconSearch,
  IconShieldCheck,
  IconUserPlus,
  IconX,
} from '@tabler/icons-react';

import {
  DeviceClassificationBadge,
  GatewayBadge,
  RiskBadge,
} from '../components/DeviceBadges';
import DeviceIconStack, { normalizeDeviceIcon } from '../components/DeviceIconStack';
import PortSummary from '../components/PortGuidance';
import { formatDate } from '../utils/date';
import {
  deviceStatus,
  displayDeviceName,
  formatRoleLabel,
  validExternalUrl,
} from '../utils/device';

const deviceStatusOptions = [
  { value: 'online', label: 'Online' },
  { value: 'offline', label: 'Offline' },
  { value: 'attention', label: 'Needs attention' },
  { value: 'new', label: 'New devices' },
  { value: 'visitors', label: 'Visitors' },
  { value: 'archived', label: 'Archived' },
];

const firstSeenPeriodOptions = [
  { value: 'today', label: 'Today' },
  { value: '7d', label: 'Last 7 days' },
  { value: '30d', label: 'Last 30 days' },
];

const homeBoxLinkOptions = [
  { value: 'linked', label: 'Linked' },
  { value: 'not-linked', label: 'Not linked' },
];

const inventoryViewOptions = [
  { value: 'table', label: 'List' },
  { value: 'roles', label: 'Roles' },
];

function compactFilterWidth(options, value, placeholder, min = 110, max = 176) {
  const label = options.find((option) => option.value === value)?.label || placeholder;
  const actionSpace = value ? 72 : 40;
  return Math.min(max, Math.max(min, Math.ceil(label.length * 6.5 + actionSpace)));
}
function DeviceListIcon({ device, className, size, interfaceEnabled = true }) {
  const externalUrl = String(
    device?.effective_external_url || device?.external_url || ''
  ).trim();
  const icon = <DeviceIconStack device={device} size={size} />;
  if (!interfaceEnabled || !externalUrl || !validExternalUrl(externalUrl)) {
    return <span className={className}>{icon}</span>;
  }

  return (
    <Tooltip label="Open device interface">
      <UnstyledButton
        component="a"
        className={`${className} device-interface-icon`}
        href={externalUrl}
        target="_blank"
        rel="noopener noreferrer"
        aria-label={`Open ${displayDeviceName(device)} interface in a new tab`}
        onClick={(event) => event.stopPropagation()}
        onKeyDown={(event) => event.stopPropagation()}
      >
        {icon}
        <span className="device-interface-marker" aria-hidden="true">
          <IconExternalLink size={10} stroke={2.5} />
        </span>
      </UnstyledButton>
    </Tooltip>
  );
}

function deviceSubtitle(device) {
  const hostname = String(device?.hostname || '').trim();
  const vendor = String(device?.vendor || '').trim();
  return [hostname, vendor].filter(Boolean).join(' - ') || '-';
}

function isPortGuidanceInteraction(event) {
  const pathIncludesGuidance = event.nativeEvent.composedPath().some(
    (node) => node?.classList?.contains('port-guidance-control')
  );
  if (pathIncludesGuidance) return true;

  const { clientX, clientY } = event.nativeEvent;
  return Array.from(event.currentTarget.querySelectorAll('.port-guidance-control')).some(
    (node) => {
      const bounds = node.getBoundingClientRect();
      return (
        clientX >= bounds.left
        && clientX <= bounds.right
        && clientY >= bounds.top
        && clientY <= bounds.bottom
      );
    }
  );
}

function deviceMapShape(device) {
  const icon = normalizeDeviceIcon(device.icon);
  if (device.is_gateway) {
    return 'router';
  }
  if (!device.known || icon === 'unknown') {
    return 'unknown';
  }
  if (icon === 'router') {
    return 'router';
  }
  if (['server', 'nas'].includes(icon)) {
    return 'server';
  }
  if (['smart-hub', 'phone', 'tablet', 'smart-watch', 'robot-vacuum', 'power-strip', 'smart-power-strip', 'smart-relay', 'power-meter', 'game-console', 'lock'].includes(icon)) {
    return 'compact';
  }
  if (['tv', 'streamer', 'security-camera'].includes(icon)) {
    return 'media';
  }
  return 'device';
}

function NetworkMapDeviceNode({ device, onSelectDevice }) {
  const status = deviceStatus(device);

  return (
    <UnstyledButton
      component="div"
      key={device.id}
      className={`network-device-node ${deviceMapShape(device)} ${device.online ? 'online' : 'offline'}`}
      role="button"
      tabIndex={0}
      onClick={(event) => {
        if (!isPortGuidanceInteraction(event)) {
          onSelectDevice(device);
        }
      }}
      onKeyDown={(event) => {
        if (
          !isPortGuidanceInteraction(event)
          && (event.key === 'Enter' || event.key === ' ')
        ) {
          event.preventDefault();
          onSelectDevice(device);
        }
      }}
    >
      <Group justify="space-between" align="flex-start" wrap="nowrap">
        <span className="network-device-icon">
          <DeviceIconStack device={device} size={22} />
        </span>
        <Group gap={4} justify="flex-end" wrap="wrap">
          <RiskBadge device={device} compact />
          <Badge color={status.color} variant="light">
            {status.label}
          </Badge>
        </Group>
      </Group>
      <Text fw={800} className="network-node-name">{displayDeviceName(device)}</Text>
      <Text size="xs" className="mobile-mono-value">{device.ip}</Text>
      <div className="network-device-ports">
        <PortSummary ports={device.open_ports || []} />
      </div>
    </UnstyledButton>
  );
}


function buildRoleSections(devices) {
  const sectionsByRole = new Map();

  devices.forEach((device) => {
    const role = device.role || 'device';
    const roleLabel = formatRoleLabel(role);
    if (!sectionsByRole.has(roleLabel)) {
      sectionsByRole.set(roleLabel, []);
    }
    sectionsByRole.get(roleLabel).push(device);
  });

  return Array.from(sectionsByRole.entries())
    .map(([role, roleDevices]) => ({
      role,
      devices: roleDevices.sort((left, right) =>
        String(left.name || left.ip || '').localeCompare(String(right.name || right.ip || ''))
      ),
    }))
    .sort((left, right) => left.role.localeCompare(right.role));
}

function RolesMap({ devices = [], onSelectDevice }) {
  const roleSections = buildRoleSections(devices);

  return (
    <Paper className="rooms-map-panel" radius="md">
      <div className="rooms-map">
        {roleSections.length ? (
          <div className="rooms-map-list">
            {roleSections.map((section) => (
              <section className="rooms-map-room" key={section.role}>
                <Group justify="space-between" align="center" mb="sm" wrap="nowrap">
                  <Group gap="xs" wrap="nowrap" className="rooms-map-title">
                    <span className="rooms-map-icon">
                      <IconNetwork size={22} />
                    </span>
                    <Text fw={800} className="rooms-map-room-name">{section.role}</Text>
                  </Group>
                  <Badge variant="light" color="indigo">
                    {section.devices.length}
                  </Badge>
                </Group>
                <div className="network-device-grid">
                  {section.devices.map((device) => (
                    <NetworkMapDeviceNode
                      key={device.id}
                      device={device}
                      onSelectDevice={onSelectDevice}
                    />
                  ))}
                </div>
              </section>
            ))}
          </div>
        ) : (
          <Text c="dimmed" ta="center" py="xl">
            No devices to show.
          </Text>
        )}
      </div>
    </Paper>
  );
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

function sortableOrderingDescendingFirst(field, currentOrdering) {
  if (currentOrdering === `-${field}`) {
    return field;
  }
  if (currentOrdering === field) {
    return '';
  }
  return `-${field}`;
}

function DeviceStatusInline({ device, muted = false }) {
  const status = deviceStatus(device);
  return (
    <Group className="device-status-inline" gap="xs" wrap="nowrap">
      <span className={`status-dot ${status.dot}`} />
      <Text size="sm" c={muted ? 'dimmed' : undefined}>{status.label}</Text>
    </Group>
  );
}

export default function DevicesView({
  devices = [],
  roleDevices = [],
  roleDeviceCount = 0,
  inventoryView,
  onInventoryViewChange,
  filters,
  bulkEdit,
  ordering,
  pagination,
  showHomeBoxFilter,
  showFirstSeen,
  timeZone,
  listRef,
  onSelectDevice,
}) {
  const {
    deviceStatus,
    onDeviceStatusChange,
    networkRangeOptions,
    networkRangeFilter,
    onNetworkRangeFilterChange,
    firstSeenPeriod,
    onFirstSeenPeriodChange,
    homeBoxLinkStatus,
    onHomeBoxLinkStatusChange,
    search,
    onSearchChange,
  } = filters;
  const {
    enabled: bulkEditEnabled,
    selectedDeviceIds,
    updating: bulkUpdatingDevices,
    canEditDevices,
    onToggleDevice: toggleBulkDevice,
    onToggleAll: toggleAllBulkDevices,
    onClose: closeBulkEdit,
    onUpdate: updateSelectedDevices,
    onEnable: enableBulkEdit,
  } = bulkEdit;
  const {
    value: deviceOrdering,
    onChange: setDeviceOrdering,
  } = ordering;
  const {
    data: devicePagination,
    limit: deviceLimit,
    onLimitChange: setDeviceLimit,
    onOffsetChange: setDeviceOffset,
    loading,
    refreshing,
  } = pagination;

  const filteredDevices = devices;
  const selectableDeviceIds = filteredDevices.map((device) => device.id);
  const allSelectableDevicesSelected = Boolean(
    selectableDeviceIds.length
    && selectableDeviceIds.every((deviceId) => selectedDeviceIds.includes(deviceId))
  );
  const someSelectableDevicesSelected = selectedDeviceIds.length > 0;
  const deviceCount = devicePagination.count || 0;
  const deviceStart = deviceCount ? devicePagination.offset + 1 : 0;
  const deviceEnd = Math.min(devicePagination.offset + filteredDevices.length, deviceCount);
  const currentDevicePage = Math.floor(devicePagination.offset / deviceLimit) + 1;
  const devicePageCount = Math.max(1, Math.ceil(deviceCount / deviceLimit));
  const deviceRangeLabel = `Showing ${deviceStart}-${deviceEnd} of ${deviceCount} devices`;
  const selectedDeviceStatus =
    deviceStatusOptions.find((option) => option.value === deviceStatus) || null;
  const deviceStatusFilterWidth = compactFilterWidth(
    deviceStatusOptions,
    deviceStatus,
    'Status'
  );
  const firstSeenFilterWidth = compactFilterWidth(
    firstSeenPeriodOptions,
    firstSeenPeriod,
    'First seen'
  );
  const homeBoxFilterWidth = compactFilterWidth(
    homeBoxLinkOptions,
    homeBoxLinkStatus,
    'HomeBox'
  );
  const setInventoryView = onInventoryViewChange;
  const setDeviceStatus = onDeviceStatusChange;
  const setNetworkRangeFilter = onNetworkRangeFilterChange;
  const setFirstSeenPeriod = onFirstSeenPeriodChange;
  const setHomeBoxLinkStatus = onHomeBoxLinkStatusChange;
  const setSearch = onSearchChange;
  const deviceListRef = listRef;
  const openDevicePage = onSelectDevice;
  const displayTimeZone = timeZone;
  const setBulkEditEnabled = (enabled) => {
    if (enabled) enableBulkEdit();
    else closeBulkEdit();
  };

  return (
    <Paper className="content-panel devices-content-panel" radius="md">
                <Stack gap={0}>
                  <Group className="devices-panel-header" justify="space-between" p="md">
                    <Group className="devices-panel-heading">
                      <IconNetwork size={22} />
                      <Title order={4}>Devices</Title>
                    </Group>
                    <SegmentedControl
                      className="device-view-control"
                      data={inventoryViewOptions}
                      value={inventoryView}
                      onChange={setInventoryView}
                      aria-label="Inventory view"
                    />
                    <Group className={`devices-panel-controls ${showHomeBoxFilter ? 'with-homebox' : ''}`}>
                      <Select
                        className="device-status-filter"
                        w={deviceStatusFilterWidth}
                        placeholder="Status"
                        clearable
                        data={deviceStatusOptions}
                        value={deviceStatus}
                        aria-label={selectedDeviceStatus?.label || 'Status'}
                        onChange={(value) => setDeviceStatus(value || '')}
                      />
                      <MultiSelect
                        className="device-network-filter"
                        w={210}
                        placeholder="Network ranges"
                        clearable
                        searchable
                        hidePickedOptions
                        comboboxProps={{ width: 340 }}
                        data={networkRangeOptions}
                        value={networkRangeFilter}
                        aria-label="Filter by network ranges"
                        onChange={setNetworkRangeFilter}
                        maxDropdownHeight={260}
                        styles={{ option: { whiteSpace: 'nowrap' } }}
                      />
                      <Select
                        className="device-first-seen-filter"
                        w={firstSeenFilterWidth}
                        placeholder="First seen"
                        clearable
                        data={firstSeenPeriodOptions}
                        value={firstSeenPeriod}
                        aria-label="Filter by first seen"
                        onChange={(value) => setFirstSeenPeriod(value || '')}
                      />
                      {showHomeBoxFilter && (
                        <Select
                          className="device-homebox-filter"
                          w={homeBoxFilterWidth}
                          placeholder="HomeBox"
                          clearable
                          data={homeBoxLinkOptions}
                          value={homeBoxLinkStatus}
                          aria-label="Filter by HomeBox link"
                          onChange={(value) => setHomeBoxLinkStatus(value || '')}
                        />
                      )}
                      <TextInput
                        className="device-search"
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
                  {inventoryView === 'roles' ? (
                    <Box p="md">
                      <RolesMap
                        devices={roleDevices}
                        onSelectDevice={openDevicePage}
                      />
                      <Text size="xs" c="dimmed" mt="sm">
                        {roleDeviceCount > roleDevices.length
                          ? `Showing ${roleDevices.length} of ${roleDeviceCount} devices grouped by role.`
                          : `Showing ${roleDevices.length} ${roleDevices.length === 1 ? 'device' : 'devices'} grouped by role.`}
                      </Text>
                    </Box>
                  ) : (
                    <>
                      <Box className="device-list-toolbar" p="md">
                        <Group justify="space-between" wrap="wrap" gap="sm">
                          <Group gap="xs">
                            {bulkEditEnabled && (
                              <Checkbox
                                label="Select all"
                                checked={allSelectableDevicesSelected}
                                indeterminate={
                                  someSelectableDevicesSelected && !allSelectableDevicesSelected
                                }
                                disabled={!selectableDeviceIds.length}
                                onChange={toggleAllBulkDevices}
                              />
                            )}
                            <Button
                              size="xs"
                              variant={deviceOrdering === 'name' ? 'light' : 'subtle'}
                              onClick={() => setDeviceOrdering(sortableOrdering('name', deviceOrdering))}
                            >
                              Name
                            </Button>
                            <Button
                              size="xs"
                              variant={deviceOrdering === 'ip' ? 'light' : 'subtle'}
                              onClick={() => setDeviceOrdering(sortableOrdering('ip', deviceOrdering))}
                            >
                              IP
                            </Button>
                            <Button
                              size="xs"
                              variant={deviceOrdering === '-lastseen' ? 'light' : 'subtle'}
                              onClick={() => setDeviceOrdering(sortableOrdering('lastseen', deviceOrdering))}
                            >
                              Last seen
                            </Button>
                            <Button
                              size="xs"
                              variant={
                                deviceOrdering === 'firstseen' || deviceOrdering === '-firstseen'
                                  ? 'light'
                                  : 'subtle'
                              }
                              onClick={() =>
                                setDeviceOrdering(
                                  sortableOrderingDescendingFirst('firstseen', deviceOrdering)
                                )
                              }
                            >
                              First seen
                            </Button>
                          </Group>
                          <Group gap="sm" wrap="wrap">
                            {bulkEditEnabled ? (
                              <>
                                <Text size="sm" c="dimmed">
                                  {selectedDeviceIds.length} selected
                                </Text>
                                <Button size="xs" variant="default" onClick={closeBulkEdit}>
                                  Cancel
                                </Button>
                                <Button
                                  size="xs"
                                  leftSection={<IconShieldCheck size={16} />}
                                  disabled={!selectedDeviceIds.length}
                                  loading={bulkUpdatingDevices}
                                  onClick={() => updateSelectedDevices('known')}
                                >
                                  Mark as known
                                </Button>
                                <Button
                                  size="xs"
                                  variant="light"
                                  leftSection={<IconUserPlus size={16} />}
                                  disabled={!selectedDeviceIds.length}
                                  loading={bulkUpdatingDevices}
                                  onClick={() => updateSelectedDevices('visitor')}
                                >
                                  Mark as visitor
                                </Button>
                                <Button
                                  size="xs"
                                  variant="light"
                                  leftSection={<IconCheck size={16} />}
                                  disabled={!selectedDeviceIds.length}
                                  loading={bulkUpdatingDevices}
                                  onClick={() => updateSelectedDevices('attention')}
                                >
                                  Mark attention as reviewed
                                </Button>
                              </>
                            ) : (
                              <>
                                <Text size="sm" c="dimmed">
                                  {deviceRangeLabel}
                                </Text>
                                {canEditDevices && (
                                  <Button
                                    size="xs"
                                    variant="light"
                                    leftSection={<IconEdit size={16} />}
                                    disabled={!filteredDevices.length}
                                    onClick={() => setBulkEditEnabled(true)}
                                  >
                                    Bulk edit
                                  </Button>
                                )}
                              </>
                            )}
                          </Group>
                        </Group>
                      </Box>
                      <Stack ref={deviceListRef} className="device-list" gap={0}>
                        {filteredDevices.map((device) => (
                          <UnstyledButton
                            component="div"
                            className={`device-list-row${bulkEditEnabled ? ' bulk-edit' : ''}${selectedDeviceIds.includes(device.id) ? ' selected' : ''}`}
                            key={device.id}
                            role={bulkEditEnabled ? 'checkbox' : 'button'}
                            aria-label={
                              bulkEditEnabled
                                ? `Select ${displayDeviceName(device)}`
                                : `Open ${displayDeviceName(device)} details`
                            }
                            aria-checked={bulkEditEnabled ? selectedDeviceIds.includes(device.id) : undefined}
                            tabIndex={0}
                            onClick={(event) => {
                              if (isPortGuidanceInteraction(event)) return;
                              if (bulkEditEnabled) {
                                toggleBulkDevice(device);
                              } else {
                                openDevicePage(device);
                              }
                            }}
                            onKeyDown={(event) => {
                              if (isPortGuidanceInteraction(event)) return;
                              if (event.key === 'Enter' || event.key === ' ') {
                                event.preventDefault();
                                if (bulkEditEnabled) {
                                  toggleBulkDevice(device);
                                } else {
                                  openDevicePage(device);
                                }
                              }
                            }}
                          >
                            {bulkEditEnabled && (
                              <Checkbox
                                checked={selectedDeviceIds.includes(device.id)}
                                readOnly
                                tabIndex={-1}
                                aria-label={`Select ${displayDeviceName(device)}`}
                                pointerEvents="none"
                              />
                            )}
                            <Group className="device-list-primary" gap="md" align="center" wrap="nowrap">
                              <DeviceListIcon
                                device={device}
                                className="device-list-icon"
                                size={21}
                                interfaceEnabled={!bulkEditEnabled}
                              />
                              <Box className="device-list-title">
                                <Group gap="xs" wrap="nowrap">
                                  <Text fw={800} className="truncate-cell">{displayDeviceName(device)}</Text>
                                  <Stack className="device-list-state-badges" gap={4}>
                                    <DeviceClassificationBadge device={device} />
                                    <GatewayBadge device={device} compact />
                                  </Stack>
                                </Group>
                                <Text size="sm" c="dimmed" className="truncate-cell">
                                  {deviceSubtitle(device)}
                                </Text>
                              </Box>
                            </Group>
                            <div className="device-list-meta">
                              <Box>
                                <Text size="xs" c="dimmed">Status</Text>
                                <DeviceStatusInline device={device} muted />
                              </Box>
                              <Box>
                                <Text size="xs" c="dimmed">IP / MAC</Text>
                                <Text size="sm" fw={700} className="mobile-mono-value device-list-ip-value">{device.ip}</Text>
                                <Text size="xs" c="dimmed" className="mobile-mono-value device-list-mac-value">
                                  {device.mac || '-'}
                                </Text>
                              </Box>
                              <Box>
                                <Text size="xs" c="dimmed">Room</Text>
                                <Text className="device-list-meta-value">{device.room || '-'}</Text>
                              </Box>
                              <Box>
                                <Text size="xs" c="dimmed">Role</Text>
                                <Text className="device-list-meta-value">{formatRoleLabel(device.role)}</Text>
                              </Box>
                              <Box>
                                <Text size="xs" c="dimmed">Ports</Text>
                                <PortSummary ports={device.open_ports || []} />
                              </Box>
                              <Box>
                                <Text size="xs" c="dimmed">Risk</Text>
                                <RiskBadge device={device} compact />
                              </Box>
                              <Box className="device-list-last-seen">
                                <Text size="xs" c="dimmed">
                                  {showFirstSeen ? 'First seen' : 'Last seen'}
                                </Text>
                                <Text className="device-list-last-seen-value">
                                  {formatDate(
                                    showFirstSeen ? device.firstseen : device.lastseen,
                                    displayTimeZone
                                  )}
                                </Text>
                              </Box>
                            </div>
                          </UnstyledButton>
                        ))}
                      </Stack>
                      <Box className="device-mobile-sort-toolbar" p="md">
                        <Group justify="space-between" align="center" wrap="wrap" gap="sm">
                          <Group className="device-mobile-sort-buttons" gap="xs" wrap="wrap">
                            <Button
                              size="xs"
                              variant={deviceOrdering === 'name' ? 'light' : 'subtle'}
                              onClick={() => setDeviceOrdering(sortableOrdering('name', deviceOrdering))}
                            >
                              Name
                            </Button>
                            <Button
                              size="xs"
                              variant={deviceOrdering === 'ip' ? 'light' : 'subtle'}
                              onClick={() => setDeviceOrdering(sortableOrdering('ip', deviceOrdering))}
                            >
                              IP
                            </Button>
                            <Button
                              size="xs"
                              variant={deviceOrdering === '-lastseen' ? 'light' : 'subtle'}
                              onClick={() => setDeviceOrdering(sortableOrdering('lastseen', deviceOrdering))}
                            >
                              Last seen
                            </Button>
                            <Button
                              size="xs"
                              variant={
                                deviceOrdering === 'firstseen' || deviceOrdering === '-firstseen'
                                  ? 'light'
                                  : 'subtle'
                              }
                              onClick={() =>
                                setDeviceOrdering(
                                  sortableOrderingDescendingFirst('firstseen', deviceOrdering)
                                )
                              }
                            >
                              First seen
                            </Button>
                          </Group>
                          <Text size="sm" c="dimmed">
                            {deviceRangeLabel}
                          </Text>
                        </Group>
                      </Box>
                      <Stack className="device-mobile-list" gap={0}>
                        {filteredDevices.map((device) => (
                          <UnstyledButton
                            component="div"
                            className={`device-mobile-row${bulkEditEnabled ? ' bulk-edit' : ''}${selectedDeviceIds.includes(device.id) ? ' selected' : ''}`}
                            key={device.id}
                            role={bulkEditEnabled ? 'checkbox' : 'button'}
                            aria-label={
                              bulkEditEnabled
                                ? `Select ${displayDeviceName(device)}`
                                : `Open ${displayDeviceName(device)} details`
                            }
                            aria-checked={bulkEditEnabled ? selectedDeviceIds.includes(device.id) : undefined}
                            tabIndex={0}
                            onClick={(event) => {
                              if (isPortGuidanceInteraction(event)) return;
                              if (bulkEditEnabled) {
                                toggleBulkDevice(device);
                              } else {
                                openDevicePage(device);
                              }
                            }}
                            onKeyDown={(event) => {
                              if (isPortGuidanceInteraction(event)) return;
                              if (event.key === 'Enter' || event.key === ' ') {
                                event.preventDefault();
                                if (bulkEditEnabled) {
                                  toggleBulkDevice(device);
                                } else {
                                  openDevicePage(device);
                                }
                              }
                            }}
                          >
                            <Group justify="space-between" align="flex-start" wrap="nowrap">
                              <Group gap="sm" align="flex-start" wrap="nowrap" className="device-mobile-main">
                                {bulkEditEnabled && (
                                  <Checkbox
                                    checked={selectedDeviceIds.includes(device.id)}
                                    readOnly
                                    tabIndex={-1}
                                    aria-label={`Select ${displayDeviceName(device)}`}
                                    pointerEvents="none"
                                  />
                                )}
                                <DeviceListIcon
                                  device={device}
                                  className="device-mobile-icon"
                                  size={18}
                                  interfaceEnabled={!bulkEditEnabled}
                                />
                                <Box className="device-mobile-title">
                                  <Text fw={700} className="truncate-cell">{displayDeviceName(device)}</Text>
                                  <DeviceStatusInline device={device} muted />
                                </Box>
                              </Group>
                              <Group className="device-mobile-badges" gap={6} justify="flex-end" wrap="wrap">
                                <RiskBadge device={device} compact />
                                <GatewayBadge device={device} compact />
                                <DeviceClassificationBadge device={device} />
                              </Group>
                            </Group>
                            <SimpleGrid className="device-mobile-details" cols={2} spacing="xs" mt="sm">
                              <Box>
                                <Text size="xs" c="dimmed">IP / MAC</Text>
                                <Text size="sm" className="mobile-mono-value">{device.ip}</Text>
                                <Text size="xs" c="dimmed" className="mobile-mono-value device-list-mac-value">
                                  {device.mac || '-'}
                                </Text>
                              </Box>
                              <Box>
                                <Text size="xs" c="dimmed">
                                  {showFirstSeen ? 'First seen' : 'Last seen'}
                                </Text>
                                <Text size="sm">
                                  {formatDate(
                                    showFirstSeen ? device.firstseen : device.lastseen,
                                    displayTimeZone
                                  )}
                                </Text>
                              </Box>
                              <Box className="device-mobile-wide">
                                <Text size="xs" c="dimmed">Room</Text>
                                <Text size="sm">{device.room || '-'}</Text>
                              </Box>
                              <Box className="device-mobile-wide">
                                <Text size="xs" c="dimmed">Role</Text>
                                <Text size="sm">{formatRoleLabel(device.role)}</Text>
                              </Box>
                              <Box className="device-mobile-wide">
                                <Text size="xs" c="dimmed">Ports</Text>
                                <PortSummary ports={device.open_ports || []} />
                              </Box>
                            </SimpleGrid>
                          </UnstyledButton>
                        ))}
                      </Stack>
                      <Box className="device-pagination" p="md">
                        <Group justify="space-between" align="flex-end" wrap="wrap" gap="sm">
                          <Select
                            className="device-page-size"
                            w={120}
                            label="Per page"
                            allowDeselect={false}
                            data={['25', '50', '75', '100']}
                            value={String(deviceLimit)}
                            onChange={(value) => setDeviceLimit(Number(value || 100))}
                          />
                          <Text size="sm" fw={600} className="device-page-number">
                            Page {currentDevicePage} of {devicePageCount}
                          </Text>
                          <Group gap="xs" wrap="nowrap">
                            <Button
                              size="xs"
                              variant="default"
                              leftSection={<IconArrowLeft size={16} />}
                              disabled={
                                devicePagination.previous_offset === null || loading || refreshing
                              }
                              onClick={() => setDeviceOffset(devicePagination.previous_offset)}
                            >
                              Previous
                            </Button>
                            <Button
                              size="xs"
                              variant="default"
                              rightSection={<IconArrowRight size={16} />}
                              disabled={devicePagination.next_offset === null || loading || refreshing}
                              onClick={() => setDeviceOffset(devicePagination.next_offset)}
                            >
                              Next
                            </Button>
                          </Group>
                        </Group>
                      </Box>
                    </>
                  )}
                </Stack>
              </Paper>
  );
}
