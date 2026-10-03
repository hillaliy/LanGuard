import { useEffect, useMemo, useRef, useState } from 'react';
import { buildRoomOptions } from '../utils/device';
import { formatScanRange } from '../utils/scan';

export const outsideNetworkRangeFilter = 'outside';

export function retainAvailableNetworkRangeFilters(current, configuredRanges) {
  const available = current.filter(
    (value) => value === outsideNetworkRangeFilter || configuredRanges.includes(value)
  );
  return available.length === current.length ? current : available;
}

export function useDeviceInventory({ integrationStatus }) {
  const [devices, setDevices] = useState([]);
  const [mapDevices, setMapDevices] = useState([]);
  const [roleDevices, setRoleDevices] = useState([]);
  const [roleDeviceCount, setRoleDeviceCount] = useState(0);
  const [devicePagination, setDevicePagination] = useState({
    count: 0,
    limit: 100,
    offset: 0,
    next_offset: null,
    previous_offset: null,
  });
  const [counters, setCounters] = useState({});
  const [search, setSearch] = useState('');
  const [deviceStatus, setDeviceStatus] = useState('');
  const [networkRangeFilter, setNetworkRangeFilter] = useState([]);
  const [configuredNetworkRanges, setConfiguredNetworkRanges] = useState([]);
  const [configuredNetworkRangeLabels, setConfiguredNetworkRangeLabels] = useState({});
  const [bulkEditEnabled, setBulkEditEnabled] = useState(false);
  const [selectedDeviceIds, setSelectedDeviceIds] = useState([]);
  const [bulkUpdatingDevices, setBulkUpdatingDevices] = useState(false);
  const [firstSeenPeriod, setFirstSeenPeriod] = useState('');
  const [homeBoxLinkStatus, setHomeBoxLinkStatus] = useState('');
  const [inventoryView, setInventoryView] = useState('table');
  const [deviceOrdering, setDeviceOrdering] = useState('');
  const [deviceLimit, setDeviceLimit] = useState(100);
  const [deviceOffset, setDeviceOffset] = useState(0);
  const deviceListRef = useRef(null);
  const tableStateRef = useRef({
    search: '',
    deviceStatus: '',
    networkRangeFilter: [],
    firstSeenPeriod: '',
    homeBoxLinkStatus: '',
    deviceLimit: 100,
    deviceOffset: 0,
    deviceOrdering: '',
    inventoryView: 'table',
  });

  const filteredDevices = useMemo(() => devices, [devices]);
  const selectableDeviceIds = useMemo(
    () => filteredDevices.map((device) => device.id),
    [filteredDevices]
  );
  const allSelectableDevicesSelected = Boolean(
    selectableDeviceIds.length
    && selectableDeviceIds.every((deviceId) => selectedDeviceIds.includes(deviceId))
  );
  const roomOptions = useMemo(() => buildRoomOptions(mapDevices), [mapDevices]);
  const networkRangeOptions = useMemo(
    () => [
      ...configuredNetworkRanges.map((networkRange) => ({
        value: networkRange,
        label: formatScanRange(networkRange, configuredNetworkRangeLabels),
      })),
      { value: outsideNetworkRangeFilter, label: 'Outside configured ranges' },
    ],
    [configuredNetworkRangeLabels, configuredNetworkRanges]
  );
  const homeBoxStatusKnown = Boolean(integrationStatus?.homebox);
  const showHomeBoxFilter = Boolean(
    integrationStatus?.homebox?.enabled && integrationStatus?.homebox?.configured
  );
  const showFirstSeen = deviceOrdering === 'firstseen' || deviceOrdering === '-firstseen';

  useEffect(() => {
    if (!bulkEditEnabled) return;
    setSelectedDeviceIds((current) => {
      const available = current.filter((deviceId) => selectableDeviceIds.includes(deviceId));
      return available.length === current.length ? current : available;
    });
  }, [bulkEditEnabled, selectableDeviceIds]);

  useEffect(() => {
    if (inventoryView !== 'table' && bulkEditEnabled) {
      setBulkEditEnabled(false);
      setSelectedDeviceIds([]);
    }
  }, [bulkEditEnabled, inventoryView]);

  useEffect(() => {
    tableStateRef.current = {
      search,
      deviceStatus,
      networkRangeFilter,
      firstSeenPeriod,
      homeBoxLinkStatus,
      deviceLimit,
      deviceOffset,
      deviceOrdering,
      inventoryView,
    };
  }, [
    search,
    deviceStatus,
    networkRangeFilter,
    firstSeenPeriod,
    homeBoxLinkStatus,
    deviceOrdering,
    inventoryView,
    deviceLimit,
    deviceOffset,
  ]);

  useEffect(() => {
    setDeviceOffset(0);
  }, [
    search,
    deviceStatus,
    networkRangeFilter,
    firstSeenPeriod,
    homeBoxLinkStatus,
    deviceOrdering,
    deviceLimit,
  ]);

  useEffect(() => {
    if (homeBoxStatusKnown && !showHomeBoxFilter) setHomeBoxLinkStatus('');
  }, [homeBoxStatusKnown, showHomeBoxFilter]);

  function toggleBulkDevice(device) {
    setSelectedDeviceIds((current) =>
      current.includes(device.id)
        ? current.filter((deviceId) => deviceId !== device.id)
        : [...current, device.id]
    );
  }

  function closeBulkEdit() {
    setBulkEditEnabled(false);
    setSelectedDeviceIds([]);
  }

  function toggleAllBulkDevices() {
    setSelectedDeviceIds(allSelectableDevicesSelected ? [] : selectableDeviceIds);
  }

  return {
    devices, setDevices, filteredDevices, mapDevices, setMapDevices,
    roleDevices, setRoleDevices, roleDeviceCount, setRoleDeviceCount,
    devicePagination, setDevicePagination, counters, setCounters,
    search, setSearch, deviceStatus, setDeviceStatus,
    networkRangeFilter, setNetworkRangeFilter,
    configuredNetworkRanges, setConfiguredNetworkRanges,
    configuredNetworkRangeLabels, setConfiguredNetworkRangeLabels,
    bulkEditEnabled, setBulkEditEnabled, selectedDeviceIds, setSelectedDeviceIds,
    bulkUpdatingDevices, setBulkUpdatingDevices,
    firstSeenPeriod, setFirstSeenPeriod, homeBoxLinkStatus, setHomeBoxLinkStatus,
    inventoryView, setInventoryView, deviceOrdering, setDeviceOrdering,
    deviceLimit, setDeviceLimit, deviceOffset, setDeviceOffset,
    deviceListRef, tableStateRef, roomOptions, networkRangeOptions,
    showHomeBoxFilter, showFirstSeen,
    toggleBulkDevice, closeBulkEdit, toggleAllBulkDevices,
  };
}
