import { useEffect, useMemo, useRef, useState } from 'react';
import { useDisclosure } from '@mantine/hooks';
import { apiRequest, clearStoredUser, storeUser } from '../api';
import { appendUniqueById, hasNextActivityPage } from '../utils/activity';
import { buildRoomOptions } from '../utils/device';
import { showErrorNotification, showServerNotification } from '../utils/notifications';
import { formatScanRange } from '../utils/scan';
import { useLiveClock } from './useLiveClock';
import { useVersionStatus } from './useVersionStatus';

const outsideNetworkRangeFilter = "outside";
const activityPageLimit = 500;
const dashboardStateStorageKey = "languard_dashboard_navigation_state";
const mainViewPaths = { dashboard: "/dashboard", devices: "/devices", "home-map": "/home-map", docker: "/docker", events: "/events", history: "/scan-history", notifications: "/notifications", dns: "/dns-activity", settings: "/settings" };

function retainAvailableNetworkRangeFilters(current, configuredRanges) {
  const available = current.filter((value) => value === outsideNetworkRangeFilter || configuredRanges.includes(value));
  return available.length === current.length ? current : available;
}

function mainViewPath(view) { return mainViewPaths[view] || mainViewPaths.dashboard; }
function mainViewFromPath(pathname) {
  const normalizedPath = pathname.replace(/\/+$/, "") || "/";
  if (normalizedPath === "/") return "dashboard";
  return Object.entries(mainViewPaths).find(([, path]) => path === normalizedPath)?.[0] || "dashboard";
}
function deviceIdFromPath(pathname) { return pathname.match(/^\/devices\/(\d+)\/?$/)?.[1] || ''; }

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
  const currentTime = useLiveClock();
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
  const [scanStatus, setScanStatus] = useState(null);
  const [scanVisibility, setScanVisibility] = useState(null);
  const [integrationStatus, setIntegrationStatus] = useState({});
  const [speedtestTrackerPayload, setSpeedtestTrackerPayload] = useState(null);
  const [accessCapabilities, setAccessCapabilities] = useState({
    can_edit_devices: Boolean(user?.is_staff || user?.is_superuser || user?.can_edit_devices),
    can_edit_home_map: Boolean(user?.is_staff || user?.is_superuser || user?.can_edit_home_map),
    can_run_scans: Boolean(user?.is_staff || user?.is_superuser || user?.can_run_scans),
  });
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
  const [networkRangeFilter, setNetworkRangeFilter] = useState([]);
  const [configuredNetworkRanges, setConfiguredNetworkRanges] = useState([]);
  const [configuredNetworkRangeLabels, setConfiguredNetworkRangeLabels] = useState({});
  const [bulkEditEnabled, setBulkEditEnabled] = useState(false);
  const [selectedDeviceIds, setSelectedDeviceIds] = useState([]);
  const [bulkUpdatingDevices, setBulkUpdatingDevices] = useState(false);
  const [firstSeenPeriod, setFirstSeenPeriod] = useState('');
  const [homeBoxLinkStatus, setHomeBoxLinkStatus] = useState('');
  const [inventoryView, setInventoryView] = useState('table');
  const [mainView, setMainView] = useState(initialView);
  const [deviceOrdering, setDeviceOrdering] = useState('');
  const [deviceLimit, setDeviceLimit] = useState(100);
  const [deviceOffset, setDeviceOffset] = useState(0);
  const [eventType, setEventType] = useState('');
  const [devicePageId, setDevicePageId] = useState(
    initialDeviceId ? String(initialDeviceId) : ''
  );
  const {
    changelogOpened,
    setChangelogOpened,
    closeChangelog,
    latestVersion,
    hasVersionUpdate,
    hasVersionIndicator,
    versionTooltip,
  } = useVersionStatus();
  const [logoutModalOpened, logoutModal] = useDisclosure(false);
  const [loggingOut, setLoggingOut] = useState(false);
  const [usersModalOpened, usersModal] = useDisclosure(false);
  const [scanDetailsOpened, scanDetailsModal] = useDisclosure(false);
  const [mobileNavigationOpened, mobileNavigation] = useDisclosure(false);
  const deviceListRef = useRef(null);
  const pendingDashboardScrollRef = useRef(null);
  const pendingDeviceListScrollRef = useRef(null);
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
      {
        value: outsideNetworkRangeFilter,
        label: 'Outside configured ranges',
      },
    ],
    [configuredNetworkRangeLabels, configuredNetworkRanges]
  );
  const canManageUsers = Boolean(user?.is_staff || user?.is_superuser);
  const canEditDevices = canManageUsers || Boolean(accessCapabilities.can_edit_devices);
  const canEditHomeMap = canManageUsers || Boolean(accessCapabilities.can_edit_home_map);
  const canRunScans = canManageUsers || Boolean(accessCapabilities.can_run_scans);
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
  const homeBoxStatusKnown = Boolean(integrationStatus?.homebox);
  const showHomeBoxFilter = Boolean(
    integrationStatus?.homebox?.enabled && integrationStatus?.homebox?.configured
  );
  const showFirstSeen = deviceOrdering === 'firstseen' || deviceOrdering === '-firstseen';

  useEffect(() => {
    setAccessCapabilities({
      can_edit_devices: Boolean(user?.is_staff || user?.is_superuser || user?.can_edit_devices),
      can_edit_home_map: Boolean(user?.is_staff || user?.is_superuser || user?.can_edit_home_map),
      can_run_scans: Boolean(user?.is_staff || user?.is_superuser || user?.can_run_scans),
    });
  }, [
    user?.is_staff,
    user?.is_superuser,
    user?.can_edit_devices,
    user?.can_edit_home_map,
    user?.can_run_scans,
  ]);

  useEffect(() => {
    if (!bulkEditEnabled) {
      return;
    }
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

  function storeDashboardNavigationState(overrides = {}) {
    window.sessionStorage.setItem(
      dashboardStateStorageKey,
      JSON.stringify({
        search,
        deviceStatus,
        networkRangeFilter,
        firstSeenPeriod,
        homeBoxLinkStatus,
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

  function storeCurrentHistoryState() {
    window.history.replaceState(
      {
        ...window.history.state,
        languardMainView: mainView,
        scrollY: window.scrollY,
        deviceListScrollTop: deviceListRef.current?.scrollTop || 0,
      },
      '',
      window.location.href
    );
  }

  function openDevicePage(device) {
    if (!device?.id) {
      return;
    }
    const returnScrollY = window.scrollY;
    const returnDeviceListScrollTop = deviceListRef.current?.scrollTop || 0;
    storeDashboardNavigationState();
    storeCurrentHistoryState();
    window.history.pushState(
      {
        languardDevicePage: true,
        languardReturnView: mainView,
        languardReturnScrollY: returnScrollY,
        languardReturnDeviceListScrollTop: returnDeviceListScrollTop,
      },
      '',
      `/devices/${device.id}`
    );
    setDevicePageId(String(device.id));
    window.setTimeout(() => window.scrollTo({ top: 0 }), 0);
  }

  function navigateToView(view) {
    const targetPath = mainViewPath(view);
    if (devicePageId) {
      storeDashboardNavigationState({ mainView: view, scrollY: 0 });
      window.history.pushState({ languardMainView: view, scrollY: 0 }, '', targetPath);
      setDevicePageId('');
      setMainView(view);
      window.setTimeout(() => window.scrollTo({ top: 0 }), 0);
      return;
    }
    if (mainView === view && window.location.pathname === targetPath) {
      return;
    }
    storeCurrentHistoryState();
    window.history.pushState({ languardMainView: view, scrollY: 0 }, '', targetPath);
    setMainView(view);
    window.setTimeout(() => window.scrollTo({ top: 0 }), 0);
  }

  function openAttentionDevices() {
    tableStateRef.current = {
      ...tableStateRef.current,
      search: '',
      deviceStatus: 'attention',
      networkRangeFilter: [],
      firstSeenPeriod: '',
      homeBoxLinkStatus: '',
      deviceOffset: 0,
    };
    setSearch('');
    setDeviceStatus('attention');
    setNetworkRangeFilter([]);
    setFirstSeenPeriod('');
    setHomeBoxLinkStatus('');
    setDeviceOffset(0);
    navigateToView('devices');
  }

  function openRecentChanges() {
    setEventType('');
    navigateToView('events');
  }

  function returnFromDevicePage() {
    if (window.history.state?.languardDevicePage) {
      window.history.back();
    } else {
      const targetPath = mainViewPath(mainView);
      window.history.replaceState({ languardMainView: mainView }, '', targetPath);
      setDevicePageId('');
    }
  }

  async function returnAfterDeviceDeleted() {
    await loadData({ quiet: true });

    const historyState = window.history.state || {};
    const openedFromApplication = Boolean(historyState.languardDevicePage);
    const returnView = openedFromApplication
      ? historyState.languardReturnView || mainView
      : 'devices';
    const returnScrollY = openedFromApplication
      ? Math.max(Number(historyState.languardReturnScrollY) || 0, 0)
      : 0;
    const returnDeviceListScrollTop = openedFromApplication
      ? Math.max(Number(historyState.languardReturnDeviceListScrollTop) || 0, 0)
      : 0;

    storeDashboardNavigationState({
      mainView: returnView,
      scrollY: returnScrollY,
      deviceListScrollTop: returnDeviceListScrollTop,
    });
    window.history.replaceState(
      {
        languardMainView: returnView,
        scrollY: returnScrollY,
        deviceListScrollTop: returnDeviceListScrollTop,
      },
      '',
      mainViewPath(returnView)
    );
    setDevicePageId('');
    setMainView(returnView);
  }

  useEffect(() => {
    const previousScrollRestoration = window.history.scrollRestoration;
    window.history.scrollRestoration = 'manual';

    const initialPathDeviceId = deviceIdFromPath(window.location.pathname);
    const pathView = mainViewFromPath(window.location.pathname);
    setDevicePageId((current) => current || initialPathDeviceId);
    if (!initialPathDeviceId) {
      setMainView(pathView);
      window.history.replaceState(
        { ...window.history.state, languardMainView: pathView },
        '',
        mainViewPath(pathView)
      );
    }

    function handlePopState(event) {
      const nextDeviceId = deviceIdFromPath(window.location.pathname);
      setDevicePageId(nextDeviceId);
      if (!nextDeviceId) {
        setMainView(mainViewFromPath(window.location.pathname));
        pendingDashboardScrollRef.current = Math.max(Number(event.state?.scrollY) || 0, 0);
        pendingDeviceListScrollRef.current = Math.max(
          Number(event.state?.deviceListScrollTop) || 0,
          0
        );
      }
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
    if (homeBoxStatusKnown && !showHomeBoxFilter) {
      setHomeBoxLinkStatus('');
    }
  }, [homeBoxStatusKnown, showHomeBoxFilter]);

  async function loadData({ quiet = false, notifyOnError = false, refreshIntegrations = false } = {}) {
    if (quiet) {
      setRefreshing(true);
    } else {
      setLoading(true);
    }
    setError('');

    try {
      const currentTableState = tableStateRef.current;
      const deviceFilterParams = {
        search: currentTableState.search,
        status:
          currentTableState.deviceStatus
            && !['attention', 'new', 'visitors', 'archived'].includes(
              currentTableState.deviceStatus
            )
            ? currentTableState.deviceStatus
            : undefined,
        needs_attention:
          currentTableState.deviceStatus === 'attention' ? 'true' : undefined,
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
      const mapDeviceParams = {
        limit: 100,
        ordering: 'ip',
      };
      const dashboardEventParams = {
        limit: 8,
      };
      const roleDeviceRequest = currentTableState.inventoryView === 'roles'
        ? apiRequest('device/', {
          params: {
            ...deviceFilterParams,
            limit: 100,
            offset: 0,
            ordering: 'name',
          },
        })
        : Promise.resolve(null);

      const settingsRequest = canManageUsers
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
      ] =
        await Promise.all([
          apiRequest('device/', { params: deviceParams }),
          apiRequest('device/', { params: mapDeviceParams }),
          roleDeviceRequest,
          apiRequest('scan/status/'),
          apiRequest('events/', { params: dashboardEventParams }),
          settingsRequest,
          apiRequest('integrations/speedtest-tracker/latest/', {
            params: { refresh: refreshIntegrations ? 'true' : undefined },
          }).catch(() => null),
        ]);

      setDevices(deviceData.data || []);
      setMapDevices(mapDeviceData.data || []);
      if (roleDeviceData) {
        setRoleDevices(roleDeviceData.data || []);
        setRoleDeviceCount(roleDeviceData.pagination?.count || 0);
      }
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
      setIntegrationStatus(statusData.integrations || {});
      const nextNetworkRanges = Array.isArray(statusData.network_ranges)
        ? statusData.network_ranges
        : [];
      setConfiguredNetworkRanges(nextNetworkRanges);
      setConfiguredNetworkRangeLabels(statusData.network_range_labels || {});
      setNetworkRangeFilter((current) =>
        retainAvailableNetworkRangeFilters(current, nextNetworkRanges)
      );
      setSpeedtestTrackerPayload(speedtestData || null);
      setAccessCapabilities(statusData.permissions || {});
      if (statusData.time_zone) {
        setDashboardTimeZone(statusData.time_zone);
      }
      setDashboardEvents(dashboardEventData.data || []);
      if (settingsData.data) {
        setAppSettings(settingsData.data);
      }
    } catch (err) {
      setError(quiet ? '' : err.message);
      if (notifyOnError) {
        showErrorNotification(err);
      } else if (quiet) {
        showErrorNotification(err);
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

  async function loadScanData({ notifyOnError = false } = {}) {
    try {
      const statusData = await apiRequest('scan/status/');
      setScanStatus(statusData.data || statusData.active_scan || null);
      setScanVisibility(statusData.visibility || null);
      setIntegrationStatus(statusData.integrations || {});
      const nextNetworkRanges = Array.isArray(statusData.network_ranges)
        ? statusData.network_ranges
        : [];
      setConfiguredNetworkRanges(nextNetworkRanges);
      setConfiguredNetworkRangeLabels(statusData.network_range_labels || {});
      setNetworkRangeFilter((current) =>
        retainAvailableNetworkRangeFilters(current, nextNetworkRanges)
      );
      setAccessCapabilities(statusData.permissions || {});
      if (statusData.time_zone) {
        setDashboardTimeZone(statusData.time_zone);
      }
    } catch (err) {
      if (notifyOnError) {
        showErrorNotification(err);
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
        showErrorNotification(err);
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
        showErrorNotification(err);
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
        showErrorNotification(err);
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
      setNetworkRangeFilter(
        Array.isArray(state.networkRangeFilter) ? state.networkRangeFilter : []
      );
      setFirstSeenPeriod(state.firstSeenPeriod || '');
      setHomeBoxLinkStatus(state.homeBoxLinkStatus || '');
      setInventoryView(state.inventoryView || 'table');
      setMainView(mainViewFromPath(window.location.pathname));
      setDeviceOrdering(state.deviceOrdering || '');
      setEventType(state.eventType || '');
      tableStateRef.current = {
        ...tableStateRef.current,
        search: state.search || '',
        deviceStatus: state.deviceStatus || '',
        networkRangeFilter: Array.isArray(state.networkRangeFilter)
          ? state.networkRangeFilter
          : [],
        firstSeenPeriod: state.firstSeenPeriod || '',
        homeBoxLinkStatus: state.homeBoxLinkStatus || '',
        deviceOrdering: state.deviceOrdering || '',
        inventoryView: state.inventoryView || 'table',
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
  }, [
    search,
    deviceStatus,
    networkRangeFilter,
    firstSeenPeriod,
    homeBoxLinkStatus,
    inventoryView,
    deviceOrdering,
    deviceLimit,
    deviceOffset,
  ]);

  async function runScan() {
    if (scanIsActive || refreshing) {
      return;
    }
    setRefreshing(true);
    setError('');
    try {
      const payload = await apiRequest('scan/', {
        method: 'POST',
        body: {},
      });
      await loadData({ quiet: true });
      showServerNotification(payload);
    } catch (err) {
      setError(err.message);
      showErrorNotification(err);
    } finally {
      setRefreshing(false);
    }
  }

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

  async function updateSelectedDevices(classification) {
    if (!selectedDeviceIds.length) {
      return;
    }
    setBulkUpdatingDevices(true);
    try {
      const payload = await apiRequest('devices/bulk-update/', {
        method: 'POST',
        body:
          classification === 'attention'
            ? {
                ids: selectedDeviceIds,
                acknowledge_attention: true,
              }
            : {
                ids: selectedDeviceIds,
                known: true,
                is_visitor: classification === 'visitor',
              },
      });
      closeBulkEdit();
      await loadData({ quiet: true });
      showServerNotification(payload);
    } catch (err) {
      showErrorNotification(err);
    } finally {
      setBulkUpdatingDevices(false);
    }
  }

  async function logout() {
    setLoggingOut(true);
    try {
      await apiRequest('logout/', { method: 'POST' });
      clearStoredUser();
      onLogout();
    } catch (err) {
      showErrorNotification(err);
    } finally {
      setLoggingOut(false);
    }
  }

  function updateCurrentUser(nextUser) {
    if (!nextUser) {
      onLogout();
      return;
    }
    storeUser(nextUser);
    onUserUpdated(nextUser);
  }

  return {
    loading,
    refreshing,
    error,
    setError,
    currentTime,
    filteredDevices,
    mapDevices,
    roleDevices,
    roleDeviceCount,
    devicePagination,
    counters,
    scanStatus,
    scanVisibility,
    speedtestTrackerPayload,
    scanRuns,
    scanRunPagination,
    dashboardEvents,
    events,
    eventPagination,
    notifications,
    notificationPagination,
    activityLoadingMore,
    appSettings,
    search,
    setSearch,
    deviceStatus,
    setDeviceStatus,
    networkRangeFilter,
    setNetworkRangeFilter,
    configuredNetworkRanges,
    configuredNetworkRangeLabels,
    bulkEditEnabled,
    setBulkEditEnabled,
    selectedDeviceIds,
    bulkUpdatingDevices,
    firstSeenPeriod,
    setFirstSeenPeriod,
    homeBoxLinkStatus,
    setHomeBoxLinkStatus,
    inventoryView,
    setInventoryView,
    mainView,
    deviceOrdering,
    setDeviceOrdering,
    deviceLimit,
    setDeviceLimit,
    setDeviceOffset,
    eventType,
    setEventType,
    devicePageId,
    changelogOpened,
    setChangelogOpened,
    latestVersion,
    logoutModalOpened,
    logoutModal,
    loggingOut,
    usersModalOpened,
    usersModal,
    scanDetailsOpened,
    scanDetailsModal,
    mobileNavigationOpened,
    mobileNavigation,
    deviceListRef,
    roomOptions,
    networkRangeOptions,
    canManageUsers,
    canEditDevices,
    canEditHomeMap,
    canRunScans,
    scanIsActive,
    scanButtonLabel,
    hasVersionUpdate,
    hasVersionIndicator,
    versionTooltip,
    displayTimeZone,
    showDnsActivity,
    showDockerInventory,
    showHomeBoxFilter,
    showFirstSeen,
    openDevicePage,
    navigateToView,
    openAttentionDevices,
    openRecentChanges,
    returnFromDevicePage,
    returnAfterDeviceDeleted,
    loadData,
    loadMoreEventsData,
    loadMoreScanRunsData,
    loadMoreNotificationsData,
    runScan,
    toggleBulkDevice,
    closeBulkEdit,
    toggleAllBulkDevices,
    updateSelectedDevices,
    logout,
    updateCurrentUser,
    closeChangelog,
  };
}
