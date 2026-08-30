'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import {
  ActionIcon,
  Alert,
  Autocomplete,
  Badge,
  Box,
  Button,
  Checkbox,
  Container,
  Divider,
  FileButton,
  Group,
  Image,
  LoadingOverlay,
  Loader,
  Modal,
  NumberInput,
  Paper,
  PasswordInput,
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
  useMantineColorScheme,
} from '@mantine/core';
import { useDisclosure } from '@mantine/hooks';
import { notifications } from '@mantine/notifications';
import {
  IconAlertCircle,
  IconAirConditioning,
  IconArrowLeft,
  IconArrowsSort,
  IconBell,
  IconBlind,
  IconBrandGithub,
  IconBulb,
  IconBulbFilled,
  IconCast,
  IconClock,
  IconDeviceCctv,
  IconDeviceDesktop,
  IconDeviceLaptop,
  IconDeviceMobile,
  IconDeviceSpeaker,
  IconDeviceTablet,
  IconDeviceTv,
  IconDeviceWatch,
  IconDownload,
  IconEdit,
  IconGripVertical,
  IconHistory,
  IconLamp,
  IconLayoutDashboard,
  IconLine,
  IconLock,
  IconLogout,
  IconMoon,
  IconNetwork,
  IconOutlet,
  IconPrinter,
  IconPropeller,
  IconQuestionMark,
  IconRefresh,
  IconArrowUpRight,
  IconRestore,
  IconRouter,
  IconSearch,
  IconSend,
  IconServer,
  IconDeviceFloppy,
  IconSettings,
  IconShieldCheck,
  IconShieldLock,
  IconSmartHome,
  IconSun,
  IconTemperature,
  IconTrash,
  IconUpload,
  IconUserPlus,
  IconUserMinus,
  IconUserEdit,
  IconVacuumCleaner,
  IconWifi,
  IconWindmill,
  IconWindow,
  IconX,
} from '@tabler/icons-react';
import {
  apiRequest,
  BACKEND_UNAVAILABLE_MESSAGE,
  clearStoredUser,
  getAdminUrl,
  getStoredUser,
  storeUser,
} from './api';
import { APP_VERSION, CHANGELOG_ENTRIES } from './version';

const changelogSeenStorageKey = 'languard_changelog_seen_version';
const versionCheckFallbackInterval = 6 * 60 * 60 * 1000;

