import { useEffect, useRef, useState } from 'react';

const dashboardStateStorageKey = 'languard_dashboard_navigation_state';
const mainViewPaths = {
  dashboard: '/dashboard',
  devices: '/devices',
  'home-map': '/home-map',
  docker: '/docker',
  events: '/events',
  history: '/scan-history',
  notifications: '/notifications',
  dns: '/dns-activity',
  settings: '/settings',
};

function mainViewPath(view) {
  return mainViewPaths[view] || mainViewPaths.dashboard;
}

function mainViewFromPath(pathname) {
  const normalizedPath = pathname.replace(/\/+$/, '') || '/';
  if (normalizedPath === '/') return 'dashboard';
  return Object.entries(mainViewPaths).find(([, path]) => path === normalizedPath)?.[0]
    || 'dashboard';
}

function deviceIdFromPath(pathname) {
  return pathname.match(/^\/devices\/(\d+)\/?$/)?.[1] || '';
}

export function useLanGuardNavigation({
  initialDeviceId,
  initialView,
  loading,
  devicesLength,
  inventory,
  eventType,
  setEventType,
  reloadData,
}) {
  const [mainView, setMainView] = useState(initialView);
  const [devicePageId, setDevicePageId] = useState(
    initialDeviceId ? String(initialDeviceId) : ''
  );
  const pendingDashboardScrollRef = useRef(null);
  const pendingDeviceListScrollRef = useRef(null);
  const {
    search, setSearch, deviceStatus, setDeviceStatus,
    networkRangeFilter, setNetworkRangeFilter,
    firstSeenPeriod, setFirstSeenPeriod,
    homeBoxLinkStatus, setHomeBoxLinkStatus,
    inventoryView, setInventoryView,
    deviceOrdering, setDeviceOrdering,
    setDeviceOffset, deviceListRef, tableStateRef,
  } = inventory;

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
    if (!device?.id) return;
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
    if (mainView === view && window.location.pathname === targetPath) return;
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
    await reloadData({ quiet: true });
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
      { languardMainView: returnView, scrollY: returnScrollY, deviceListScrollTop: returnDeviceListScrollTop },
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
    if (devicePageId) return;
    const stored = window.sessionStorage.getItem(dashboardStateStorageKey);
    if (!stored) return;
    try {
      const state = JSON.parse(stored);
      const restoredNetworkRanges = Array.isArray(state.networkRangeFilter)
        ? state.networkRangeFilter
        : [];
      setSearch(state.search || '');
      setDeviceStatus(state.deviceStatus || '');
      setNetworkRangeFilter(restoredNetworkRanges);
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
        networkRangeFilter: restoredNetworkRanges,
        firstSeenPeriod: state.firstSeenPeriod || '',
        homeBoxLinkStatus: state.homeBoxLinkStatus || '',
        deviceOrdering: state.deviceOrdering || '',
        inventoryView: state.inventoryView || 'table',
      };
      pendingDashboardScrollRef.current = Math.max(Number(state.scrollY) || 0, 0);
      pendingDeviceListScrollRef.current = Math.max(Number(state.deviceListScrollTop) || 0, 0);
    } catch {
      window.sessionStorage.removeItem(dashboardStateStorageKey);
    }
  }, [devicePageId]);

  useEffect(() => {
    if (devicePageId || loading || pendingDashboardScrollRef.current === null) return undefined;
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
    const fallbackTimers = [150, 400, 800].map((delay) => window.setTimeout(
      () => window.scrollTo({ top: scrollTop, behavior: 'auto' }),
      delay
    ));
    return () => {
      if (animationFrame !== null) window.cancelAnimationFrame(animationFrame);
      fallbackTimers.forEach((timer) => window.clearTimeout(timer));
    };
  }, [devicePageId, devicesLength, loading, mainView]);

  useEffect(() => {
    if (
      devicePageId || loading || inventoryView !== 'table'
      || pendingDeviceListScrollRef.current === null
    ) return undefined;
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
        if (Math.abs(list.scrollTop - scrollTop) <= 1) return;
      }
      if (attempts < 12) animationFrame = window.requestAnimationFrame(restoreScroll);
    };
    animationFrame = window.requestAnimationFrame(restoreScroll);
    const fallbackTimers = [150, 400, 800].map((delay) => window.setTimeout(() => {
      if (deviceListRef.current) deviceListRef.current.scrollTop = scrollTop;
    }, delay));
    return () => {
      if (animationFrame !== null) window.cancelAnimationFrame(animationFrame);
      fallbackTimers.forEach((timer) => window.clearTimeout(timer));
    };
  }, [devicePageId, devicesLength, inventoryView, loading, mainView]);

  return {
    mainView, devicePageId, openDevicePage, navigateToView, openAttentionDevices,
    openRecentChanges, returnFromDevicePage, returnAfterDeviceDeleted,
  };
}
