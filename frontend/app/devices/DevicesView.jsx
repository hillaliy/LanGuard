'use client';

import { Divider, Paper, Stack } from '@mantine/core';
import DeviceDesktopList from './DeviceDesktopList';
import DeviceInventoryFilters from './DeviceInventoryFilters';
import DeviceListToolbar, { DeviceMobileSortToolbar } from './DeviceListToolbar';
import DeviceMobileList from './DeviceMobileList';
import DevicePagination from './DevicePagination';
import DeviceRolesView from './DeviceRolesView';

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
  const deviceCount = pagination.data.count || 0;
  const deviceStart = deviceCount ? pagination.data.offset + 1 : 0;
  const deviceEnd = Math.min(pagination.data.offset + devices.length, deviceCount);
  const deviceRangeLabel = `Showing ${deviceStart}-${deviceEnd} of ${deviceCount} devices`;

  return (
    <Paper className="content-panel devices-content-panel" radius="md">
      <Stack gap={0}>
        <DeviceInventoryFilters
          inventoryView={inventoryView}
          onInventoryViewChange={onInventoryViewChange}
          filters={filters}
          showHomeBoxFilter={showHomeBoxFilter}
        />
        <Divider />
        {inventoryView === 'roles' ? (
          <DeviceRolesView
            devices={roleDevices}
            totalCount={roleDeviceCount}
            onSelectDevice={onSelectDevice}
          />
        ) : (
          <>
            <DeviceListToolbar
              devices={devices}
              rangeLabel={deviceRangeLabel}
              ordering={ordering.value}
              onOrderingChange={ordering.onChange}
              bulkEdit={bulkEdit}
            />
            <DeviceDesktopList
              devices={devices}
              bulkEdit={bulkEdit}
              showFirstSeen={showFirstSeen}
              timeZone={timeZone}
              listRef={listRef}
              onSelectDevice={onSelectDevice}
            />
            <DeviceMobileSortToolbar
              ordering={ordering.value}
              onChange={ordering.onChange}
              rangeLabel={deviceRangeLabel}
            />
            <DeviceMobileList
              devices={devices}
              bulkEdit={bulkEdit}
              showFirstSeen={showFirstSeen}
              timeZone={timeZone}
              onSelectDevice={onSelectDevice}
            />
            <DevicePagination
              pagination={pagination.data}
              limit={pagination.limit}
              loading={pagination.loading}
              refreshing={pagination.refreshing}
              onLimitChange={pagination.onLimitChange}
              onOffsetChange={pagination.onOffsetChange}
            />
          </>
        )}
      </Stack>
    </Paper>
  );
}
