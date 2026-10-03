import { Box, Button, Checkbox, Group, Text } from '@mantine/core';
import { IconCheck, IconEdit, IconShieldCheck, IconUserPlus } from '@tabler/icons-react';
import { sortableOrdering, sortableOrderingDescendingFirst } from './deviceListUtils';

export function DeviceSortButtons({ ordering, onChange }) {
  return (
    <>
      <Button
        size="xs"
        variant={ordering === 'name' ? 'light' : 'subtle'}
        onClick={() => onChange(sortableOrdering('name', ordering))}
      >Name</Button>
      <Button
        size="xs"
        variant={ordering === 'ip' ? 'light' : 'subtle'}
        onClick={() => onChange(sortableOrdering('ip', ordering))}
      >IP</Button>
      <Button
        size="xs"
        variant={ordering === '-lastseen' ? 'light' : 'subtle'}
        onClick={() => onChange(sortableOrdering('lastseen', ordering))}
      >Last seen</Button>
      <Button
        size="xs"
        variant={['firstseen', '-firstseen'].includes(ordering) ? 'light' : 'subtle'}
        onClick={() => onChange(sortableOrderingDescendingFirst('firstseen', ordering))}
      >First seen</Button>
    </>
  );
}

export default function DeviceListToolbar({
  devices,
  rangeLabel,
  ordering,
  onOrderingChange,
  bulkEdit,
}) {
  const {
    enabled,
    selectedDeviceIds,
    updating,
    canEditDevices,
    onToggleAll,
    onClose,
    onUpdate,
    onEnable,
  } = bulkEdit;
  const selectableDeviceIds = devices.map((device) => device.id);
  const allSelected = Boolean(
    selectableDeviceIds.length
    && selectableDeviceIds.every((deviceId) => selectedDeviceIds.includes(deviceId))
  );
  const someSelected = selectedDeviceIds.length > 0;

  return (
    <Box className="device-list-toolbar" p="md">
      <Group justify="space-between" wrap="wrap" gap="sm">
        <Group gap="xs">
          {enabled && (
            <Checkbox
              label="Select all"
              checked={allSelected}
              indeterminate={someSelected && !allSelected}
              disabled={!selectableDeviceIds.length}
              onChange={onToggleAll}
            />
          )}
          <DeviceSortButtons ordering={ordering} onChange={onOrderingChange} />
        </Group>
        <Group gap="sm" wrap="wrap">
          {enabled ? (
            <>
              <Text size="sm" c="dimmed">{selectedDeviceIds.length} selected</Text>
              <Button size="xs" variant="default" onClick={onClose}>Cancel</Button>
              <Button
                size="xs"
                leftSection={<IconShieldCheck size={16} />}
                disabled={!selectedDeviceIds.length}
                loading={updating}
                onClick={() => onUpdate('known')}
              >Mark as known</Button>
              <Button
                size="xs"
                variant="light"
                leftSection={<IconUserPlus size={16} />}
                disabled={!selectedDeviceIds.length}
                loading={updating}
                onClick={() => onUpdate('visitor')}
              >Mark as visitor</Button>
              <Button
                size="xs"
                variant="light"
                leftSection={<IconCheck size={16} />}
                disabled={!selectedDeviceIds.length}
                loading={updating}
                onClick={() => onUpdate('attention')}
              >Mark attention as reviewed</Button>
            </>
          ) : (
            <>
              <Text size="sm" c="dimmed">{rangeLabel}</Text>
              {canEditDevices && (
                <Button
                  size="xs"
                  variant="light"
                  leftSection={<IconEdit size={16} />}
                  disabled={!devices.length}
                  onClick={onEnable}
                >Bulk edit</Button>
              )}
            </>
          )}
        </Group>
      </Group>
    </Box>
  );
}

export function DeviceMobileSortToolbar({ ordering, onChange, rangeLabel }) {
  return (
    <Box className="device-mobile-sort-toolbar" p="md">
      <Group justify="space-between" align="center" wrap="wrap" gap="sm">
        <Group className="device-mobile-sort-buttons" gap="xs" wrap="wrap">
          <DeviceSortButtons ordering={ordering} onChange={onChange} />
        </Group>
        <Text size="sm" c="dimmed">{rangeLabel}</Text>
      </Group>
    </Box>
  );
}
