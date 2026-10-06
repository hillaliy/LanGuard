import {
  ActionIcon,
  Group,
  MultiSelect,
  SegmentedControl,
  Select,
  TextInput,
  Title,
} from '@mantine/core';
import { IconNetwork, IconSearch, IconX } from '@tabler/icons-react';

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

export default function DeviceInventoryFilters({
  inventoryView,
  onInventoryViewChange,
  filters,
  showHomeBoxFilter,
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
  const selectedDeviceStatus =
    deviceStatusOptions.find((option) => option.value === deviceStatus) || null;

  return (
    <Group className="devices-panel-header" justify="space-between" p="md">
      <Group className="devices-panel-heading">
        <IconNetwork size={22} />
        <Title order={4}>Devices</Title>
      </Group>
      <SegmentedControl
        className="device-view-control"
        data={inventoryViewOptions}
        value={inventoryView}
        onChange={onInventoryViewChange}
        aria-label="Inventory view"
      />
      <Group className={`devices-panel-controls ${showHomeBoxFilter ? 'with-homebox' : ''}`}>
        <Select
          className="device-status-filter"
          w={compactFilterWidth(deviceStatusOptions, deviceStatus, 'Status')}
          placeholder="Status"
          clearable
          data={deviceStatusOptions}
          value={deviceStatus}
          aria-label={selectedDeviceStatus?.label || 'Status'}
          onChange={(value) => onDeviceStatusChange(value || '')}
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
          onChange={onNetworkRangeFilterChange}
          maxDropdownHeight={260}
          styles={{ option: { whiteSpace: 'nowrap' } }}
        />
        <Select
          className="device-first-seen-filter"
          w={compactFilterWidth(firstSeenPeriodOptions, firstSeenPeriod, 'First seen', 140, 190)}
          placeholder="First seen"
          clearable
          data={firstSeenPeriodOptions}
          value={firstSeenPeriod}
          aria-label="Filter by first seen"
          onChange={(value) => onFirstSeenPeriodChange(value || '')}
        />
        {showHomeBoxFilter && (
          <Select
            className="device-homebox-filter"
            w={compactFilterWidth(homeBoxLinkOptions, homeBoxLinkStatus, 'HomeBox')}
            placeholder="HomeBox"
            clearable
            data={homeBoxLinkOptions}
            value={homeBoxLinkStatus}
            aria-label="Filter by HomeBox link"
            onChange={(value) => onHomeBoxLinkStatusChange(value || '')}
          />
        )}
        <TextInput
          className="device-search"
          w={{ base: 180, sm: 260 }}
          placeholder="Search"
          leftSection={<IconSearch size={17} />}
          rightSection={search ? (
            <ActionIcon
              aria-label="Clear device search"
              color="gray"
              size="sm"
              variant="subtle"
              onClick={() => onSearchChange('')}
            >
              <IconX size={16} />
            </ActionIcon>
          ) : null}
          value={search}
          onChange={(event) => onSearchChange(event.currentTarget.value)}
        />
      </Group>
    </Group>
  );
}