function formatRoleLabel(value) {
  return String(value || 'device')
    .replace(/([a-z0-9])([A-Z])/g, '$1 $2')
    .replace(/[-_]+/g, ' ')
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function validExternalUrl(value) {
  const candidate = String(value || '').trim();
  if (!candidate) {
    return true;
  }
  try {
    const url = new URL(candidate);
    return (url.protocol === 'http:' || url.protocol === 'https:') && Boolean(url.hostname);
  } catch {
    return false;
  }
}

function normalizeMacText(value) {
  return String(value || '').trim().toLowerCase();
}

function compactMac(value) {
  return normalizeMacText(value).replace(/[:-]/g, '');
}

function isMacAddressText(value) {
  const compact = compactMac(value);
  return compact.length === 12 && /^[0-9a-f]+$/.test(compact);
}

function isLocallyAdministeredMac(value) {
  const compact = compactMac(value);
  if (compact.length < 2 || !/^[0-9a-f]{2}/.test(compact)) {
    return false;
  }
  return (Number.parseInt(compact.slice(0, 2), 16) & 0x02) === 0x02;
}

function macSuffix(value) {
  return compactMac(value).slice(-4).toUpperCase();
}

function displayDeviceName(device) {
  const name = String(device?.name || '').trim();
  if (name && !isMacAddressText(name)) {
    return name;
  }

  const suffix = macSuffix(device?.mac || name);
  if (!suffix) {
    return name || 'Unknown Device';
  }

  return isLocallyAdministeredMac(device?.mac || name)
    ? `Private Device ${suffix}`
    : `Unknown Device ${suffix}`;
}

function deviceSubtitle(device) {
  const hostname = String(device?.hostname || '').trim();
  const vendor = String(device?.vendor || '').trim();
  const mac = String(device?.mac || '').trim();
  const details = [hostname, vendor].filter(Boolean);

  if (details.length) {
    return details.join(' - ');
  }

  if (isLocallyAdministeredMac(mac)) {
    return `Private/random MAC - ${mac}`;
  }

  return mac || '-';
}

const eventTypeOptions = [
  { value: 'new_device', label: 'New devices' },
  { value: 'device_online', label: 'Online events' },
  { value: 'device_offline', label: 'Offline events' },
  { value: 'port_opened', label: 'Opened ports' },
  { value: 'port_closed', label: 'Closed ports' },
];

const deviceStatusOptions = [
  { value: 'online', label: 'Online' },
  { value: 'offline', label: 'Offline' },
  { value: 'new', label: 'New devices' },
];

const firstSeenPeriodOptions = [
  { value: 'today', label: 'Today' },
  { value: '7d', label: 'Last 7 days' },
  { value: '30d', label: 'Last 30 days' },
];

const deviceRoleOptions = [
  'device',
  'gateway',
  'router',
  'meshRouter',
  'hub',
  'camera',
  'computer',
  'server',
  'phone',
  'tablet',
  'tv',
  'streamer',
  'printer',
  'speaker',
  'light',
  'climate',
  'smartPlug',
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

const inventoryViewOptions = [
  { value: 'table', label: 'List' },
  { value: 'roles', label: 'Roles' },
];

const homeMapFilterOptions = [
  { value: 'all', label: 'All' },
  { value: 'online', label: 'Online' },
  { value: 'offline', label: 'Offline' },
];

const unassignedRoomLabel = 'Unassigned';
const homeMapLayoutStorageKey = 'languard_home_map_layout_v1';

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

function showSuccessNotification(title, message) {
  notifications.show({
    title,
    message,
    color: 'teal',
    icon: <IconShieldCheck size={18} />,
  });
}

function showErrorNotification(title, message) {
  const backendUnavailable = message === BACKEND_UNAVAILABLE_MESSAGE;
  notifications.show({
    title: backendUnavailable ? 'Server unavailable' : title,
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
  { value: 'smart-hub', label: 'Smart hub', icon: IconSmartHome },
  { value: 'phone', label: 'Phone', icon: IconDeviceMobile },
  { value: 'tablet', label: 'Tablet', icon: IconDeviceTablet },
  { value: 'smart-watch', label: 'Smart watch', icon: IconDeviceWatch },
  { value: 'laptop', label: 'Laptop', icon: IconDeviceLaptop },
  { value: 'tv', label: 'TV', icon: IconDeviceTv },
  { value: 'streamer', label: 'Streamer', icon: IconCast },
  { value: 'security-camera', label: 'Security camera', icon: IconDeviceCctv },
  { value: 'shutter', label: 'Shutter', icon: IconWindow },
  { value: 'blinds', label: 'Blinds', icon: IconBlind },
  { value: 'light', label: 'Light', icon: IconBulb },
  { value: 'led-strip', label: 'LED strip', icon: IconLine },
  { value: 'desk-lamp', label: 'Desk lamp', icon: IconLamp },
  { value: 'ceiling-light', label: 'Ceiling light', icon: IconBulbFilled },
  { value: 'air-conditioner', label: 'Air conditioner', icon: IconAirConditioning },
  { value: 'fan', label: 'Fan', icon: IconPropeller },
  { value: 'ceiling-fan', label: 'Ceiling fan', icon: IconWindmill },
  { value: 'thermostat', label: 'Thermostat', icon: IconTemperature },
  { value: 'speaker', label: 'Speaker', icon: IconDeviceSpeaker },
  { value: 'printer', label: 'Printer', icon: IconPrinter },
  { value: 'lock', label: 'Lock', icon: IconLock },
  { value: 'robot-vacuum', label: 'Robot vacuum', icon: IconVacuumCleaner },
  { value: 'power-strip', label: 'Power strip', icon: IconOutlet },
  { value: 'server', label: 'Server', icon: IconServer },
];

function normalizeDeviceIcon(value) {
  const aliases = {
    plus: 'unknown',
    device: 'desktop',
    computer: 'desktop',
    desktopcomputer: 'desktop',
    hub: 'smart-hub',
    'smart-hub': 'smart-hub',
    smarthub: 'smart-hub',
    'smart-home': 'smart-hub',
    smarthome: 'smart-hub',
    aqara: 'smart-hub',
    aqura: 'smart-hub',
    cpu: 'smart-hub',
    'point.3.connected.trianglepath.dotted': 'smart-hub',
    'sensor.tag.radiowaves.forward': 'smart-hub',
    'switch.2': 'smart-hub',
    mobile: 'phone',
    iphone: 'phone',
    ipad: 'tablet',
    pad: 'tablet',
    applewatch: 'smart-watch',
    watch: 'smart-watch',
    smartwatch: 'smart-watch',
    'smart-watch': 'smart-watch',
    wearable: 'smart-watch',
    macbook: 'laptop',
    television: 'tv',
    airplayvideo: 'streamer',
    cast: 'streamer',
    streaming: 'streamer',
    camera: 'security-camera',
    cctv: 'security-camera',
    'video.doorbell': 'security-camera',
    blind: 'blinds',
    'blinds.horizontal.closed': 'shutter',
    shade: 'blinds',
    curtain: 'blinds',
    window: 'shutter',
    'window.shade.closed': 'blinds',
    'roller-shutter': 'shutter',
    rollershutter: 'shutter',
    bulb: 'light',
    lightbulb: 'light',
    'lightbulb.max': 'light',
    'light.panel': 'light',
    'lightswitch.on': 'light',
    led: 'led-strip',
    'led-strip': 'led-strip',
    ledstrip: 'led-strip',
    'light-strip': 'led-strip',
    lightstrip: 'led-strip',
    'strip-light': 'led-strip',
    striplight: 'led-strip',
    'light.strip.2': 'led-strip',
    lamp: 'desk-lamp',
    'lamp.desk': 'desk-lamp',
    'desk-lamp': 'desk-lamp',
    desklamp: 'desk-lamp',
    'table-lamp': 'desk-lamp',
    tablelamp: 'desk-lamp',
    'lamp.ceiling': 'ceiling-light',
    'light.recessed': 'ceiling-light',
    'ceiling-light': 'ceiling-light',
    ceilinglight: 'ceiling-light',
    downlight: 'ceiling-light',
    'air.conditioner.horizontal': 'air-conditioner',
    aircon: 'air-conditioner',
    ac: 'air-conditioner',
    hvac: 'air-conditioner',
    propeller: 'fan',
    'standing-fan': 'fan',
    'floor-fan': 'fan',
    ceilingfan: 'ceiling-fan',
    'cilling-fan': 'ceiling-fan',
    cillingfan: 'ceiling-fan',
    'fan.ceiling': 'ceiling-fan',
    'thermometer.medium': 'thermostat',
    'thermometer-snow': 'thermostat',
    temperature: 'thermostat',
    audio: 'speaker',
    hifispeaker: 'speaker',
    homepod: 'speaker',
    security: 'lock',
    smartlock: 'lock',
    'smart-lock': 'lock',
    lock: 'lock',
    printer: 'printer',
    vacuum: 'robot-vacuum',
    roomba: 'robot-vacuum',
    robot: 'robot-vacuum',
    'robotic.vacuum': 'robot-vacuum',
    'vacuum-cleaner': 'robot-vacuum',
    outlet: 'power-strip',
    socket: 'power-strip',
    plug: 'power-strip',
    powerplug: 'power-strip',
    'poweroutlet.strip': 'power-strip',
    'poweroutlet.type.h': 'power-strip',
    'smart-plug': 'power-strip',
    'plug-strip': 'power-strip',
    'power-outlet': 'power-strip',
    nas: 'server',
    'server.rack': 'server',
    'wifi.router': 'router',
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

function deviceDisplayIcons(device) {
  const primaryIcon = normalizeDeviceIcon(device?.icon);
  const secondaryIcon = normalizeDeviceIcon(device?.secondary_icon);

  if (!secondaryIcon || secondaryIcon === 'unknown' || secondaryIcon === primaryIcon) {
    return [primaryIcon];
  }

  return [primaryIcon, secondaryIcon];
}

function DeviceIconStack({ device, size = 18, className = '' }) {
  const icons = deviceDisplayIcons(device);

  return (
    <span className={`device-icon-stack ${icons.length > 1 ? 'has-secondary' : ''} ${className}`.trim()}>
      {icons.map((icon) => (
        <DeviceIcon key={icon} value={icon} size={size} />
      ))}
    </span>
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
  if (icon === 'server') {
    return 'server';
  }
  if (['smart-hub', 'phone', 'tablet', 'smart-watch', 'robot-vacuum', 'power-strip', 'lock'].includes(icon)) {
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
      key={device.id}
      className={`network-device-node ${deviceMapShape(device)} ${device.online ? 'online' : 'offline'}`}
      onClick={() => onSelectDevice(device)}
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

function getDeviceRoomLabel(device) {
  const room = String(device.room || '').trim();
  return room || 'Unassigned';
}

function buildRoomSections(devices) {
  const sectionsByRoom = new Map();

  devices.forEach((device) => {
    const room = getDeviceRoomLabel(device);
    if (!sectionsByRoom.has(room)) {
      sectionsByRoom.set(room, []);
    }
    sectionsByRoom.get(room).push(device);
  });

  return Array.from(sectionsByRoom.entries())
    .map(([room, roomDevices]) => ({
      room,
      devices: roomDevices.sort((left, right) =>
        String(left.name || left.ip || '').localeCompare(String(right.name || right.ip || ''))
      ),
    }))
    .sort((left, right) => {
      if (left.room === 'Unassigned') return 1;
      if (right.room === 'Unassigned') return -1;
      return left.room.localeCompare(right.room);
    });
}

function homeMapDeviceStatusClass(device) {
  const risk = String(device.risk || '').toLowerCase();
  if (risk === 'high') {
    return 'high-risk';
  }
  if (risk === 'medium') {
    return 'medium-risk';
  }
  if (!device.online) {
    return 'offline';
  }
  return 'healthy';
}

function homeMapAttentionCount(devices = []) {
  return devices.filter((device) => {
    const risk = String(device.risk || '').toLowerCase();
    return !device.online || risk === 'medium' || risk === 'high';
  }).length;
}

function homeMapDeviceMatchesFilter(device, filter) {
  const risk = String(device.risk || '').toLowerCase();
  if (filter === 'online') {
    return Boolean(device.online);
  }
  if (filter === 'offline') {
    return !device.online;
  }
  if (filter === 'attention') {
    return !device.online || risk === 'medium' || risk === 'high';
  }
  return true;
}

function buildHomeMapRooms(devices, filter = 'all') {
  return buildRoomSections(devices).map((section) => ({
    ...section,
    visibleDevices: section.devices.filter((device) => homeMapDeviceMatchesFilter(device, filter)),
    attentionCount: homeMapAttentionCount(section.devices),
  }));
}

function normalizeHomeMapLayout(layout, rooms) {
  const roomNames = new Set(rooms.map((section) => section.room));
  const order = Array.isArray(layout?.order)
    ? layout.order.filter((room, index, values) =>
      roomNames.has(room) && values.indexOf(room) === index
    )
    : [];

  rooms.forEach((section) => {
    if (!order.includes(section.room)) {
      order.push(section.room);
    }
  });

  const parents = {};
  if (layout?.parents && typeof layout.parents === 'object') {
    Object.entries(layout.parents).forEach(([room, parent]) => {
      if (
        roomNames.has(room) &&
        roomNames.has(parent) &&
        room !== parent
      ) {
        parents[room] = parent;
      }
    });
  }

  Object.keys(parents).forEach((room) => {
    const seen = new Set([room]);
    let parent = parents[room];
    while (parent) {
      if (seen.has(parent)) {
        delete parents[room];
        return;
      }
      seen.add(parent);
      parent = parents[parent];
    }
  });

  return { order, parents };
}

function orderHomeMapRooms(rooms, order) {
  const orderIndex = new Map(order.map((room, index) => [room, index]));
  return [...rooms].sort((left, right) => {
    const leftIndex = orderIndex.has(left.room) ? orderIndex.get(left.room) : Number.MAX_SAFE_INTEGER;
    const rightIndex = orderIndex.has(right.room) ? orderIndex.get(right.room) : Number.MAX_SAFE_INTEGER;
    if (leftIndex !== rightIndex) {
      return leftIndex - rightIndex;
    }
    return left.room.localeCompare(right.room);
  });
}

function HomeMapDeviceButton({ device, onSelectDevice }) {
  const status = deviceStatus(device);
  const risk = String(device.risk || '').toLowerCase();
  const vendor = String(device.vendor || '').trim();
  const hostname = String(device.hostname || '').trim();
  const tooltipParts = [
    displayDeviceName(device),
    device.ip,
    status.label,
    vendor,
    hostname,
  ].filter(Boolean);
  const tooltip = tooltipParts.join(' · ');

  return (
    <Tooltip label={tooltip} withArrow>
      <UnstyledButton
        className={`home-map-device ${homeMapDeviceStatusClass(device)}`}
        onClick={() => onSelectDevice(device)}
        aria-label={tooltip}
      >
        <DeviceIconStack device={device} size={20} />
        {(risk === 'medium' || risk === 'high') && (
          <span className={`home-map-device-risk ${risk}`} aria-hidden="true" />
        )}
      </UnstyledButton>
    </Tooltip>
  );
}

function HomeMapRoom({
  section,
  childSections = [],
  draggedRoom,
  editMode = false,
  isNested = false,
  dropTarget,
  onDragStart,
  onDragEnd,
  onDragOverRoom,
  onDropOnRoom,
  onDragLeaveRoom,
  onMoveToRoot,
  onSelectDevice,
}) {
  const roomStatus = section.attentionCount > 0 ? 'attention' : 'healthy';
  const deviceCount = section.devices.length;
  const visibleDevices = section.visibleDevices || section.devices;
  const roomSize = childSections.length
    ? 'zone'
    : deviceCount >= 10
    ? 'large'
    : deviceCount >= 7
      ? 'wide'
      : deviceCount >= 4
        ? 'medium'
        : 'small';

  return (
    <article
      className={`home-map-room ${roomStatus} ${roomSize} ${isNested ? 'nested' : ''} ${editMode ? 'editable' : ''} ${draggedRoom === section.room ? 'dragging' : ''} ${editMode && dropTarget?.room === section.room ? `drop-${dropTarget.position}` : ''}`}
      draggable={editMode}
      onDragStart={editMode ? (event) => onDragStart(event, section.room) : undefined}
      onDragEnd={editMode ? onDragEnd : undefined}
      onDragOver={editMode ? (event) => onDragOverRoom(event, section.room) : undefined}
      onDragLeave={editMode ? onDragLeaveRoom : undefined}
      onDrop={editMode ? (event) => onDropOnRoom(event, section.room) : undefined}
    >
      {editMode && dropTarget?.room === section.room && (
        <span className="home-map-drop-label">
          {dropTarget.position === 'inside'
            ? 'Inside'
            : dropTarget.position === 'before'
              ? 'Before'
              : 'After'}
        </span>
      )}
      <Group justify="space-between" align="flex-start" gap="xs" wrap="nowrap">
        <Box className="home-map-room-title">
          <Group gap={6} wrap="nowrap">
            {editMode && (
              <span className="home-map-room-grip" aria-hidden="true">
                <IconGripVertical size={16} />
              </span>
            )}
            <Text fw={800} className="home-map-room-name">{section.room}</Text>
          </Group>
        </Box>
        {editMode && isNested && (
          <Tooltip label="Move to top level" withArrow>
            <ActionIcon
              aria-label={`Move ${section.room} to top level`}
              className="home-map-room-action"
              color="gray"
              size="sm"
              variant="subtle"
              onClick={(event) => {
                event.stopPropagation();
                onMoveToRoot(section.room);
              }}
              onMouseDown={(event) => event.stopPropagation()}
            >
              <IconArrowUpRight size={16} />
            </ActionIcon>
          </Tooltip>
        )}
      </Group>
      <div className="home-map-device-cloud">
        {visibleDevices.map((device) => (
          <HomeMapDeviceButton
            key={device.id}
            device={device}
            onSelectDevice={onSelectDevice}
          />
        ))}
      </div>
      {childSections.length > 0 && (
        <div className="home-map-child-rooms">
          {childSections.map((childSection) => (
            <HomeMapRoom
              key={childSection.room}
              section={childSection}
              childSections={childSection.children}
              draggedRoom={draggedRoom}
              editMode={editMode}
              isNested
              dropTarget={dropTarget}
              onDragStart={onDragStart}
              onDragEnd={onDragEnd}
              onDragOverRoom={onDragOverRoom}
              onDropOnRoom={onDropOnRoom}
              onDragLeaveRoom={onDragLeaveRoom}
              onMoveToRoot={onMoveToRoot}
              onSelectDevice={onSelectDevice}
            />
          ))}
        </div>
      )}
    </article>
  );
}

function isHomeMapDescendant(room, maybeDescendant, parents) {
  let current = parents[maybeDescendant];
  while (current) {
    if (current === room) {
      return true;
    }
    current = parents[current];
  }
  return false;
}

function HomeMap({ devices = [], onSelectDevice }) {
  const [deviceFilter, setDeviceFilter] = useState('all');
  const rooms = useMemo(() => buildHomeMapRooms(devices, deviceFilter), [deviceFilter, devices]);
  const assignedRooms = useMemo(
    () => rooms.filter((section) => section.room !== unassignedRoomLabel),
    [rooms]
  );
  const unassignedSection = useMemo(
    () => rooms.find((section) => section.room === unassignedRoomLabel),
    [rooms]
  );
  const [layout, setLayout] = useState({ order: [], parents: {} });
  const [layoutEditMode, setLayoutEditMode] = useState(false);
  const [draggedRoom, setDraggedRoom] = useState(null);
  const [dropTarget, setDropTarget] = useState(null);
  const [resetModalOpened, resetModal] = useDisclosure(false);
  const [layoutLoaded, setLayoutLoaded] = useState(false);
  const [layoutSaving, setLayoutSaving] = useState(false);
  const deviceCount = devices.length;
  const roomCount = assignedRooms.length;
  const normalizedLayout = useMemo(
    () => normalizeHomeMapLayout(layout, assignedRooms),
    [assignedRooms, layout]
  );
  const orderedRooms = useMemo(
    () => orderHomeMapRooms(assignedRooms, normalizedLayout.order),
    [assignedRooms, normalizedLayout.order]
  );
  const roomTree = useMemo(() => {
    const sectionsByRoom = new Map(orderedRooms.map((section) => [
      section.room,
      { ...section, children: [] },
    ]));
    const roots = [];

    orderedRooms.forEach((section) => {
      const node = sectionsByRoom.get(section.room);
      const parentRoom = normalizedLayout.parents[section.room];
      const parentNode = sectionsByRoom.get(parentRoom);
      if (parentNode) {
        parentNode.children.push(node);
      } else {
        roots.push(node);
      }
    });

    return roots;
  }, [normalizedLayout.parents, orderedRooms]);

  useEffect(() => {
    let cancelled = false;

    async function loadLayout() {
      try {
        const payload = await apiRequest('home-map-layout/');
        const serverLayout = payload.data?.layout || {};
        const serverHasLayout = Boolean(
          serverLayout &&
          (
            (Array.isArray(serverLayout.order) && serverLayout.order.length > 0) ||
            (serverLayout.parents && Object.keys(serverLayout.parents).length > 0)
          )
        );
        let nextLayout = serverLayout;

        if (!serverHasLayout) {
          try {
            const storedLayout = JSON.parse(localStorage.getItem(homeMapLayoutStorageKey) || '{}');
            const storedHasLayout = Boolean(
              storedLayout &&
              (
                (Array.isArray(storedLayout.order) && storedLayout.order.length > 0) ||
                (storedLayout.parents && Object.keys(storedLayout.parents).length > 0)
              )
            );
            if (storedHasLayout) {
              nextLayout = storedLayout;
            }
          } catch {
            nextLayout = serverLayout;
          }
        }

        if (!cancelled) {
          setLayout(nextLayout && typeof nextLayout === 'object' ? nextLayout : { order: [], parents: {} });
          setLayoutLoaded(true);
        }
      } catch (err) {
        if (!cancelled) {
          setLayoutLoaded(true);
          showErrorNotification('Could not load home map layout', err.message);
        }
      }
    }

    loadLayout();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!layoutLoaded) {
      return;
    }

    const nextLayout = normalizeHomeMapLayout(layout, assignedRooms);
    if (
      JSON.stringify(nextLayout.order) !== JSON.stringify(layout.order) ||
      JSON.stringify(nextLayout.parents) !== JSON.stringify(layout.parents)
    ) {
      setLayout(nextLayout);
    }
  }, [assignedRooms, layout, layoutLoaded]);

  useEffect(() => {
    if (!layoutEditMode) {
      setDraggedRoom(null);
      setDropTarget(null);
    }
  }, [layoutEditMode]);

  const updateHomeMapLayout = (updater) => {
    setLayout((currentLayout) => {
      const normalizedCurrent = normalizeHomeMapLayout(currentLayout, assignedRooms);
      return normalizeHomeMapLayout(updater(normalizedCurrent), assignedRooms);
    });
  };

  const saveHomeMapLayout = async () => {
    const nextLayout = normalizeHomeMapLayout(layout, assignedRooms);
    setLayoutSaving(true);
    try {
      await apiRequest('home-map-layout/', {
        method: 'PUT',
        body: { layout: nextLayout },
      });
      setLayout(nextLayout);
      setLayoutEditMode(false);
      try {
        localStorage.removeItem(homeMapLayoutStorageKey);
      } catch {
        // Ignore cleanup failures; DB storage is authoritative.
      }
      showSuccessNotification('Layout saved', 'Home map layout was updated.');
    } catch (err) {
      showErrorNotification('Could not save home map layout', err.message);
    } finally {
      setLayoutSaving(false);
    }
  };

  const toggleHomeMapEditMode = () => {
    if (!layoutEditMode) {
      setLayoutEditMode(true);
      return;
    }
    saveHomeMapLayout();
  };

  const handleRoomDragStart = (event, room) => {
    setDraggedRoom(room);
    event.dataTransfer.effectAllowed = 'move';
    event.dataTransfer.setData('text/plain', room);
  };

  const handleRoomDragEnd = () => {
    setDraggedRoom(null);
    setDropTarget(null);
  };

  const getRoomDropPosition = (event) => {
    const targetRect = event.currentTarget.getBoundingClientRect();
    const relativeY = (event.clientY - targetRect.top) / Math.max(targetRect.height, 1);
    if (relativeY < 0.25) {
      return 'before';
    }
    if (relativeY > 0.75) {
      return 'after';
    }
    return 'inside';
  };

  const handleDragOverRoom = (event, targetRoom) => {
    event.preventDefault();
    event.stopPropagation();
    const sourceRoom = event.dataTransfer.getData('text/plain') || draggedRoom;
    if (!sourceRoom || sourceRoom === targetRoom) {
      setDropTarget(null);
      return;
    }
    setDropTarget({ room: targetRoom, position: getRoomDropPosition(event) });
  };

  const handleDragLeaveRoom = (event) => {
    if (!event.currentTarget.contains(event.relatedTarget)) {
      setDropTarget(null);
    }
  };

  const handleDropOnRoom = (event, targetRoom) => {
    event.preventDefault();
    event.stopPropagation();
    const sourceRoom = event.dataTransfer.getData('text/plain') || draggedRoom;
    if (!sourceRoom || sourceRoom === targetRoom) {
      setDraggedRoom(null);
      setDropTarget(null);
      return;
    }

    const dropPosition = getRoomDropPosition(event);
    setDraggedRoom(null);
    setDropTarget(null);

    updateHomeMapLayout((currentLayout) => {
      if (isHomeMapDescendant(sourceRoom, targetRoom, currentLayout.parents)) {
        return currentLayout;
      }

      const targetParent = currentLayout.parents[targetRoom] || null;
      const order = currentLayout.order.filter((room) => room !== sourceRoom);
      const targetIndex = order.indexOf(targetRoom);
      const parents = { ...currentLayout.parents };

      if (dropPosition === 'inside') {
        order.splice(targetIndex >= 0 ? targetIndex + 1 : order.length, 0, sourceRoom);
        parents[sourceRoom] = targetRoom;
        return { order, parents };
      }

      order.splice(
        targetIndex >= 0 && dropPosition === 'after' ? targetIndex + 1 : Math.max(targetIndex, 0),
        0,
        sourceRoom
      );
      if (targetParent) {
        parents[sourceRoom] = targetParent;
      } else {
        delete parents[sourceRoom];
      }
      return { order, parents };
    });
  };

  const handleDropOnBuilding = (event) => {
    event.preventDefault();
    setDropTarget(null);
    const sourceRoom = event.dataTransfer.getData('text/plain') || draggedRoom;
    if (!sourceRoom) {
      setDraggedRoom(null);
      return;
    }
    setDraggedRoom(null);

    updateHomeMapLayout((currentLayout) => {
      const parents = { ...currentLayout.parents };
      delete parents[sourceRoom];
      const order = currentLayout.order.filter((room) => room !== sourceRoom);
      order.push(sourceRoom);
      return { order, parents };
    });
  };

  const moveRoomToRoot = (room) => {
    updateHomeMapLayout((currentLayout) => {
      const parents = { ...currentLayout.parents };
      delete parents[room];
      const order = currentLayout.order.filter((item) => item !== room);
      order.push(room);
      return { order, parents };
    });
  };

  const resetHomeMapLayout = () => {
    setDraggedRoom(null);
    setDropTarget(null);
    setLayout({ order: [], parents: {} });
    resetModal.close();
  };

  return (
    <>
      <Paper className="home-map-panel" radius="md">
        <Group justify="space-between" align="center" className="home-map-header" wrap="wrap">
          <Group gap="sm" wrap="nowrap">
            <span className="home-map-header-icon">
              <IconSmartHome size={24} />
            </span>
            <Box>
              <Title order={4}>Home Map</Title>
              <Text size="sm" c="dimmed">
                Rooms and device icons
              </Text>
            </Box>
          </Group>
          <Group gap="xs">
            <Badge variant="light" color="indigo">{roomCount} rooms</Badge>
            <Badge variant="light" color="blue">{deviceCount} devices</Badge>
          </Group>
        </Group>

        {deviceCount ? (
          <div className="home-map-house">
            <Group justify="space-between" className="home-map-controls" wrap="wrap">
              <SegmentedControl
                className="home-map-filter"
                data={homeMapFilterOptions}
                value={deviceFilter}
                onChange={setDeviceFilter}
                size="xs"
              />
              <Group gap="xs">
                {layoutEditMode && (
                  <Button
                    variant="subtle"
                    color="gray"
                    size="xs"
                    leftSection={<IconRestore size={16} />}
                    onClick={resetModal.open}
                  >
                    Reset layout
                  </Button>
                )}
              <Button
                variant={layoutEditMode ? 'filled' : 'light'}
                size="xs"
                leftSection={<IconGripVertical size={16} />}
                loading={layoutSaving}
                onClick={toggleHomeMapEditMode}
              >
                {layoutEditMode ? 'Done' : 'Edit layout'}
              </Button>
              </Group>
            </Group>
            <section className="home-map-building">
              <div
                className={`home-map-room-grid ${layoutEditMode ? 'editing' : ''}`}
                onDragOver={layoutEditMode ? (event) => event.preventDefault() : undefined}
                onDrop={layoutEditMode ? handleDropOnBuilding : undefined}
              >
                {roomTree.map((section) => (
                  <HomeMapRoom
                    key={section.room}
                    section={section}
                    childSections={section.children}
                    draggedRoom={draggedRoom}
                    editMode={layoutEditMode}
                    dropTarget={dropTarget}
                    onDragStart={handleRoomDragStart}
                    onDragEnd={handleRoomDragEnd}
                    onDragOverRoom={handleDragOverRoom}
                    onDropOnRoom={handleDropOnRoom}
                    onDragLeaveRoom={handleDragLeaveRoom}
                    onMoveToRoot={moveRoomToRoot}
                    onSelectDevice={onSelectDevice}
                  />
                ))}
              </div>
            </section>
            {unassignedSection && (
              <section className="home-map-utility">
                <Group justify="space-between" align="center" mb="sm" wrap="nowrap">
                  <Group gap="xs" wrap="nowrap">
                    <IconNetwork size={20} />
                    <Text fw={900}>No room</Text>
                  </Group>
                </Group>
                <div className="home-map-device-cloud">
                  {(unassignedSection.visibleDevices || unassignedSection.devices).map((device) => (
                    <HomeMapDeviceButton
                      key={device.id}
                      device={device}
                      onSelectDevice={onSelectDevice}
                    />
                  ))}
                </div>
              </section>
            )}
          </div>
        ) : (
          <Text c="dimmed" ta="center" py="xl">
          No devices to show.
        </Text>
      )}
      </Paper>
      <Modal
        opened={resetModalOpened}
        onClose={resetModal.close}
        title="Reset layout?"
        centered
        size="sm"
      >
        <Text c="dimmed" mb="lg">
          This will reset the Home Map layout to the automatic arrangement.
        </Text>
        <Group justify="flex-end">
          <Button variant="default" onClick={resetModal.close}>
            Cancel
          </Button>
          <Button color="red" onClick={resetHomeMapLayout}>
            Reset layout
          </Button>
        </Group>
      </Modal>
    </>
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

function SortableHeader({ field, label, ordering, onChange, className }) {
  const active = ordering === field || ordering === `-${field}`;
  const direction = ordering === field ? 'asc' : ordering === `-${field}` ? 'desc' : '';
  const title = active
    ? `${label} sorted ${direction === 'asc' ? 'ascending' : 'descending'}`
    : `Sort by ${label}`;

  return (
    <Table.Th className={className}>
      <UnstyledButton
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
      </UnstyledButton>
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

function normalizeApiDate(value) {
  if (typeof value !== 'string') {
    return value;
  }
  const trimmedValue = value.trim();
  if (!trimmedValue) {
    return trimmedValue;
  }
  const normalizedValue = trimmedValue.replace(
    /^(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2}:\d{2})/,
    '$1T$2'
  );
  const hasTime = normalizedValue.includes('T');
  const hasTimezone = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(normalizedValue);
  return hasTime && !hasTimezone ? `${normalizedValue}Z` : normalizedValue;
}

function formatDate(value, timeZone) {
  if (!value) {
    return '-';
  }
  const date = new Date(normalizeApiDate(value));
  if (Number.isNaN(date.getTime())) {
    return '-';
  }
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
    ...(timeZone ? { timeZone } : {}),
  }).format(date);
}

function formatDuration(seconds) {
  const value = Number(seconds);
  if (!Number.isFinite(value) || value < 0) {
    return '-';
  }
  const minutes = Math.floor(value / 60);
  const remainingSeconds = Math.floor(value % 60);
  if (minutes >= 60) {
    const hours = Math.floor(minutes / 60);
    const remainingMinutes = minutes % 60;
    return `${hours}h ${remainingMinutes}m`;
  }
  if (minutes > 0) {
    return `${minutes}m ${remainingSeconds}s`;
  }
  return `${remainingSeconds}s`;
}

function deviceStatus(device) {
  const statusValue = device?.status || (device?.online ? 'online' : 'offline');
  const labels = {
    online: 'Online',
    recently_seen: 'Recently seen',
    sleeping: 'Sleeping',
    offline: 'Offline',
  };
  const colors = {
    online: 'teal',
    recently_seen: 'blue',
    sleeping: 'yellow',
    offline: 'gray',
  };
  const dot = statusValue.replace('_', '-');
  return {
    value: statusValue,
    label: device?.status_display || labels[statusValue] || (device?.online ? 'Online' : 'Offline'),
    color: colors[statusValue] || (device?.online ? 'teal' : 'gray'),
    dot,
    reason: device?.status_reason || '',
  };
}

function DeviceStatusInline({ device, muted = false }) {
  const status = deviceStatus(device);
  return (
    <Group gap="xs" wrap="nowrap">
      <span className={`status-dot ${status.dot}`} />
      <Text size="sm" c={muted ? 'dimmed' : undefined}>{status.label}</Text>
    </Group>
  );
}

function deviceRisk(device) {
  const level = device?.risk_level || 'low';
  const labels = {
    high: 'High',
    medium: 'Medium',
    low: 'Low',
  };
  const colors = {
    high: 'red',
    medium: 'orange',
    low: 'teal',
  };
  const reasons = device?.risk_reasons || [];
  return {
    level,
    label: labels[level] || 'Low',
    color: colors[level] || 'gray',
    reasons,
    tooltip: reasons.length ? reasons.join('\n') : 'No obvious risk',
  };
}

function RiskBadge({ device, compact = false }) {
  const risk = deviceRisk(device);

  return (
    <Tooltip label={risk.tooltip} multiline withArrow>
      <Badge
        className="device-risk-badge"
        color={risk.color}
        variant={risk.level === 'low' ? 'light' : 'filled'}
        size={compact ? 'sm' : 'md'}
      >
        {compact ? risk.label : `${risk.label} risk`}
      </Badge>
    </Tooltip>
  );
}

function GatewayBadge({ device, compact = false }) {
  if (!device?.is_gateway) return null;

  return (
    <Badge
      color="blue"
      variant="light"
      size={compact ? 'sm' : 'md'}
      leftSection={<IconRouter size={compact ? 12 : 14} stroke={2} />}
    >
      Gateway
    </Badge>
  );
}

function formatTopbarDate(value, timeZone) {
  return new Intl.DateTimeFormat(undefined, {
    weekday: 'short',
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    ...(timeZone ? { timeZone } : {}),
  }).format(value);
}

function formatTopbarTime(value, timeZone) {
  return new Intl.DateTimeFormat(undefined, {
    hour: '2-digit',
    minute: '2-digit',
    ...(timeZone ? { timeZone } : {}),
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
        `Welcome, ${userDisplayName(user)}.`
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

function ThemeIconLike({ children, color, size = 42 }) {
  return (
    <Box
      style={{
        width: size,
        height: size,
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

function DashboardStatusCards({ counters = {} }) {
  return (
    <div className="dashboard-status-grid">
      <DashboardStatusCard
        icon={<IconDeviceDesktop size={30} />}
        label="Devices"
        value={counters.all_devices ?? 0}
        color="blue"
      />
      <DashboardStatusCard
        icon={<IconWifi size={30} />}
        label="Online"
        value={counters.online_devices ?? 0}
        color="green"
      />
      <DashboardStatusCard
        icon={<IconQuestionMark size={30} />}
        label="Unknown"
        value={counters.new_devices ?? 0}
        color="orange"
      />
      <DashboardStatusCard
        icon={<IconNetwork size={30} />}
        label="Open Ports"
        value={counters.open_ports ?? 0}
        color="purple"
      />
    </div>
  );
}

function DashboardStatusCard({ icon, label, value, color }) {
  return (
    <Paper className="dashboard-status-card" radius="md">
      <span className={`dashboard-status-icon ${color}`}>
        {icon}
      </span>
      <Box>
        <Text className="dashboard-status-label" fw={800}>{label}</Text>
        <Text className="dashboard-status-value" fw={900}>{value}</Text>
      </Box>
    </Paper>
  );
}

function NetworkHealthCard({ counters = {} }) {
  const totalDevices = Number(counters.all_devices) || 0;
  const newDevices = Number(counters.new_devices) || 0;
  const knownCoverage = totalDevices > 0
    ? Math.round(((totalDevices - newDevices) / totalDevices) * 100)
    : 100;
  const healthColor = knownCoverage >= 95 ? 'teal' : 'orange';
  const healthLabel = knownCoverage >= 95 ? 'Good' : 'Review';

  return (
    <Paper className="dashboard-summary-card network-health-card" radius="md">
      <Group justify="space-between" align="center" mb="lg" wrap="nowrap">
        <Group gap="sm" wrap="nowrap">
          <IconLine size={28} />
          <Title order={3}>Network Health</Title>
        </Group>
        <Badge className="dashboard-status-badge" color={healthColor} variant="light">
          {healthLabel}
        </Badge>
      </Group>
      <div className="network-health-meter" aria-hidden="true">
        <div
          className={`network-health-meter-fill ${healthColor}`}
          style={{ width: `${Math.min(100, Math.max(0, knownCoverage))}%` }}
        />
      </div>
      <Stack gap={8} mt="lg">
        <SummaryRow label="Known coverage" value={`${knownCoverage}%`} />
        <SummaryRow label="Online devices" value={counters.online_devices ?? 0} />
        <SummaryRow label="Open ports" value={counters.open_ports ?? 0} />
      </Stack>
    </Paper>
  );
}

function AutomaticScanningCard({ appSettings, scanVisibility }) {
  return (
    <Paper className="dashboard-summary-card automatic-scanning-card" radius="md">
      <Group align="flex-start" gap="md" wrap="nowrap">
        <ThemeIconLike color="blue">
          <IconClock size={24} />
        </ThemeIconLike>
        <Box>
          <Title order={3}>Automatic Scanning</Title>
          <Text c="dimmed" fw={600}>Enabled</Text>
        </Box>
      </Group>
      <SimpleGrid cols={2} mt="xl">
        <SummaryMetric label="Interval" value={appSettings?.scan_interval ? `${appSettings.scan_interval} min` : '-'} />
        <SummaryMetric label="Range" value={scanVisibility?.current_range || appSettings?.ip_range || '-'} align="right" />
      </SimpleGrid>
    </Paper>
  );
}

function ScanDetailsContent({ scanStatus, scanVisibility, timeZone }) {
  const checks = [
    'Device discovery and online status checks',
    'Open port scanning for the configured TCP ports',
    'Hostname discovery using local network name protocols',
    'Metadata probing from device services when available',
    'Offline confirmation before a device is marked unavailable',
  ];

  return (
    <Stack gap="md">
      <SimpleGrid cols={{ base: 1, sm: 2 }}>
        <SummaryMetric label="Status" value={scanVisibility?.is_scanning ? 'Scanning' : scanStatus?.status || '-'} />
        <SummaryMetric label="Devices" value={scanStatus?.devices_seen ?? 0} />
        <SummaryMetric label="Duration" value={formatDuration(scanVisibility?.duration_seconds)} />
        <SummaryMetric label="Range" value={scanVisibility?.current_range || '-'} />
        <SummaryMetric label="Started" value={formatDate(scanVisibility?.started_at, timeZone)} nowrap />
        <SummaryMetric label="Finished" value={formatDate(scanVisibility?.finished_at, timeZone)} nowrap />
      </SimpleGrid>

      {scanVisibility?.last_error && (
        <Alert color="red" icon={<IconAlertCircle size={18} />}>
          {scanVisibility.last_error}
        </Alert>
      )}

      <Divider />

      <Stack gap={8}>
        <Text fw={700}>Deep scan checks</Text>
        {checks.map((check) => (
          <Group key={check} gap="sm" wrap="nowrap">
            <ThemeIconLike color="blue" size={28}>
              <IconShieldCheck size={16} />
            </ThemeIconLike>
            <Text c="dimmed">{check}</Text>
          </Group>
        ))}
      </Stack>

      <Text c="dimmed" size="sm">
        Longer scans are usually caused by devices that do not answer and force timeout-based checks.
      </Text>
    </Stack>
  );
}

function LatestScanCard({ scanStatus, scanVisibility, timeZone, onOpenDetails }) {
  const statusColor = scanVisibility?.is_scanning
    ? 'blue'
    : scanStatus?.status === 'failed'
      ? 'red'
      : 'teal';
  const statusLabel = scanVisibility?.is_scanning ? 'Scanning' : scanStatus?.status || '-';

  return (
    <Paper
      className="dashboard-summary-card latest-scan-card dashboard-clickable-card"
      radius="md"
      component="button"
      type="button"
      onClick={onOpenDetails}
    >
      <Group justify="space-between" align="center" mb="lg" wrap="nowrap">
        <Group gap="sm" wrap="nowrap">
          <IconClock size={28} />
          <Title order={3}>Latest Scan</Title>
        </Group>
        <Badge className="dashboard-status-badge" color={statusColor} variant="light">
          {statusLabel}
        </Badge>
      </Group>
      <SimpleGrid cols={2}>
        <SummaryMetric label="Devices" value={scanStatus?.devices_seen ?? 0} />
        <SummaryMetric label="Duration" value={formatDuration(scanVisibility?.duration_seconds)} />
        <SummaryMetric label="Started" value={formatDate(scanVisibility?.started_at, timeZone)} nowrap />
        <SummaryMetric label="Finished" value={formatDate(scanVisibility?.finished_at, timeZone)} nowrap />
      </SimpleGrid>
      {scanVisibility?.last_error && (
        <Alert mt="md" color="red" icon={<IconAlertCircle size={18} />}>
          {scanVisibility.last_error}
        </Alert>
      )}
    </Paper>
  );
}

function DashboardInsightCards({ events = [], devices = [], onSelectDevice, timeZone }) {
  const recentEvents = events;
  const deviceById = useMemo(
    () => new Map(devices.map((device) => [String(device.id), device])),
    [devices]
  );
  const attentionDevices = devices
    .filter((device) => device.needs_attention ?? (!device.known || ['high', 'medium'].includes(device.risk_level)))
    .sort((first, second) => {
      const riskWeight = { high: 0, medium: 1, low: 2 };
      const firstWeight = first.known ? riskWeight[first.risk_level] ?? 2 : -1;
      const secondWeight = second.known ? riskWeight[second.risk_level] ?? 2 : -1;
      return firstWeight - secondWeight || String(first.ip).localeCompare(String(second.ip), undefined, { numeric: true });
    });

  return (
    <div className="dashboard-insight-grid">
      <Paper className="dashboard-insight-card" radius="md">
        <DashboardInsightHeader
          icon={<IconHistory size={26} />}
          title="Recently Changed"
          count={events.length}
          color="blue"
        />
        <Stack className="dashboard-insight-list" gap="sm">
          {recentEvents.length ? recentEvents.map((event) => (
            <DashboardEventRow
              key={event.id}
              event={event}
              timeZone={timeZone}
              device={eventDeviceForRow(event, deviceById, devices)}
              onSelectDevice={onSelectDevice}
            />
          )) : (
            <DashboardEmptyState label="No recent changes" />
          )}
        </Stack>
      </Paper>

      <Paper className="dashboard-insight-card" radius="md">
        <DashboardInsightHeader
          icon={<IconShieldLock size={26} />}
          title="Needs Attention"
          count={attentionDevices.length}
          color="orange"
        />
        <Stack className="dashboard-insight-list" gap="sm">
          {attentionDevices.map((device) => (
            <DashboardAttentionRow
              key={device.id}
              device={device}
              onSelectDevice={onSelectDevice}
            />
          ))}
          {!attentionDevices.length && <DashboardEmptyState label="No devices need attention" />}
        </Stack>
      </Paper>
    </div>
  );
}

function eventDeviceId(event) {
  const eventDevice = event?.device;
  if (eventDevice && typeof eventDevice === 'object') {
    return eventDevice.id;
  }
  return eventDevice;
}

function eventDeviceForRow(event, deviceById, devices) {
  const id = eventDeviceId(event);
  if (id !== null && id !== undefined && deviceById.has(String(id))) {
    return deviceById.get(String(id));
  }

  const metadata = event?.metadata || {};
  const eventMac = normalizeMacText(metadata.mac);
  const eventIp = String(metadata.ip || '').trim();
  return devices.find((device) => {
    if (eventMac && normalizeMacText(device.mac) === eventMac) {
      return true;
    }
    return eventIp && String(device.ip || '').trim() === eventIp;
  }) || null;
}

function DashboardInsightHeader({ icon, title, count, color }) {
  return (
    <Group justify="space-between" align="center" mb="md" wrap="nowrap">
      <Group gap="sm" wrap="nowrap">
        {icon}
        <Title order={3}>{title}</Title>
      </Group>
      <Badge className="dashboard-insight-count" color={color} variant="light">
        {count}
      </Badge>
    </Group>
  );
}

function DashboardEventRow({ event, timeZone, device, onSelectDevice }) {
  async function handleSelectEventDevice() {
    if (device) {
      onSelectDevice(device);
      return;
    }

    const id = eventDeviceId(event);
    if (id === null || id === undefined) {
      return;
    }

    try {
      const payload = await apiRequest(`device/?id=${id}`);
      if (payload.data) {
        onSelectDevice(payload.data);
      }
    } catch (err) {
      showErrorNotification('Could not open device', err.message);
    }
  }

  const content = (
    <>
      <span className="dashboard-insight-row-icon blue">
        <IconHistory size={20} />
      </span>
      <Box className="dashboard-insight-row-body">
        <Text fw={800} className="truncate-cell">
          {event.message || event.event_type_display || event.event_type}
        </Text>
        <Text size="sm" c="dimmed" className="truncate-cell">
          {[event.event_type_display || event.event_type, formatDate(event.created_at, timeZone)]
            .filter(Boolean)
            .join(' - ')}
        </Text>
      </Box>
    </>
  );

  if (device || eventDeviceId(event) !== null && eventDeviceId(event) !== undefined) {
    return (
      <UnstyledButton
        className="dashboard-insight-row dashboard-insight-button"
        aria-label={`Open ${event.message || 'changed device'}`}
        onClick={handleSelectEventDevice}
      >
        {content}
      </UnstyledButton>
    );
  }

  return (
    <div className="dashboard-insight-row">
      {content}
    </div>
  );
}

function DashboardAttentionRow({ device, onSelectDevice }) {
  const risk = deviceRisk(device);
  const reason = !device.known ? 'Unknown device' : risk.label;

  return (
    <UnstyledButton
      className="dashboard-insight-row dashboard-insight-button"
      onClick={() => onSelectDevice(device)}
    >
      <span className="dashboard-insight-row-icon orange">
        <DeviceIconStack device={device} size={18} />
      </span>
      <Box className="dashboard-insight-row-body">
        <Text fw={800} className="truncate-cell">{displayDeviceName(device)}</Text>
        <Text size="sm" c="dimmed" className="truncate-cell">
          {[reason, device.ip].filter(Boolean).join(' - ')}
        </Text>
      </Box>
      <Badge className="dashboard-insight-risk" color={risk.color} variant="light">
        {risk.label}
      </Badge>
    </UnstyledButton>
  );
}

function DashboardEmptyState({ label }) {
  return (
    <Text c="dimmed" fw={700} py="sm">
      {label}
    </Text>
  );
}

function SummaryRow({ label, value }) {
  return (
    <Group justify="space-between" wrap="nowrap">
      <Text c="dimmed" fw={600}>{label}</Text>
      <Text fw={800}>{value}</Text>
    </Group>
  );
}

function SummaryMetric({ label, value, align = 'left', nowrap = false }) {
  return (
    <Box ta={align}>
      <Text size="sm" c="dimmed" fw={600}>{label}</Text>
      <Text
        className={`dashboard-summary-value${nowrap ? ' dashboard-summary-value-nowrap' : ''}`}
        fw={800}
      >
        {value}
      </Text>
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
    <Box className="device-field identity-confidence-field">
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

function buildRoomOptions(devices = [], currentRoom = '') {
  return Array.from(
    new Set(
      [...devices.map((device) => device.room), currentRoom]
        .map((value) => String(value || '').trim())
        .filter(Boolean)
    )
  )
    .sort((left, right) => left.localeCompare(right))
    .map((value) => ({ value, label: value }));
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

function DeviceDetailsPage({ deviceId, onBack, onSaved, onDeleted, timeZone, roomOptions }) {
  const [device, setDevice] = useState(null);
  const [events, setEvents] = useState([]);
  const [eventPagination, setEventPagination] = useState(null);
  const [icon, setIcon] = useState('');
  const [secondaryIcon, setSecondaryIcon] = useState('');
  const [name, setName] = useState('');
  const [role, setRole] = useState('device');
  const [room, setRoom] = useState('');
  const [known, setKnown] = useState(false);
  const [comments, setComments] = useState('');
  const [externalUrl, setExternalUrl] = useState('');
  const [detectedWebUrl, setDetectedWebUrl] = useState('');
  const [detectingWebUrl, setDetectingWebUrl] = useState(false);
  const [attentionAcknowledged, setAttentionAcknowledged] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loadingMoreEvents, setLoadingMoreEvents] = useState(false);
  const [saving, setSaving] = useState(false);
  const [editing, setEditing] = useState(false);
  const [error, setError] = useState('');
  const [deleteConfirmOpened, deleteConfirm] = useDisclosure(false);

  function populateForm(nextDevice) {
    setIcon(nextDevice?.icon || '');
    setSecondaryIcon(nextDevice?.secondary_icon || '');
    setName(nextDevice?.name || '');
    setRole(nextDevice?.role || 'device');
    setRoom(nextDevice?.room || '');
    setKnown(Boolean(nextDevice?.known));
    setComments(nextDevice?.comments || '');
    setExternalUrl(nextDevice?.external_url || '');
    setAttentionAcknowledged(Boolean(nextDevice?.attention_acknowledged));
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
      showErrorNotification('Could not save device', message);
      setSaving(false);
      return;
    }
    try {
      await apiRequest(`device/?id=${device.id}`, {
        method: 'PUT',
        body: {
          icon,
          secondary_icon: secondaryIcon || '',
          name,
          role,
          room,
          known,
          comments,
          external_url: externalUrl.trim(),
          acknowledge_attention: known && attentionAcknowledged,
        },
      });
      const updatedDevice = await loadDevice({ quiet: true });
      await onSaved(updatedDevice);
      showSuccessNotification('Device saved', `${name || device.name} was updated.`);
      setEditing(false);
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
      showSuccessNotification('Device deleted', `${deletedName} was removed.`);
      deleteConfirm.close();
      await onDeleted();
    } catch (err) {
      setError(err.message);
      showErrorNotification('Could not delete device', err.message);
    } finally {
      setSaving(false);
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
      showErrorNotification('Could not load device history', err.message);
    } finally {
      setLoadingMoreEvents(false);
    }
  }

  const currentStatus = device ? deviceStatus(device) : null;
  const activeUrl = externalUrl.trim() || detectedWebUrl;

  return (
    <Paper className="device-detail-page" radius="md">
      <LoadingOverlay visible={loading} />
      <Stack gap="lg">
        <Group justify="space-between" align="flex-start" wrap="wrap">
          <Group gap="sm" align="flex-start" wrap="nowrap">
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
            <Box>
              <Group gap="xs" wrap="wrap">
                <Title order={2}>{device ? displayDeviceName(device) : 'Device'}</Title>
                {device && <GatewayBadge device={device} compact />}
                {device && <RiskBadge device={device} compact />}
              </Group>
              {device && <Text c="dimmed">{deviceSubtitle(device)}</Text>}
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
          {device && (
            editing ? (
              <Group gap="xs">
                <Button variant="default" onClick={cancelEditing} disabled={saving}>Cancel</Button>
                <Button leftSection={<IconDeviceFloppy size={18} />} onClick={save} loading={saving}>
                  Save
                </Button>
              </Group>
            ) : (
              <Button leftSection={<IconEdit size={18} />} onClick={() => setEditing(true)}>
                Edit device
              </Button>
            )
          )}
        </Group>

        {error && (
          <Alert color="red" icon={<IconAlertCircle size={18} />}>
            {error}
          </Alert>
        )}
        {device && (
          <Tabs defaultValue="overview" keepMounted={false}>
            <Tabs.List>
              <Tabs.Tab value="overview" leftSection={<IconNetwork size={17} />}>Overview</Tabs.Tab>
              <Tabs.Tab value="history" leftSection={<IconHistory size={17} />}>History</Tabs.Tab>
            </Tabs.List>

            <Tabs.Panel value="overview" pt="lg">
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
                    <TextInput
                      label="External link"
                      placeholder="https://192.168.0.20"
                      value={externalUrl}
                      error={!validExternalUrl(externalUrl) ? 'Enter a valid HTTP or HTTPS URL.' : null}
                      onChange={(event) => setExternalUrl(event.currentTarget.value)}
                    />
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
                  <Group align="flex-start">
                    <Switch
                      label="Known device"
                      checked={known}
                      onChange={(event) => {
                        const nextKnown = event.currentTarget.checked;
                        setKnown(nextKnown);
                        if (!nextKnown) {
                          setAttentionAcknowledged(false);
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
                  <Group>
                    <Button
                      color="red"
                      variant="light"
                      leftSection={<IconTrash size={18} />}
                      onClick={deleteConfirm.open}
                    >
                      Delete device
                    </Button>
                  </Group>
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
                            <Badge key={`${port.protocol}-${port.port}`} variant="light">
                              {port.protocol}/{port.port}{port.service ? ` ${port.service}` : ''}
                            </Badge>
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
    </Paper>
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
                    <UnstyledButton
                      key={item.id}
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
                    </UnstyledButton>
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

function SettingsPage({ onSaved }) {
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
  const [notifyNewDevices, setNotifyNewDevices] = useState(true);
  const [notifyDeviceOnline, setNotifyDeviceOnline] = useState(false);
  const [notifyDeviceOffline, setNotifyDeviceOffline] = useState(false);
  const [notifyPortChanges, setNotifyPortChanges] = useState(false);
  const [quietHoursEnabled, setQuietHoursEnabled] = useState(false);
  const [quietHoursStart, setQuietHoursStart] = useState('22:00');
  const [quietHoursEnd, setQuietHoursEnd] = useState('07:00');
  const [quietHoursDays, setQuietHoursDays] = useState(allQuietHoursDays);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [testingChannel, setTestingChannel] = useState('');
  const [exporting, setExporting] = useState(false);
  const [importing, setImporting] = useState(false);
  const [importingWatchYourLan, setImportingWatchYourLan] = useState(false);
  const [cleanupDays, setCleanupDays] = useState(90);
  const [cleanupTarget, setCleanupTarget] = useState(null);
  const [cleaningActivity, setCleaningActivity] = useState('');
  const [error, setError] = useState('');
  const [cleanupConfirmOpened, cleanupConfirm] = useDisclosure(false);

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
      setNotifyNewDevices(Boolean(data.notify_new_devices));
      setNotifyDeviceOnline(Boolean(data.notify_device_online));
      setNotifyDeviceOffline(Boolean(data.notify_device_offline));
      setNotifyPortChanges(Boolean(data.notify_port_changes));
      setQuietHoursEnabled(Boolean(data.notification_quiet_hours_enabled));
      setQuietHoursStart(data.notification_quiet_hours_start || '22:00');
      setQuietHoursEnd(data.notification_quiet_hours_end || '07:00');
      setQuietHoursDays(
        Array.isArray(data.notification_quiet_hours_days)
          ? data.notification_quiet_hours_days
          : allQuietHoursDays
      );
      setCleanupDays(Number(data.activity_cleanup_retention_days ?? 90));
    } catch (err) {
      setError(err.message);
      showErrorNotification('Could not load settings', err.message);
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
      const body = {
        ip_range: ipRange,
        scan_interval: scanInterval,
        time_zone: timeZone,
        discord_enabled: discordEnabled,
        telegram_enabled: telegramEnabled,
        notify_new_devices: notifyNewDevices,
        notify_device_online: notifyDeviceOnline,
        notify_device_offline: notifyDeviceOffline,
        notify_port_changes: notifyPortChanges,
        notification_quiet_hours_enabled: quietHoursEnabled,
        notification_quiet_hours_start: quietHoursStart,
        notification_quiet_hours_end: quietHoursEnd,
        notification_quiet_hours_days: quietHoursDays,
        activity_cleanup_retention_days: cleanupDays,
      };
      body.discord_webhook = discordWebhook;
      body.telegram_token = telegramToken;
      body.telegram_user_id = telegramUserId;

      const savedSettings = await apiRequest('settings/', { method: 'PUT', body });
      await loadSettings();
      await onSaved(savedSettings.data || {});
      showSuccessNotification('Settings saved', 'Scanner and notification settings were updated.');
    } catch (err) {
      setError(err.message);
      showErrorNotification('Could not save settings', err.message);
    } finally {
      setSaving(false);
    }
  }

  async function testNotificationChannel(channel) {
    setTestingChannel(channel);
    setError('');
    try {
      const body =
        channel === 'discord'
          ? { channel, discord_webhook: discordWebhook.trim() }
          : {
              channel,
              telegram_token: telegramToken.trim(),
              telegram_user_id: telegramUserId.trim(),
            };
      const payload = await apiRequest('notifications/test/', { method: 'POST', body });
      showSuccessNotification(
        'Test notification sent',
        payload?.data?.message || `Check your ${channel} channel.`
      );
    } catch (err) {
      setError(err.message);
      showErrorNotification('Test notification failed', err.message);
    } finally {
      setTestingChannel('');
    }
  }

  async function exportInventory() {
    setExporting(true);
    setError('');
    try {
      const payload = await apiRequest('devices/export/');
      const json = JSON.stringify(payload, null, 2);
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
      showSuccessNotification('Inventory exported', 'Device names, icons, vendors, IPs, and ports were exported.');
    } catch (err) {
      setError(err.message);
      showErrorNotification('Could not export inventory', err.message);
    } finally {
      setExporting(false);
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
      const summary = result.data || {};
      showSuccessNotification(
        'Inventory imported',
        `Created ${summary.created || 0}, updated ${summary.updated || 0}, skipped ${summary.skipped || 0}.`
      );
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
      const summary = result.data || {};
      showSuccessNotification(
        'WatchYourLAN migration complete',
        `Created ${summary.created || 0}, updated ${summary.updated || 0}, skipped ${summary.skipped || 0}.`
      );
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

  const cleanupTargetLabels = {
    events: 'Events',
    scan_runs: 'Scan history',
    notifications: 'Notifications',
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
      const deleted = result.data?.deleted || {};
      const targetLabel = cleanupTargetLabels[cleanupTarget] || 'Activity';
      showSuccessNotification(
        `${targetLabel} cleaned`,
        `Deleted ${deleted.events || 0} events, ${deleted.scan_runs || 0} scan runs, and ${deleted.notifications || 0} notifications.`
      );
      return true;
    } catch (err) {
      setError(err.message);
      showErrorNotification('Could not clean activity', err.message);
      return false;
    } finally {
      setCleaningActivity('');
    }
  }

  function openCleanupConfirm(target) {
    setCleanupTarget(target);
    cleanupConfirm.open();
  }

  return (
    <Paper className="content-panel settings-page" radius="md" p="lg">
      <LoadingOverlay visible={loading} />
      <Stack>
        <Group justify="space-between" align="flex-start">
          <Group gap="sm">
            <span className="page-icon">
              <IconSettings size={26} />
            </span>
            <Box>
              <Title order={2}>Settings</Title>
              <Text c="dimmed">Scanner, notifications, and inventory tools</Text>
            </Box>
          </Group>
          <Button onClick={saveSettings} loading={saving}>
            Save
          </Button>
        </Group>

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
          The interval starts after each scan completes. Restart the scanner container after changing scan interval or timezone.
        </Text>

        <Stack gap="sm">
          <Text fw={700}>Notification rules</Text>
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
          </SimpleGrid>
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
          <Group align="flex-end" wrap="nowrap">
            <TextInput
              style={{ flex: 1 }}
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
            <Tooltip label="Send test notification">
              <ActionIcon
                size={36}
                variant="light"
                aria-label="Send Discord test notification"
                loading={testingChannel === 'discord'}
                disabled={
                  !discordWebhook.trim() ||
                  Boolean(testingChannel && testingChannel !== 'discord')
                }
                onClick={() => testNotificationChannel('discord')}
              >
                <IconSend size={18} />
              </ActionIcon>
            </Tooltip>
          </Group>
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
          <Group align="flex-end" wrap="nowrap">
            <TextInput
              style={{ flex: 1 }}
              label="Telegram bot token"
              placeholder="123456:bot-token"
              value={telegramToken}
              onChange={(event) => setTelegramToken(event.currentTarget.value)}
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
                  !telegramToken.trim() ||
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

        <Divider />

        <Group justify="space-between" align="flex-start">
          <Box>
            <Text fw={700}>Activity cleanup</Text>
            <Text size="sm" c="dimmed">
              Scheduled cleanup runs every 24 hours using this retention period. Use clean all only for manual resets.
            </Text>
          </Box>
          <Group gap="sm" align="flex-end">
            <NumberInput
              w={150}
              label="Older than"
              value={cleanupDays}
              onChange={(value) => setCleanupDays(value === '' || value === null ? 90 : Number(value))}
              min={1}
              max={3650}
              suffix=" days"
            />
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
          </Group>
        </Group>

        <Divider />

        <Group justify="space-between" align="flex-start">
          <Box>
            <Text fw={700}>Device inventory</Text>
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

        <Group justify="space-between" align="flex-start">
          <Box>
            <Text fw={700}>WatchYourLAN migration</Text>
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

        <Divider />
        <Group justify="flex-end" className="settings-page-actions">
          <Button onClick={saveSettings} loading={saving}>
            Save
          </Button>
        </Group>
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

function ActivityTablePanel({ children, hasMore = false, loadingMore = false, onLoadMore }) {
  const viewportRef = useRef(null);
  const loadRequestedRef = useRef(false);

  useEffect(() => {
    if (!loadingMore) {
      loadRequestedRef.current = false;
    }
  }, [loadingMore]);

  function handleScrollPositionChange() {
    const viewport = viewportRef.current;
    if (!viewport || !hasMore || loadingMore || loadRequestedRef.current || !onLoadMore) {
      return;
    }

    const remaining = viewport.scrollHeight - viewport.scrollTop - viewport.clientHeight;
    if (remaining < 140) {
      loadRequestedRef.current = true;
      onLoadMore();
    }
  }

  return (
    <Paper className="content-panel activity-table-panel" radius="md">
      <ScrollArea
        viewportRef={viewportRef}
        h="min(640px, calc(100vh - 250px))"
        offsetScrollbars
        scrollbarSize={10}
        type="always"
        onScrollPositionChange={handleScrollPositionChange}
      >
        <Box className="activity-table-scroll">
          {children}
          {hasMore && (
            <Group justify="center" p="md">
              <Loader size="sm" />
            </Group>
          )}
        </Box>
      </ScrollArea>
    </Paper>
  );
}

function EventsPage({
  events,
  eventType,
  setEventType,
  timeZone,
  pagination,
  loadingMore,
  onLoadMore,
  onSelectDevice,
}) {
  async function handleSelectEventDevice(event) {
    const id = eventDeviceId(event);
    if (id === null || id === undefined) {
      return;
    }

    try {
      const payload = await apiRequest(`device/?id=${id}`);
      if (payload.data) {
        onSelectDevice(payload.data);
      }
    } catch (err) {
      showErrorNotification('Could not open device', err.message);
    }
  }

  return (
    <Stack gap="lg">
      <Group justify="space-between" align="flex-end">
        <Group gap="sm">
          <span className="page-icon">
            <IconBell size={26} />
          </span>
          <Box>
            <Title order={2}>Events</Title>
            <Text c="dimmed">Network changes and alert decisions</Text>
          </Box>
        </Group>
        <Group gap="sm">
          <Badge variant="light">{activityRecordLabel(pagination, events.length)}</Badge>
          <Select
            w={220}
            placeholder="Event type"
            clearable
            data={eventTypeOptions}
            value={eventType}
            onChange={(value) => setEventType(value || '')}
          />
        </Group>
      </Group>

      <ActivityTablePanel
        hasMore={hasNextActivityPage(pagination)}
        loadingMore={loadingMore}
        onLoadMore={onLoadMore}
      >
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
            {events.map((event) => {
              const hasDevice = eventDeviceId(event) !== null && eventDeviceId(event) !== undefined;
              return (
                <Table.Tr
                  key={event.id}
                  className={hasDevice ? 'activity-clickable-row' : undefined}
                  tabIndex={hasDevice ? 0 : undefined}
                  role={hasDevice ? 'button' : undefined}
                  aria-label={hasDevice ? `Open device for ${event.message || 'event'}` : undefined}
                  onClick={hasDevice ? () => handleSelectEventDevice(event) : undefined}
                  onKeyDown={hasDevice ? (keyboardEvent) => {
                    if (keyboardEvent.key === 'Enter' || keyboardEvent.key === ' ') {
                      keyboardEvent.preventDefault();
                      handleSelectEventDevice(event);
                    }
                  } : undefined}
                >
                  <Table.Td>
                    <Badge variant="light">
                      {event.event_type_display || event.event_type}
                    </Badge>
                  </Table.Td>
                  <Table.Td>{event.message}</Table.Td>
                  <Table.Td>{formatDate(event.created_at, timeZone)}</Table.Td>
                  <Table.Td>
                    <Badge color={event.notified ? 'teal' : 'gray'} variant="light">
                      {event.notified ? 'Handled' : 'Pending'}
                    </Badge>
                  </Table.Td>
                </Table.Tr>
              );
            })}
          </Table.Tbody>
        </Table>
      </ActivityTablePanel>
    </Stack>
  );
}

function scanRunDurationSeconds(run) {
  if (!run?.started_at || !run?.finished_at) return 0;
  return Math.max(0, Math.round((new Date(run.finished_at) - new Date(run.started_at)) / 1000));
}

function ScanComparisonModal({ opened, onClose, scanRuns, timeZone }) {
  const comparableRuns = useMemo(
    () => scanRuns.filter((run) => run.status !== 'running' && run.finished_at),
    [scanRuns]
  );
  const [currentId, setCurrentId] = useState(null);
  const [baselineId, setBaselineId] = useState(null);

  useEffect(() => {
    const availableIds = new Set(comparableRuns.map((run) => String(run.id)));
    if (!currentId || !availableIds.has(currentId)) {
      setCurrentId(comparableRuns[0] ? String(comparableRuns[0].id) : null);
    }
    if (!baselineId || !availableIds.has(baselineId) || baselineId === currentId) {
      setBaselineId(comparableRuns[1] ? String(comparableRuns[1].id) : null);
    }
  }, [baselineId, comparableRuns, currentId]);

  const currentRun = comparableRuns.find((run) => String(run.id) === currentId);
  const baselineRun = comparableRuns.find((run) => String(run.id) === baselineId);
  const options = comparableRuns.map((run) => ({
    value: String(run.id),
    label: `${formatDate(run.started_at, timeZone)} · ${run.ip_range}`,
  }));
  const metrics = [
    { label: 'Devices seen', current: currentRun?.devices_seen, baseline: baselineRun?.devices_seen },
    { label: 'Online devices', current: currentRun?.online_devices, baseline: baselineRun?.online_devices },
    { label: 'New devices', current: currentRun?.new_devices, baseline: baselineRun?.new_devices },
    { label: 'Ports opened', current: currentRun?.ports_opened, baseline: baselineRun?.ports_opened },
    { label: 'Ports closed', current: currentRun?.ports_closed, baseline: baselineRun?.ports_closed },
    {
      label: 'Duration',
      current: scanRunDurationSeconds(currentRun),
      baseline: scanRunDurationSeconds(baselineRun),
      duration: true,
    },
  ];

  return (
    <Modal opened={opened} onClose={onClose} title="Compare scans" centered size="lg">
      <Stack gap="lg">
        <SimpleGrid cols={{ base: 1, sm: 2 }}>
          <Select
            label="Current scan"
            data={options}
            value={currentId}
            onChange={setCurrentId}
            allowDeselect={false}
            searchable
          />
          <Select
            label="Baseline scan"
            data={options}
            value={baselineId}
            onChange={setBaselineId}
            allowDeselect={false}
            searchable
          />
        </SimpleGrid>

        {currentRun && baselineRun && currentRun.id !== baselineRun.id ? (
          <>
            <Group justify="space-between" gap="md">
              <Group gap="xs">
                <Text c="dimmed" size="sm">Current</Text>
                <Badge color={currentRun.status === 'success' ? 'teal' : 'red'} variant="light">
                  {currentRun.status}
                </Badge>
              </Group>
              <Group gap="xs">
                <Text c="dimmed" size="sm">Baseline</Text>
                <Badge color={baselineRun.status === 'success' ? 'teal' : 'red'} variant="light">
                  {baselineRun.status}
                </Badge>
              </Group>
            </Group>
            <Table.ScrollContainer minWidth={520}>
              <Table verticalSpacing="sm">
                <Table.Thead>
                  <Table.Tr>
                    <Table.Th>Metric</Table.Th>
                    <Table.Th>Baseline</Table.Th>
                    <Table.Th>Current</Table.Th>
                    <Table.Th>Change</Table.Th>
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {metrics.map((metric) => {
                    const current = Number(metric.current) || 0;
                    const baseline = Number(metric.baseline) || 0;
                    const delta = current - baseline;
                    const displayValue = (value) => metric.duration ? formatDuration(value) : value;
                    const deltaLabel = metric.duration
                      ? `${delta > 0 ? '+' : delta < 0 ? '-' : ''}${formatDuration(Math.abs(delta))}`
                      : `${delta > 0 ? '+' : ''}${delta}`;
                    return (
                      <Table.Tr key={metric.label}>
                        <Table.Td><Text fw={700}>{metric.label}</Text></Table.Td>
                        <Table.Td>{displayValue(baseline)}</Table.Td>
                        <Table.Td>{displayValue(current)}</Table.Td>
                        <Table.Td>
                          <Badge color={delta === 0 ? 'gray' : 'blue'} variant="light">
                            {deltaLabel}
                          </Badge>
                        </Table.Td>
                      </Table.Tr>
                    );
                  })}
                </Table.Tbody>
              </Table>
            </Table.ScrollContainer>
            <Text c="dimmed" size="sm">
              Comparison uses the totals recorded for each scan. Historical per-device snapshots were not stored.
            </Text>
          </>
        ) : (
          <Alert color="blue" icon={<IconAlertCircle size={18} />}>
            Select two different completed scans to compare them.
          </Alert>
        )}
      </Stack>
    </Modal>
  );
}

function ScanHistoryPage({ scanRuns, timeZone, pagination, loadingMore, onLoadMore }) {
  const [comparisonOpened, comparison] = useDisclosure(false);
  const comparableRunCount = scanRuns.filter(
    (run) => run.status !== 'running' && run.finished_at
  ).length;

  return (
    <>
      <Stack gap="lg">
        <Group justify="space-between" align="flex-end">
          <Group gap="sm">
            <span className="page-icon">
              <IconHistory size={26} />
            </span>
            <Box>
              <Title order={2}>Scan history</Title>
              <Text c="dimmed">Recent scan runs and detected changes</Text>
            </Box>
          </Group>
          <Group gap="sm">
            <Button
              variant="light"
              leftSection={<IconArrowsSort size={18} />}
              onClick={comparison.open}
              disabled={comparableRunCount < 2}
            >
              Compare scans
            </Button>
            <Badge variant="light">{activityRecordLabel(pagination, scanRuns.length)}</Badge>
          </Group>
        </Group>

        <ActivityTablePanel
          hasMore={hasNextActivityPage(pagination)}
          loadingMore={loadingMore}
          onLoadMore={onLoadMore}
        >
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
                  <Table.Td>{formatDate(run.started_at, timeZone)}</Table.Td>
                  <Table.Td>{run.devices_seen}</Table.Td>
                  <Table.Td>{run.ports_opened} / {run.ports_closed}</Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </ActivityTablePanel>
      </Stack>
      <ScanComparisonModal
        opened={comparisonOpened}
        onClose={comparison.close}
        scanRuns={scanRuns}
        timeZone={timeZone}
      />
    </>
  );
}

function NotificationsPage({
  notifications: deliveries,
  timeZone,
  pagination,
  loadingMore,
  onLoadMore,
}) {
  return (
    <Stack gap="lg">
      <Group justify="space-between" align="flex-end">
        <Group gap="sm">
          <span className="page-icon">
            <IconBell size={26} />
          </span>
          <Box>
            <Title order={2}>Notifications</Title>
            <Text c="dimmed">Delivery status for external notification channels</Text>
          </Box>
        </Group>
        <Badge variant="light">{activityRecordLabel(pagination, deliveries.length)}</Badge>
      </Group>

      <ActivityTablePanel
        hasMore={hasNextActivityPage(pagination)}
        loadingMore={loadingMore}
        onLoadMore={onLoadMore}
      >
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
            {deliveries.map((delivery) => (
              <Table.Tr key={delivery.id}>
                <Table.Td>{delivery.channel_display || delivery.channel}</Table.Td>
                <Table.Td>
                  <Badge color={delivery.status === 'sent' ? 'teal' : delivery.status === 'failed' ? 'red' : 'gray'} variant="light">
                    {delivery.status_display || delivery.status}
                  </Badge>
                </Table.Td>
                <Table.Td>{delivery.attempts}</Table.Td>
                <Table.Td>{formatDate(delivery.created_at, timeZone)}</Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      </ActivityTablePanel>
    </Stack>
  );
}

const activityPageLimit = 500;
const dashboardStateStorageKey = 'languard_dashboard_navigation_state';

function activityRecordLabel(pagination, loadedCount) {
  const total = pagination?.count ?? loadedCount;
  if (total > loadedCount) {
    return `Latest ${loadedCount} of ${total} records`;
  }
  return `${loadedCount} records`;
}

function hasNextActivityPage(pagination) {
  return pagination?.next_offset !== null && pagination?.next_offset !== undefined;
}

function appendUniqueById(current, incoming) {
  const seen = new Set(current.map((item) => item.id));
  return [
    ...current,
    ...incoming.filter((item) => {
      if (seen.has(item.id)) {
        return false;
      }
      seen.add(item.id);
      return true;
    }),
  ];
}

function Dashboard({ user, onLogout, onUserUpdated, initialDeviceId = null }) {
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState('');
  const [currentTime, setCurrentTime] = useState(() => new Date());
  const [devices, setDevices] = useState([]);
  const [mapDevices, setMapDevices] = useState([]);
  const [devicePagination, setDevicePagination] = useState({
    count: 0,
    limit: 100,
    offset: 0,
    next_offset: null,
    previous_offset: null,
  });
  const [counters, setCounters] = useState({});
  const [scanStatus, setScanStatus] = useState(null);
  const [scanVisibility, setScanVisibility] = useState(null);
  const [scanRuns, setScanRuns] = useState([]);
  const [scanRunPagination, setScanRunPagination] = useState(null);
  const [dashboardEvents, setDashboardEvents] = useState([]);
  const [events, setEvents] = useState([]);
  const [eventPagination, setEventPagination] = useState(null);
  const [notifications, setNotifications] = useState([]);
  const [notificationPagination, setNotificationPagination] = useState(null);
  const [activityLoadingMore, setActivityLoadingMore] = useState({
    events: false,
    scanRuns: false,
    notifications: false,
  });
  const [appSettings, setAppSettings] = useState(null);
  const [dashboardTimeZone, setDashboardTimeZone] = useState();
  const [search, setSearch] = useState('');
  const [deviceStatus, setDeviceStatus] = useState('');
  const [firstSeenPeriod, setFirstSeenPeriod] = useState('');
  const [inventoryView, setInventoryView] = useState('table');
  const [mainView, setMainView] = useState('dashboard');
  const [deviceOrdering, setDeviceOrdering] = useState('');
  const [eventType, setEventType] = useState('');
  const [devicePageId, setDevicePageId] = useState(
    initialDeviceId ? String(initialDeviceId) : ''
  );
  const [changelogOpened, setChangelogOpened] = useState(false);
  const [seenChangelogVersion, setSeenChangelogVersion] = useState(APP_VERSION);
  const [latestVersion, setLatestVersion] = useState(APP_VERSION);
  const [versionCheckInterval, setVersionCheckInterval] = useState(
    versionCheckFallbackInterval
  );
  const [logoutModalOpened, logoutModal] = useDisclosure(false);
  const [usersModalOpened, usersModal] = useDisclosure(false);
  const [scanDetailsOpened, scanDetailsModal] = useDisclosure(false);
  const deviceListRef = useRef(null);
  const pendingDashboardScrollRef = useRef(null);
  const pendingDeviceListScrollRef = useRef(null);
  const tableStateRef = useRef({
    search: '',
    deviceStatus: '',
    firstSeenPeriod: '',
    deviceLimit: 100,
    deviceOffset: 0,
    deviceOrdering: '',
  });

  const filteredDevices = useMemo(() => devices, [devices]);
  const roomOptions = useMemo(() => buildRoomOptions(mapDevices), [mapDevices]);
  const deviceLimit = 100;
  const deviceOffset = 0;
  const deviceEnd = Math.min(devices.length, devicePagination.count || devices.length);
  const selectedDeviceStatus =
    deviceStatusOptions.find((option) => option.value === deviceStatus) || null;
  const canManageUsers = Boolean(user?.is_staff || user?.is_superuser);
  const hasUnreadChangelog = seenChangelogVersion !== APP_VERSION;
  const hasVersionUpdate = isNewerVersion(latestVersion, APP_VERSION);
  const hasVersionIndicator = hasUnreadChangelog || hasVersionUpdate;
  const versionTooltip = hasVersionUpdate
    ? `New version v${latestVersion} is available`
    : 'Version history';
  const displayTimeZone = appSettings?.time_zone || dashboardTimeZone || undefined;
  const showFirstSeen = deviceOrdering === 'firstseen' || deviceOrdering === '-firstseen';
  function storeDashboardNavigationState(overrides = {}) {
    window.sessionStorage.setItem(
      dashboardStateStorageKey,
      JSON.stringify({
        search,
        deviceStatus,
        firstSeenPeriod,
        inventoryView,
        mainView,
        deviceOrdering,
        eventType,
        scrollY: window.scrollY,
        deviceListScrollTop: deviceListRef.current?.scrollTop || 0,
        ...overrides,
      })
    );
  }

  function openDevicePage(device) {
    if (!device?.id) {
      return;
    }
    storeDashboardNavigationState();
    window.history.pushState({ languardDevicePage: true }, '', `/devices/${device.id}`);
    setDevicePageId(String(device.id));
    window.setTimeout(() => window.scrollTo({ top: 0 }), 0);
  }

  function navigateToView(view) {
    if (devicePageId) {
      storeDashboardNavigationState({ mainView: view, scrollY: 0 });
      window.history.pushState({}, '', '/');
      setDevicePageId('');
      setMainView(view);
      return;
    }
    setMainView(view);
  }

  function returnFromDevicePage() {
    if (window.history.state?.languardDevicePage) {
      window.history.back();
    } else {
      window.history.replaceState({}, '', '/');
      setDevicePageId('');
    }
  }

  useEffect(() => {
    const previousScrollRestoration = window.history.scrollRestoration;
    window.history.scrollRestoration = 'manual';

    function deviceIdFromPath() {
      return window.location.pathname.match(/^\/devices\/(\d+)\/?$/)?.[1] || '';
    }

    setDevicePageId((current) => current || deviceIdFromPath());
    function handlePopState() {
      setDevicePageId(deviceIdFromPath());
    }
    window.addEventListener('popstate', handlePopState);
    return () => {
      window.removeEventListener('popstate', handlePopState);
      window.history.scrollRestoration = previousScrollRestoration;
    };
  }, []);

  useEffect(() => {
    tableStateRef.current = {
      search,
      deviceStatus,
      firstSeenPeriod,
      deviceLimit,
      deviceOffset,
      deviceOrdering,
    };
  }, [search, deviceStatus, firstSeenPeriod, deviceOrdering]);

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
        status:
          currentTableState.deviceStatus && currentTableState.deviceStatus !== 'new'
            ? currentTableState.deviceStatus
            : undefined,
        known: currentTableState.deviceStatus === 'new' ? 'false' : undefined,
        first_seen: currentTableState.firstSeenPeriod || undefined,
        limit: currentTableState.deviceLimit,
        offset: currentTableState.deviceOffset,
        ordering: currentTableState.deviceOrdering || undefined,
      };
      const mapDeviceParams = {
        limit: 100,
        ordering: 'ip',
      };
      const dashboardEventParams = {
        limit: 8,
      };

      const settingsRequest = canManageUsers
        ? apiRequest('settings/')
        : Promise.resolve({ data: null });
      const [deviceData, mapDeviceData, statusData, dashboardEventData, settingsData] =
        await Promise.all([
          apiRequest('device/', { params: deviceParams }),
          apiRequest('device/', { params: mapDeviceParams }),
          apiRequest('scan/status/'),
          apiRequest('events/', { params: dashboardEventParams }),
          settingsRequest,
        ]);

      setDevices(deviceData.data || []);
      setMapDevices(mapDeviceData.data || []);
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
      setScanStatus(statusData.data || statusData.active_scan || null);
      setScanVisibility(statusData.visibility || null);
      if (statusData.time_zone) {
        setDashboardTimeZone(statusData.time_zone);
      }
      setDashboardEvents(dashboardEventData.data || []);
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

  async function loadScanData({ notifyOnError = false, notifyOnSuccess = false } = {}) {
    try {
      const statusData = await apiRequest('scan/status/');
      setScanStatus(statusData.data || statusData.active_scan || null);
      setScanVisibility(statusData.visibility || null);
      if (statusData.time_zone) {
        setDashboardTimeZone(statusData.time_zone);
      }
      if (notifyOnSuccess) {
        showSuccessNotification('Scan refreshed', 'Latest scan status loaded.');
      }
    } catch (err) {
      if (notifyOnError) {
        showErrorNotification('Scan refresh failed', err.message);
      }
    }
  }

  async function loadEventsData({ notifyOnError = false, offset = 0, append = false } = {}) {
    try {
      const payload = await apiRequest('events/', {
        params: {
          event_type: eventType || undefined,
          limit: activityPageLimit,
          offset,
        },
      });
      const nextEvents = payload.data || [];
      setEvents((current) => (append ? appendUniqueById(current, nextEvents) : nextEvents));
      setEventPagination(payload.pagination || null);
    } catch (err) {
      if (notifyOnError) {
        showErrorNotification('Events refresh failed', err.message);
      }
    }
  }

  async function loadScanRunsData({ notifyOnError = false, offset = 0, append = false } = {}) {
    try {
      const payload = await apiRequest('scan/runs/', {
        params: {
          limit: activityPageLimit,
          offset,
        },
      });
      const nextRuns = payload.data || [];
      setScanRuns((current) => (append ? appendUniqueById(current, nextRuns) : nextRuns));
      setScanRunPagination(payload.pagination || null);
    } catch (err) {
      if (notifyOnError) {
        showErrorNotification('Scan history refresh failed', err.message);
      }
    }
  }

  async function loadNotificationsData({ notifyOnError = false, offset = 0, append = false } = {}) {
    try {
      const payload = await apiRequest('notifications/', {
        params: {
          limit: activityPageLimit,
          offset,
        },
      });
      const nextNotifications = payload.data || [];
      setNotifications((current) => (
        append ? appendUniqueById(current, nextNotifications) : nextNotifications
      ));
      setNotificationPagination(payload.pagination || null);
    } catch (err) {
      if (notifyOnError) {
        showErrorNotification('Notifications refresh failed', err.message);
      }
    }
  }

  async function loadMoreEventsData() {
    if (!hasNextActivityPage(eventPagination) || activityLoadingMore.events) {
      return;
    }
    setActivityLoadingMore((current) => ({ ...current, events: true }));
    try {
      await loadEventsData({
        notifyOnError: true,
        offset: eventPagination.next_offset,
        append: true,
      });
    } finally {
      setActivityLoadingMore((current) => ({ ...current, events: false }));
    }
  }

  async function loadMoreScanRunsData() {
    if (!hasNextActivityPage(scanRunPagination) || activityLoadingMore.scanRuns) {
      return;
    }
    setActivityLoadingMore((current) => ({ ...current, scanRuns: true }));
    try {
      await loadScanRunsData({
        notifyOnError: true,
        offset: scanRunPagination.next_offset,
        append: true,
      });
    } finally {
      setActivityLoadingMore((current) => ({ ...current, scanRuns: false }));
    }
  }

  async function loadMoreNotificationsData() {
    if (!hasNextActivityPage(notificationPagination) || activityLoadingMore.notifications) {
      return;
    }
    setActivityLoadingMore((current) => ({ ...current, notifications: true }));
    try {
      await loadNotificationsData({
        notifyOnError: true,
        offset: notificationPagination.next_offset,
        append: true,
      });
    } finally {
      setActivityLoadingMore((current) => ({ ...current, notifications: false }));
    }
  }

  useEffect(() => {
    if (devicePageId) {
      return;
    }
    const stored = window.sessionStorage.getItem(dashboardStateStorageKey);
    if (!stored) {
      return;
    }
    try {
      const state = JSON.parse(stored);
      setSearch(state.search || '');
      setDeviceStatus(state.deviceStatus || '');
      setFirstSeenPeriod(state.firstSeenPeriod || '');
      setInventoryView(state.inventoryView || 'table');
      setMainView(state.mainView || 'dashboard');
      setDeviceOrdering(state.deviceOrdering || '');
      setEventType(state.eventType || '');
      tableStateRef.current = {
        ...tableStateRef.current,
        search: state.search || '',
        deviceStatus: state.deviceStatus || '',
        firstSeenPeriod: state.firstSeenPeriod || '',
        deviceOrdering: state.deviceOrdering || '',
      };
      pendingDashboardScrollRef.current = Math.max(Number(state.scrollY) || 0, 0);
      pendingDeviceListScrollRef.current = Math.max(
        Number(state.deviceListScrollTop) || 0,
        0
      );
    } catch {
      window.sessionStorage.removeItem(dashboardStateStorageKey);
    }
  }, [devicePageId]);

  useEffect(() => {
    if (devicePageId || loading || pendingDashboardScrollRef.current === null) {
      return undefined;
    }

    const scrollTop = pendingDashboardScrollRef.current;
    pendingDashboardScrollRef.current = null;
    let animationFrame = null;
    let attempts = 0;
    const restoreScroll = () => {
      window.scrollTo({ top: scrollTop, behavior: 'auto' });
      attempts += 1;
      if (attempts < 12 && Math.abs(window.scrollY - scrollTop) > 1) {
        animationFrame = window.requestAnimationFrame(restoreScroll);
      }
    };
    animationFrame = window.requestAnimationFrame(restoreScroll);
    const fallbackTimers = [150, 400, 800].map((delay) =>
      window.setTimeout(() => {
        window.scrollTo({ top: scrollTop, behavior: 'auto' });
      }, delay)
    );

    return () => {
      if (animationFrame !== null) {
        window.cancelAnimationFrame(animationFrame);
      }
      fallbackTimers.forEach((timer) => window.clearTimeout(timer));
    };
  }, [devicePageId, devices.length, loading, mainView]);

  useEffect(() => {
    if (
      devicePageId ||
      loading ||
      inventoryView !== 'table' ||
      pendingDeviceListScrollRef.current === null
    ) {
      return undefined;
    }

    const scrollTop = pendingDeviceListScrollRef.current;
    pendingDeviceListScrollRef.current = null;
    let animationFrame = null;
    let attempts = 0;
    const restoreScroll = () => {
      const list = deviceListRef.current;
      if (!list) {
        attempts += 1;
      } else {
        list.scrollTop = scrollTop;
        attempts += 1;
        if (Math.abs(list.scrollTop - scrollTop) <= 1) {
          return;
        }
      }
      if (attempts < 12) {
        animationFrame = window.requestAnimationFrame(restoreScroll);
      }
    };
    animationFrame = window.requestAnimationFrame(restoreScroll);
    const fallbackTimers = [150, 400, 800].map((delay) =>
      window.setTimeout(() => {
        if (deviceListRef.current) {
          deviceListRef.current.scrollTop = scrollTop;
        }
      }, delay)
    );

    return () => {
      if (animationFrame !== null) {
        window.cancelAnimationFrame(animationFrame);
      }
      fallbackTimers.forEach((timer) => window.clearTimeout(timer));
    };
  }, [devicePageId, devices.length, inventoryView, loading, mainView]);

  useEffect(() => {
    loadData();
    const timer = window.setInterval(() => loadData({ quiet: true }), 60000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    const timer = window.setInterval(() => loadScanData(), 10000);
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
    if (mainView === 'events') {
      loadEventsData({ notifyOnError: true });
    }
  }, [mainView, eventType]);

  useEffect(() => {
    if (mainView === 'history') {
      loadScanRunsData({ notifyOnError: true });
    }
  }, [mainView]);

  useEffect(() => {
    if (mainView === 'notifications') {
      loadNotificationsData({ notifyOnError: true });
    }
  }, [mainView]);

  useEffect(() => {
    const timer = window.setTimeout(() => loadData({ quiet: true }), 250);
    return () => window.clearTimeout(timer);
  }, [search, deviceStatus, firstSeenPeriod, deviceOrdering]);

  async function runScan() {
    setRefreshing(true);
    setError('');
    try {
      await apiRequest('scan/', {
        method: 'POST',
        body: {},
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
                    <UnstyledButton
                      className={`version-pill ${hasVersionIndicator ? 'has-update' : ''}`}
                      onClick={() => setChangelogOpened(true)}
                      aria-label={`LanGuard version ${APP_VERSION}`}
                    >
                      v{APP_VERSION}
                      {hasVersionIndicator && <span className="version-dot" aria-hidden="true" />}
                    </UnstyledButton>
                  </Tooltip>
                  <Tooltip label="GitHub project">
                    <ActionIcon
                      component="a"
                      href="https://github.com/hillaliy/LanGuard"
                      target="_blank"
                      rel="noreferrer"
                      variant="light"
                      color="gray"
                      size="sm"
                      aria-label="GitHub project"
                    >
                      <IconBrandGithub size={17} />
                    </ActionIcon>
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
                    {formatTopbarDate(currentTime, displayTimeZone)}
                  </Text>
                  <Text size="sm" fw={700} lh={1.15}>
                    {formatTopbarTime(currentTime, displayTimeZone)}
                  </Text>
                </Box>
              </Group>
              <ColorSchemeControl />
              <Button
                size="sm"
                leftSection={<IconRefresh size={17} />}
                onClick={runScan}
                loading={refreshing}
                className="topbar-scan-button"
              >
                Run Scan
              </Button>
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

      <div className="app-layout">
        <aside className="app-sidebar" aria-label="Primary navigation">
          <Stack className="sidebar-nav" gap={6}>
            <Button
              className="sidebar-nav-button"
              variant={!devicePageId && mainView === 'dashboard' ? 'filled' : 'subtle'}
              justify="flex-start"
              leftSection={<IconLayoutDashboard size={18} />}
              onClick={() => navigateToView('dashboard')}
              fullWidth
            >
              Dashboard
            </Button>
            <Button
              className="sidebar-nav-button"
              variant={!devicePageId && mainView === 'home-map' ? 'filled' : 'subtle'}
              justify="flex-start"
              leftSection={<IconSmartHome size={18} />}
              onClick={() => navigateToView('home-map')}
              fullWidth
            >
              Home Map
            </Button>
            <Divider my={4} />
            <Button
              className="sidebar-nav-button"
              variant={!devicePageId && mainView === 'events' ? 'filled' : 'subtle'}
              justify="flex-start"
              leftSection={<IconBell size={18} />}
              onClick={() => navigateToView('events')}
              fullWidth
            >
              Events
            </Button>
            <Button
              className="sidebar-nav-button"
              variant={!devicePageId && mainView === 'history' ? 'filled' : 'subtle'}
              justify="flex-start"
              leftSection={<IconHistory size={18} />}
              onClick={() => navigateToView('history')}
              fullWidth
            >
              Scan history
            </Button>
            <Button
              className="sidebar-nav-button"
              variant={!devicePageId && mainView === 'notifications' ? 'filled' : 'subtle'}
              justify="flex-start"
              leftSection={<IconBell size={18} />}
              onClick={() => navigateToView('notifications')}
              fullWidth
            >
              Notifications
            </Button>
            {canManageUsers && (
              <>
                <Divider my={4} />
                <Button
                  className="sidebar-nav-button"
                  component="a"
                  href={getAdminUrl()}
                  target="_blank"
                  rel="noreferrer"
                  variant="subtle"
                  justify="flex-start"
                  leftSection={<IconShieldLock size={18} />}
                  fullWidth
                >
                  Admin site
                </Button>
                <Button
                  className="sidebar-nav-button"
                  variant={!devicePageId && mainView === 'settings' ? 'filled' : 'subtle'}
                  justify="flex-start"
                  leftSection={<IconSettings size={18} />}
                  onClick={() => navigateToView('settings')}
                  fullWidth
                >
                  Settings
                </Button>
              </>
            )}
          </Stack>
        </aside>

      <Container size="xl" py="xl" className="app-content">
        <LoadingOverlay visible={loading} />
        <Stack gap="lg">
          {error && (
            <Alert color="red" icon={<IconAlertCircle size={18} />} withCloseButton onClose={() => setError('')}>
              {error}
            </Alert>
          )}

          {devicePageId ? (
            <DeviceDetailsPage
              deviceId={devicePageId}
              onBack={returnFromDevicePage}
              onSaved={async () => loadData({ quiet: true })}
              onDeleted={async () => {
                storeDashboardNavigationState({ mainView: 'dashboard', scrollY: 0 });
                window.history.replaceState({}, '', '/');
                setDevicePageId('');
                setMainView('dashboard');
              }}
              timeZone={displayTimeZone}
              roomOptions={roomOptions}
            />
          ) : mainView === 'home-map' ? (
            <HomeMap
              devices={mapDevices}
              onSelectDevice={openDevicePage}
            />
          ) : mainView === 'settings' && canManageUsers ? (
            <SettingsPage
              onSaved={async () => {
                await loadData({ quiet: true });
              }}
            />
          ) : mainView === 'events' ? (
            <EventsPage
              events={events}
              eventType={eventType}
              setEventType={setEventType}
              timeZone={displayTimeZone}
              pagination={eventPagination}
              loadingMore={activityLoadingMore.events}
              onLoadMore={loadMoreEventsData}
              onSelectDevice={openDevicePage}
            />
          ) : mainView === 'history' ? (
            <ScanHistoryPage
              scanRuns={scanRuns}
              timeZone={displayTimeZone}
              pagination={scanRunPagination}
              loadingMore={activityLoadingMore.scanRuns}
              onLoadMore={loadMoreScanRunsData}
            />
          ) : mainView === 'notifications' ? (
            <NotificationsPage
              notifications={notifications}
              timeZone={displayTimeZone}
              pagination={notificationPagination}
              loadingMore={activityLoadingMore.notifications}
              onLoadMore={loadMoreNotificationsData}
            />
          ) : (
            <>
          <DashboardStatusCards counters={counters} />

          <div className="dashboard-summary-grid">
            <NetworkHealthCard counters={counters} />
            <AutomaticScanningCard appSettings={appSettings} scanVisibility={scanVisibility} />
            <LatestScanCard
              scanStatus={scanStatus}
              scanVisibility={scanVisibility}
              timeZone={displayTimeZone}
              onOpenDetails={scanDetailsModal.open}
            />
          </div>

          <DashboardInsightCards
            events={dashboardEvents}
            devices={mapDevices}
            onSelectDevice={openDevicePage}
            timeZone={displayTimeZone}
          />

          <Paper className="content-panel devices-content-panel" radius="md">
            <Stack gap={0}>
              <Group className="devices-panel-header" justify="space-between" p="md">
                <Group>
                  <IconNetwork size={22} />
                  <Title order={4}>Devices</Title>
                </Group>
                <Group className="devices-panel-controls">
                  <SegmentedControl
                    data={inventoryViewOptions}
                    value={inventoryView}
                    onChange={setInventoryView}
                    aria-label="Inventory view"
                  />
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
                    w={150}
                    placeholder="First seen"
                    clearable
                    data={firstSeenPeriodOptions}
                    value={firstSeenPeriod}
                    aria-label="Filter by first seen"
                    onChange={(value) => setFirstSeenPeriod(value || '')}
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
              {inventoryView === 'roles' ? (
                <Box p="md">
                  <RolesMap
                    devices={mapDevices}
                    onSelectDevice={openDevicePage}
                  />
                  <Text size="xs" c="dimmed" mt="sm">
                    Showing up to 100 devices grouped by role.
                  </Text>
                </Box>
              ) : (
                <>
                  <Box className="device-list-toolbar" p="md">
                    <Group justify="space-between" wrap="wrap" gap="sm">
                      <Group gap="xs">
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
                        Showing {deviceEnd} of {devicePagination.count || deviceEnd} devices
                      </Text>
                    </Group>
                  </Box>
                  <Stack ref={deviceListRef} className="device-list" gap={0}>
                    {filteredDevices.map((device) => (
                      <UnstyledButton
                        className="device-list-row"
                        key={device.id}
                        onClick={() => openDevicePage(device)}
                      >
                        <Group className="device-list-primary" gap="md" align="center" wrap="nowrap">
                          <span className="device-list-icon">
                            <DeviceIconStack device={device} size={21} />
                          </span>
                          <Box className="device-list-title">
                            <Group gap="xs" wrap="nowrap">
                              <Text fw={800} className="truncate-cell">{displayDeviceName(device)}</Text>
                              <GatewayBadge device={device} compact />
                              <Badge
                                className="device-known-badge"
                                color={device.known ? 'teal' : 'yellow'}
                                variant="light"
                              >
                                {device.known ? 'Known' : 'New'}
                              </Badge>
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
                            <Text size="xs" c="dimmed">IP</Text>
                            <Text fw={700} className="mobile-mono-value device-list-ip-value">{device.ip}</Text>
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
                  <Stack className="device-mobile-list" gap={0}>
                    {filteredDevices.map((device) => (
                      <UnstyledButton
                        className="device-mobile-row"
                        key={device.id}
                        onClick={() => openDevicePage(device)}
                      >
                        <Group justify="space-between" align="flex-start" wrap="nowrap">
                          <Group gap="sm" align="flex-start" wrap="nowrap" className="device-mobile-main">
                            <span className="device-mobile-icon">
                              <DeviceIconStack device={device} size={18} />
                            </span>
                            <Box className="device-mobile-title">
                              <Text fw={700} className="truncate-cell">{displayDeviceName(device)}</Text>
                              <DeviceStatusInline device={device} muted />
                            </Box>
                          </Group>
                          <Group gap={6} justify="flex-end" wrap="wrap">
                            <RiskBadge device={device} compact />
                            <GatewayBadge device={device} compact />
                            <Badge
                              className="device-known-badge"
                              color={device.known ? 'teal' : 'yellow'}
                              variant="light"
                            >
                              {device.known ? 'Known' : 'New'}
                            </Badge>
                          </Group>
                        </Group>
                        <SimpleGrid cols={2} spacing="xs" mt="sm">
                          <Box>
                            <Text size="xs" c="dimmed">IP</Text>
                            <Text size="sm" className="mobile-mono-value">{device.ip}</Text>
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
                            <Text size="xs" c="dimmed">MAC</Text>
                            <Text size="sm" className="mobile-mono-value">{device.mac}</Text>
                          </Box>
                          <Box className="device-mobile-wide">
                            <Text size="xs" c="dimmed">Ports</Text>
                            <PortSummary ports={device.open_ports || []} />
                          </Box>
                        </SimpleGrid>
                      </UnstyledButton>
                    ))}
                  </Stack>
                </>
              )}
            </Stack>
          </Paper>

            </>
          )}
        </Stack>
      </Container>
      </div>

      <Modal
        opened={scanDetailsOpened}
        onClose={scanDetailsModal.close}
        title="Latest scan details"
        centered
        size="lg"
      >
        <ScanDetailsContent
          scanStatus={scanStatus}
          scanVisibility={scanVisibility}
          timeZone={displayTimeZone}
        />
      </Modal>

      <UserManagementModal
        opened={usersModalOpened}
        onClose={usersModal.close}
        currentUser={user}
        onCurrentUserUpdated={updateCurrentUser}
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


export function LanGuardApplication({ initialDeviceId = null }) {
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
      initialDeviceId={initialDeviceId}
    />
  );
}

export default function Home() {
  return <LanGuardApplication />;
}
