import DashboardView from '../dashboard/DashboardView';
import DNSActivityView from '../dns-activity/DNSActivityView';
import DeviceDetailsView from '../devices/DeviceDetailsView';
import DevicesView from '../devices/DevicesView';
import DockerView from '../docker/DockerView';
import EventsView from '../events/EventsView';
import HomeMapView from '../home-map/HomeMapView';
import NotificationsView from '../notifications/NotificationsView';
import ScanHistoryView from '../scan-history/ScanHistoryView';
import SettingsView from '../settings/SettingsView';
import { showErrorNotification, showServerNotification } from '../utils/notifications';

export default function AppRouteContent({ controller }) {
  const c = controller;

  if (c.devicePageId) {
    return (
      <DeviceDetailsView
        deviceId={c.devicePageId}
        onBack={c.returnFromDevicePage}
        onSaved={async () => c.loadData({ quiet: true })}
        onDeleted={c.returnAfterDeviceDeleted}
        timeZone={c.displayTimeZone}
        roomOptions={c.roomOptions}
        dnsActivityEnabled={c.showDnsActivity}
        canEditDevices={c.canEditDevices}
        canRunScans={c.canRunScans}
        onError={showErrorNotification}
        onSuccess={showServerNotification}
      />
    );
  }

  if (c.mainView === 'home-map') {
    return (
      <HomeMapView
        devices={c.mapDevices}
        onSelectDevice={c.openDevicePage}
        canEditLayout={c.canEditHomeMap}
        onError={showErrorNotification}
        onSuccess={showServerNotification}
      />
    );
  }

  if (c.mainView === 'docker') {
    return (
      <DockerView
        timeZone={c.displayTimeZone}
        canManageUsers={c.canManageUsers}
        onSelectDevice={c.openDevicePage}
        onError={showErrorNotification}
      />
    );
  }

  if (c.mainView === 'settings' && c.canManageUsers) {
    return <SettingsView onSaved={async () => c.loadData({ quiet: true })} />;
  }

  if (c.mainView === 'events') {
    return (
      <EventsView
        events={c.events}
        eventType={c.eventType}
        setEventType={c.setEventType}
        timeZone={c.displayTimeZone}
        pagination={c.eventPagination}
        loadingMore={c.activityLoadingMore.events}
        onLoadMore={c.loadMoreEventsData}
        onSelectDevice={c.openDevicePage}
        onError={showErrorNotification}
      />
    );
  }

  if (c.mainView === 'history') {
    return (
      <ScanHistoryView
        scanRuns={c.scanRuns}
        timeZone={c.displayTimeZone}
        pagination={c.scanRunPagination}
        loadingMore={c.activityLoadingMore.scanRuns}
        onLoadMore={c.loadMoreScanRunsData}
      />
    );
  }

  if (c.mainView === 'notifications') {
    return (
      <NotificationsView
        notifications={c.notifications}
        timeZone={c.displayTimeZone}
        pagination={c.notificationPagination}
        loadingMore={c.activityLoadingMore.notifications}
        onLoadMore={c.loadMoreNotificationsData}
      />
    );
  }

  if (c.mainView === 'dns') {
    return (
      <DNSActivityView
        timeZone={c.displayTimeZone}
        onSelectDevice={c.openDevicePage}
        onError={showErrorNotification}
      />
    );
  }

  if (c.mainView === 'dashboard') {
    return (
      <DashboardView
        counters={c.counters}
        appSettings={c.appSettings}
        networkRanges={c.configuredNetworkRanges}
        networkRangeLabels={c.configuredNetworkRangeLabels}
        scanStatus={c.scanStatus}
        scanVisibility={c.scanVisibility}
        timeZone={c.displayTimeZone}
        onOpenScanDetails={c.scanDetailsModal.open}
        speedtestTrackerPayload={c.speedtestTrackerPayload}
        events={c.dashboardEvents}
        devices={c.mapDevices}
        onSelectDevice={c.openDevicePage}
        onOpenAttentionDevices={c.openAttentionDevices}
        onOpenRecentChanges={c.openRecentChanges}
        onError={showErrorNotification}
      />
    );
  }

  return (
    <DevicesView
      devices={c.filteredDevices}
      roleDevices={c.roleDevices}
      roleDeviceCount={c.roleDeviceCount}
      inventoryView={c.inventoryView}
      onInventoryViewChange={c.setInventoryView}
      filters={{
        deviceStatus: c.deviceStatus,
        onDeviceStatusChange: c.setDeviceStatus,
        networkRangeOptions: c.networkRangeOptions,
        networkRangeFilter: c.networkRangeFilter,
        onNetworkRangeFilterChange: c.setNetworkRangeFilter,
        firstSeenPeriod: c.firstSeenPeriod,
        onFirstSeenPeriodChange: c.setFirstSeenPeriod,
        homeBoxLinkStatus: c.homeBoxLinkStatus,
        onHomeBoxLinkStatusChange: c.setHomeBoxLinkStatus,
        search: c.search,
        onSearchChange: c.setSearch,
      }}
      bulkEdit={{
        enabled: c.bulkEditEnabled,
        selectedDeviceIds: c.selectedDeviceIds,
        updating: c.bulkUpdatingDevices,
        canEditDevices: c.canEditDevices,
        onToggleDevice: c.toggleBulkDevice,
        onToggleAll: c.toggleAllBulkDevices,
        onClose: c.closeBulkEdit,
        onUpdate: c.updateSelectedDevices,
        onEnable: () => c.setBulkEditEnabled(true),
      }}
      ordering={{ value: c.deviceOrdering, onChange: c.setDeviceOrdering }}
      pagination={{
        data: c.devicePagination,
        limit: c.deviceLimit,
        onLimitChange: c.setDeviceLimit,
        onOffsetChange: c.setDeviceOffset,
        loading: c.loading,
        refreshing: c.refreshing,
      }}
      showHomeBoxFilter={c.showHomeBoxFilter}
      showFirstSeen={c.showFirstSeen}
      timeZone={c.displayTimeZone}
      listRef={c.deviceListRef}
      onSelectDevice={c.openDevicePage}
    />
  );
}
