import { useEffect, useState } from 'react';
import { apiRequest, clearStoredUser } from '../api';
import { showErrorNotification, showServerNotification } from '../utils/notifications';
import { useDeviceInventory, retainAvailableNetworkRangeFilters } from './useDeviceInventory';
import { useLanGuardActivity } from './useLanGuardActivity';
import { useLanGuardNavigation } from './useLanGuardNavigation';
import { useLanGuardSession } from './useLanGuardSession';
import { useLiveClock } from './useLiveClock';

export function useLanGuardController({
  user,
  onLogout,
  onUserUpdated,
  initialDeviceId = null,
  initialView = 'dashboard',
}) {
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState('');
  const [scanStatus, setScanStatus] = useState(null);
  const [scanVisibility, setScanVisibility] = useState(null);
  const [integrationStatus, setIntegrationStatus] = useState({});
  const [speedtestTrackerPayload, setSpeedtestTrackerPayload] = useState(null);
  const [appSettings, setAppSettings] = useState(null);
  const [dashboardTimeZone, setDashboardTimeZone] = useState();
  const [eventType, setEventType] = useState('');
  const currentTime = useLiveClock();
  const session = useLanGuardSession({ user, onLogout, onUserUpdated });
  const inventory = useDeviceInventory({ integrationStatus });
  const navigation = useLanGuardNavigation({
    initialDeviceId,
    initialView,
    loading,
    devicesLength: inventory.devices.length,
    inventory,
    eventType,
    setEventType,
    reloadData: loadData,
  });
  const activity = useLanGuardActivity({ mainView: navigation.mainView, eventType });

  const scanIsActive = Boolean(scanVisibility?.is_scanning);
  const scanButtonLabel = scanIsActive
    ? scanVisibility?.source === 'scheduled'
      ? 'Scheduled scan running'
      : scanVisibility?.source === 'manual'
        ? 'Manual scan running'
        : 'Scan running'
    : 'Run Scan';
  const displayTimeZone = appSettings?.time_zone || dashboardTimeZone || undefined;
  const showDnsActivity = Boolean(
    (integrationStatus?.adguard?.enabled && integrationStatus?.adguard?.configured)
    || (integrationStatus?.pihole?.enabled && integrationStatus?.pihole?.configured)
  );
  const showDockerInventory = Boolean(integrationStatus?.docker?.configured);

  function applyScanStatus(statusData) {
    setScanStatus(statusData.data || statusData.active_scan || null);
    setScanVisibility(statusData.visibility || null);
    setIntegrationStatus(statusData.integrations || {});
    const nextNetworkRanges = Array.isArray(statusData.network_ranges)
      ? statusData.network_ranges
      : [];
    inventory.setConfiguredNetworkRanges(nextNetworkRanges);
    inventory.setConfiguredNetworkRangeLabels(statusData.network_range_labels || {});
    inventory.setNetworkRangeFilter((current) =>
      retainAvailableNetworkRangeFilters(current, nextNetworkRanges)
    );
    session.setAccessCapabilities(statusData.permissions || {});
    if (statusData.time_zone) setDashboardTimeZone(statusData.time_zone);
  }

  async function loadData({ quiet = false, notifyOnError = false, refreshIntegrations = false } = {}) {
    if (quiet) setRefreshing(true);
    else setLoading(true);
    setError('');

    try {
      const currentTableState = inventory.tableStateRef.current;
      const deviceFilterParams = {
        search: currentTableState.search,
        status:
          currentTableState.deviceStatus
            && !['attention', 'new', 'visitors', 'archived'].includes(
              currentTableState.deviceStatus
            )
            ? currentTableState.deviceStatus
            : undefined,
        needs_attention: currentTableState.deviceStatus === 'attention' ? 'true' : undefined,
        known: currentTableState.deviceStatus === 'new' ? 'false' : undefined,
        is_visitor: currentTableState.deviceStatus === 'visitors' ? 'true' : undefined,
        archived: currentTableState.deviceStatus === 'archived' ? 'true' : undefined,
        network_ranges: currentTableState.networkRangeFilter.length
          ? currentTableState.networkRangeFilter.join(',')
          : undefined,
        first_seen: currentTableState.firstSeenPeriod || undefined,
        homebox_linked: currentTableState.homeBoxLinkStatus
          ? String(currentTableState.homeBoxLinkStatus === 'linked')
          : undefined,
      };
      const deviceParams = {
        ...deviceFilterParams,
        limit: currentTableState.deviceLimit,
        offset: currentTableState.deviceOffset,
        ordering: currentTableState.deviceOrdering || undefined,
      };
      const roleDeviceRequest = currentTableState.inventoryView === 'roles'
        ? apiRequest('device/', {
          params: { ...deviceFilterParams, limit: 100, offset: 0, ordering: 'name' },
        })
        : Promise.resolve(null);
      const settingsRequest = session.canManageUsers
        ? apiRequest('settings/')
        : Promise.resolve({ data: null });
      const [
        deviceData,
        mapDeviceData,
        roleDeviceData,
        statusData,
        dashboardEventData,
        settingsData,
        speedtestData,
      ] = await Promise.all([
        apiRequest('device/', { params: deviceParams }),
        apiRequest('device/', { params: { limit: 100, ordering: 'ip' } }),
        roleDeviceRequest,
        apiRequest('scan/status/'),
        apiRequest('events/', { params: { limit: 8 } }),
        settingsRequest,
        apiRequest('integrations/speedtest-tracker/latest/', {
          params: { refresh: refreshIntegrations ? 'true' : undefined },
        }).catch(() => null),
      ]);

      inventory.setDevices(deviceData.data || []);
      inventory.setMapDevices(mapDeviceData.data || []);
      if (roleDeviceData) {
        inventory.setRoleDevices(roleDeviceData.data || []);
        inventory.setRoleDeviceCount(roleDeviceData.pagination?.count || 0);
      }
      inventory.setDevicePagination(
        deviceData.pagination || {
          count: 0,
          limit: currentTableState.deviceLimit,
          offset: currentTableState.deviceOffset,
          next_offset: null,
          previous_offset: null,
        }
      );
      inventory.setCounters(deviceData.counters || {});
      applyScanStatus(statusData);
      setSpeedtestTrackerPayload(speedtestData || null);
      activity.setDashboardEvents(dashboardEventData.data || []);
      if (settingsData.data) setAppSettings(settingsData.data);
    } catch (err) {
      setError(quiet ? '' : err.message);
      if (notifyOnError || quiet) showErrorNotification(err);
      if (err.message.toLowerCase().includes('credential')) {
        clearStoredUser();
        onLogout();
      }
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }

  async function loadScanData({ notifyOnError = false } = {}) {
    try {
      applyScanStatus(await apiRequest('scan/status/'));
    } catch (err) {
      if (notifyOnError) showErrorNotification(err);
    }
  }

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
    const timer = window.setTimeout(() => loadData({ quiet: true }), 250);
    return () => window.clearTimeout(timer);
  }, [
    inventory.search,
    inventory.deviceStatus,
    inventory.networkRangeFilter,
    inventory.firstSeenPeriod,
    inventory.homeBoxLinkStatus,
    inventory.inventoryView,
    inventory.deviceOrdering,
    inventory.deviceLimit,
    inventory.deviceOffset,
  ]);

  async function runScan() {
    if (scanIsActive || refreshing) return;
    setRefreshing(true);
    setError('');
    try {
      const payload = await apiRequest('scan/', { method: 'POST', body: {} });
      await loadData({ quiet: true });
      showServerNotification(payload);
    } catch (err) {
      setError(err.message);
      showErrorNotification(err);
    } finally {
      setRefreshing(false);
    }
  }

  async function updateSelectedDevices(classification) {
    if (!inventory.selectedDeviceIds.length) return;
    inventory.setBulkUpdatingDevices(true);
    try {
      const payload = await apiRequest('devices/bulk-update/', {
        method: 'POST',
        body:
          classification === 'attention'
            ? { ids: inventory.selectedDeviceIds, acknowledge_attention: true }
            : {
                ids: inventory.selectedDeviceIds,
                known: true,
                is_visitor: classification === 'visitor',
              },
      });
      inventory.closeBulkEdit();
      await loadData({ quiet: true });
      showServerNotification(payload);
    } catch (err) {
      showErrorNotification(err);
    } finally {
      inventory.setBulkUpdatingDevices(false);
    }
  }

  return {
    loading, refreshing, error, setError, currentTime,
    filteredDevices: inventory.filteredDevices,
    mapDevices: inventory.mapDevices,
    roleDevices: inventory.roleDevices,
    roleDeviceCount: inventory.roleDeviceCount,
    devicePagination: inventory.devicePagination,
    counters: inventory.counters,
    scanStatus, scanVisibility, speedtestTrackerPayload,
    scanRuns: activity.scanRuns,
    scanRunPagination: activity.scanRunPagination,
    dashboardEvents: activity.dashboardEvents,
    events: activity.events,
    eventPagination: activity.eventPagination,
    notifications: activity.notifications,
    notificationPagination: activity.notificationPagination,
    activityLoadingMore: activity.activityLoadingMore,
    appSettings,
    search: inventory.search, setSearch: inventory.setSearch,
    deviceStatus: inventory.deviceStatus, setDeviceStatus: inventory.setDeviceStatus,
    networkRangeFilter: inventory.networkRangeFilter,
    setNetworkRangeFilter: inventory.setNetworkRangeFilter,
    configuredNetworkRanges: inventory.configuredNetworkRanges,
    configuredNetworkRangeLabels: inventory.configuredNetworkRangeLabels,
    bulkEditEnabled: inventory.bulkEditEnabled,
    setBulkEditEnabled: inventory.setBulkEditEnabled,
    selectedDeviceIds: inventory.selectedDeviceIds,
    bulkUpdatingDevices: inventory.bulkUpdatingDevices,
    firstSeenPeriod: inventory.firstSeenPeriod,
    setFirstSeenPeriod: inventory.setFirstSeenPeriod,
    homeBoxLinkStatus: inventory.homeBoxLinkStatus,
    setHomeBoxLinkStatus: inventory.setHomeBoxLinkStatus,
    inventoryView: inventory.inventoryView, setInventoryView: inventory.setInventoryView,
    mainView: navigation.mainView,
    deviceOrdering: inventory.deviceOrdering,
    setDeviceOrdering: inventory.setDeviceOrdering,
    deviceLimit: inventory.deviceLimit,
    setDeviceLimit: inventory.setDeviceLimit,
    setDeviceOffset: inventory.setDeviceOffset,
    eventType, setEventType,
    devicePageId: navigation.devicePageId,
    changelogOpened: session.changelogOpened,
    setChangelogOpened: session.setChangelogOpened,
    latestVersion: session.latestVersion,
    logoutModalOpened: session.logoutModalOpened,
    logoutModal: session.logoutModal,
    loggingOut: session.loggingOut,
    usersModalOpened: session.usersModalOpened,
    usersModal: session.usersModal,
    scanDetailsOpened: session.scanDetailsOpened,
    scanDetailsModal: session.scanDetailsModal,
    mobileNavigationOpened: session.mobileNavigationOpened,
    mobileNavigation: session.mobileNavigation,
    deviceListRef: inventory.deviceListRef,
    roomOptions: inventory.roomOptions,
    networkRangeOptions: inventory.networkRangeOptions,
    canManageUsers: session.canManageUsers,
    canEditDevices: session.canEditDevices,
    canEditHomeMap: session.canEditHomeMap,
    canRunScans: session.canRunScans,
    scanIsActive, scanButtonLabel,
    hasVersionUpdate: session.hasVersionUpdate,
    hasVersionIndicator: session.hasVersionIndicator,
    versionTooltip: session.versionTooltip,
    displayTimeZone, showDnsActivity, showDockerInventory,
    showHomeBoxFilter: inventory.showHomeBoxFilter,
    showFirstSeen: inventory.showFirstSeen,
    openDevicePage: navigation.openDevicePage,
    navigateToView: navigation.navigateToView,
    openAttentionDevices: navigation.openAttentionDevices,
    openRecentChanges: navigation.openRecentChanges,
    returnFromDevicePage: navigation.returnFromDevicePage,
    returnAfterDeviceDeleted: navigation.returnAfterDeviceDeleted,
    loadData,
    loadMoreEventsData: activity.loadMoreEventsData,
    loadMoreScanRunsData: activity.loadMoreScanRunsData,
    loadMoreNotificationsData: activity.loadMoreNotificationsData,
    runScan,
    toggleBulkDevice: inventory.toggleBulkDevice,
    closeBulkEdit: inventory.closeBulkEdit,
    toggleAllBulkDevices: inventory.toggleAllBulkDevices,
    updateSelectedDevices,
    logout: session.logout,
    updateCurrentUser: session.updateCurrentUser,
    closeChangelog: session.closeChangelog,
  };
}
