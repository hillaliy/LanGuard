import { ActionIcon, Alert, Box, Burger, Button, Container, Divider, Drawer, Group, Image, LoadingOverlay, Modal, Stack, Text, Title, Tooltip, UnstyledButton } from '@mantine/core';
import { IconAlertCircle, IconBell, IconBrandDocker, IconBrandGithub, IconClock, IconDeviceDesktop, IconHistory, IconLayoutDashboard, IconLogout, IconRefresh, IconSettings, IconShieldLock, IconSmartHome, IconWorldSearch } from '@tabler/icons-react';
import { getAdminUrl } from "../api";
import { UserManagementModal } from "../auth/AuthViews";
import { userDisplayName, userInitials } from "../auth/user";
import DashboardView, { ScanDetailsContent } from "../dashboard/DashboardView";
import DNSActivityView from "../dns-activity/DNSActivityView";
import DeviceDetailsView from "../devices/DeviceDetailsView";
import DevicesView from "../devices/DevicesView";
import DockerView from "../docker/DockerView";
import EventsView from "../events/EventsView";
import HomeMapView from "../home-map/HomeMapView";
import { useLanGuardController } from "../hooks/useLanGuardController";
import NotificationsView from "../notifications/NotificationsView";
import ScanHistoryView from "../scan-history/ScanHistoryView";
import SettingsView from "../settings/SettingsView";
import { showErrorNotification, showServerNotification } from "../utils/notifications";
import { APP_VERSION, CHANGELOG_ENTRIES } from "../version";
import { ColorSchemeControl, formatTopbarDate, formatTopbarTime } from "./ShellControls";

function PrimaryNavigation({
  mainView,
  devicePageId,
  showDnsActivity,
  showDockerInventory,
  canManageUsers,
  onNavigate,
  onNavigateComplete,
  mobile = false,
}) {
  function navigate(view) {
    onNavigate(view);
    onNavigateComplete?.();
  }

  return (
    <Stack className={`sidebar-nav${mobile ? ' mobile-sidebar-nav' : ''}`} gap={6}>
      <Button
        className="sidebar-nav-button"
        variant={!devicePageId && mainView === 'dashboard' ? 'filled' : 'subtle'}
        justify="flex-start"
        leftSection={<IconLayoutDashboard size={18} />}
        onClick={() => navigate('dashboard')}
        fullWidth
      >
        Dashboard
      </Button>
      <Button
        className="sidebar-nav-button"
        variant={!devicePageId && mainView === 'devices' ? 'filled' : 'subtle'}
        justify="flex-start"
        leftSection={<IconDeviceDesktop size={18} />}
        onClick={() => navigate('devices')}
        fullWidth
      >
        Devices
      </Button>
      <Button
        className="sidebar-nav-button"
        variant={!devicePageId && mainView === 'home-map' ? 'filled' : 'subtle'}
        justify="flex-start"
        leftSection={<IconSmartHome size={18} />}
        onClick={() => navigate('home-map')}
        fullWidth
      >
        Home Map
      </Button>
      {showDockerInventory && (
        <Button
          className="sidebar-nav-button"
          variant={!devicePageId && mainView === 'docker' ? 'filled' : 'subtle'}
          justify="flex-start"
          leftSection={<IconBrandDocker size={18} />}
          onClick={() => navigate('docker')}
          fullWidth
        >
          Docker
        </Button>
      )}
      <Divider my={4} />
      <Button
        className="sidebar-nav-button"
        variant={!devicePageId && mainView === 'events' ? 'filled' : 'subtle'}
        justify="flex-start"
        leftSection={<IconBell size={18} />}
        onClick={() => navigate('events')}
        fullWidth
      >
        Events
      </Button>
      <Button
        className="sidebar-nav-button"
        variant={!devicePageId && mainView === 'history' ? 'filled' : 'subtle'}
        justify="flex-start"
        leftSection={<IconHistory size={18} />}
        onClick={() => navigate('history')}
        fullWidth
      >
        Scan history
      </Button>
      <Button
        className="sidebar-nav-button"
        variant={!devicePageId && mainView === 'notifications' ? 'filled' : 'subtle'}
        justify="flex-start"
        leftSection={<IconBell size={18} />}
        onClick={() => navigate('notifications')}
        fullWidth
      >
        Notifications
      </Button>
      {showDnsActivity && (
        <Button
          className="sidebar-nav-button"
          variant={!devicePageId && mainView === 'dns' ? 'filled' : 'subtle'}
          justify="flex-start"
          leftSection={<IconWorldSearch size={18} />}
          onClick={() => navigate('dns')}
          fullWidth
        >
          DNS Activity
        </Button>
      )}
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
            onClick={onNavigateComplete}
            fullWidth
          >
            Admin site
          </Button>
          <Button
            className="sidebar-nav-button"
            variant={!devicePageId && mainView === 'settings' ? 'filled' : 'subtle'}
            justify="flex-start"
            leftSection={<IconSettings size={18} />}
            onClick={() => navigate('settings')}
            fullWidth
          >
            Settings
          </Button>
        </>
      )}
    </Stack>
  );
}

export default function AppShell({
  user,
  onLogout,
  onUserUpdated,
  initialDeviceId = null,
  initialView = 'dashboard',
}) {
  const {
    loading, refreshing, error, setError, currentTime,
    filteredDevices, mapDevices, roleDevices, roleDeviceCount, devicePagination,
    counters, scanStatus, scanVisibility, speedtestTrackerPayload,
    scanRuns, scanRunPagination, dashboardEvents, events, eventPagination,
    notifications, notificationPagination, activityLoadingMore, appSettings,
    search, setSearch, deviceStatus, setDeviceStatus,
    networkRangeFilter, setNetworkRangeFilter,
    configuredNetworkRanges, configuredNetworkRangeLabels,
    bulkEditEnabled, setBulkEditEnabled, selectedDeviceIds, bulkUpdatingDevices,
    firstSeenPeriod, setFirstSeenPeriod, homeBoxLinkStatus, setHomeBoxLinkStatus,
    inventoryView, setInventoryView, mainView,
    deviceOrdering, setDeviceOrdering, deviceLimit, setDeviceLimit, setDeviceOffset,
    eventType, setEventType, devicePageId,
    changelogOpened, setChangelogOpened, latestVersion,
    logoutModalOpened, logoutModal, loggingOut,
    usersModalOpened, usersModal,
    scanDetailsOpened, scanDetailsModal,
    mobileNavigationOpened, mobileNavigation,
    deviceListRef, roomOptions, networkRangeOptions,
    canManageUsers, canEditDevices, canEditHomeMap, canRunScans,
    scanIsActive, scanButtonLabel,
    hasVersionUpdate, hasVersionIndicator, versionTooltip,
    displayTimeZone, showDnsActivity, showDockerInventory,
    showHomeBoxFilter, showFirstSeen,
    openDevicePage, navigateToView, openAttentionDevices, openRecentChanges,
    returnFromDevicePage, returnAfterDeviceDeleted,
    loadData, loadMoreEventsData, loadMoreScanRunsData, loadMoreNotificationsData,
    runScan, toggleBulkDevice, closeBulkEdit, toggleAllBulkDevices,
    updateSelectedDevices, logout, updateCurrentUser, closeChangelog,
  } = useLanGuardController({
    user,
    onLogout,
    onUserUpdated,
    initialDeviceId,
    initialView,
  });

  return (
    <main className="shell">
      <header className="topbar">
        <Container size="xl" py="sm">
          <Group justify="space-between">
            <Group className="topbar-brand" gap="sm" wrap="nowrap">
              <Burger
                className="mobile-topbar-menu"
                opened={mobileNavigationOpened}
                onClick={mobileNavigation.toggle}
                size="sm"
                aria-label={mobileNavigationOpened ? 'Close navigation' : 'Open navigation'}
              />
              <Image src="/logo.png" alt="LanGuard" w={42} h={42} radius="sm" />
              <Box className="topbar-brand-details">
                <Group className="topbar-brand-title" gap="xs">
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
                  {process.env.NODE_ENV === 'production' && (
                    <Tooltip label="Documentation">
                      <ActionIcon
                        component="a"
                        href="https://hillaliy.github.io/LanGuard/"
                        target="_blank"
                        rel="noreferrer"
                        variant="light"
                        color="gray"
                        size="sm"
                        aria-label="LanGuard documentation"
                      >
                        <Image
                          src="/brands/docusaurus.svg"
                          alt=""
                          w={17}
                          h={17}
                        />
                      </ActionIcon>
                    </Tooltip>
                  )}
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
                  <Text size="xs" c="var(--muted-text)" lh={1.1}>
                    {formatTopbarDate(currentTime, displayTimeZone)}
                  </Text>
                  <Text size="sm" fw={700} lh={1.15}>
                    {formatTopbarTime(currentTime, displayTimeZone)}
                  </Text>
                </Box>
              </Group>
              <ColorSchemeControl />
              {canRunScans && <Button
                size="sm"
                leftSection={<IconRefresh size={17} />}
                onClick={runScan}
                loading={refreshing}
                disabled={scanIsActive}
                className="topbar-scan-button"
              >
                {scanButtonLabel}
              </Button>}
              <Tooltip label="Refresh">
                <ActionIcon
                  variant="light"
                  size="lg"
                  onClick={() => loadData({ quiet: true, notifyOnError: true, refreshIntegrations: true })}
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
        <div className="mobile-page-title">
          <Title order={2}>
            {devicePageId
              ? 'Device details'
              : {
                  dashboard: 'Dashboard',
                  devices: 'Devices',
                  'home-map': 'Home Map',
                  docker: 'Docker',
                  events: 'Events',
                  history: 'Scan history',
                  notifications: 'Notifications',
                  dns: 'DNS Activity',
                  settings: 'Settings',
                }[mainView] || 'Navigation'}
          </Title>
        </div>

        <Drawer
          opened={mobileNavigationOpened}
          onClose={mobileNavigation.close}
          title="Navigation"
          size="min(82vw, 320px)"
          className="mobile-navigation-drawer"
        >
          <PrimaryNavigation
            mainView={mainView}
            devicePageId={devicePageId}
            showDnsActivity={showDnsActivity}
            showDockerInventory={showDockerInventory}
            canManageUsers={canManageUsers}
            onNavigate={navigateToView}
            onNavigateComplete={mobileNavigation.close}
            mobile
          />
        </Drawer>

        <aside className="app-sidebar" aria-label="Primary navigation">
          <PrimaryNavigation
            mainView={mainView}
            devicePageId={devicePageId}
            showDnsActivity={showDnsActivity}
            showDockerInventory={showDockerInventory}
            canManageUsers={canManageUsers}
            onNavigate={navigateToView}
          />
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
<DeviceDetailsView
              deviceId={devicePageId}
              onBack={returnFromDevicePage}
              onSaved={async () => loadData({ quiet: true })}
              onDeleted={returnAfterDeviceDeleted}
              timeZone={displayTimeZone}
              roomOptions={roomOptions}
              dnsActivityEnabled={showDnsActivity}
              canEditDevices={canEditDevices}
              canRunScans={canRunScans}
              onError={showErrorNotification}
              onSuccess={showServerNotification}
            />
          ) : mainView === 'home-map' ? (
            <HomeMapView
              devices={mapDevices}
              onSelectDevice={openDevicePage}
              canEditLayout={canEditHomeMap}
              onError={showErrorNotification}
              onSuccess={showServerNotification}
            />
          ) : mainView === 'docker' ? (
            <DockerView
              timeZone={displayTimeZone}
              canManageUsers={canManageUsers}
              onSelectDevice={openDevicePage}
              onError={showErrorNotification}
            />
          ) : mainView === 'settings' && canManageUsers ? (
            <SettingsView
              onSaved={async () => {
                await loadData({ quiet: true });
              }}
            />
          ) : mainView === 'events' ? (
            <EventsView
              events={events}
              eventType={eventType}
              setEventType={setEventType}
              timeZone={displayTimeZone}
              pagination={eventPagination}
              loadingMore={activityLoadingMore.events}
              onLoadMore={loadMoreEventsData}
              onSelectDevice={openDevicePage}
              onError={showErrorNotification}
            />
          ) : mainView === 'history' ? (
            <ScanHistoryView
              scanRuns={scanRuns}
              timeZone={displayTimeZone}
              pagination={scanRunPagination}
              loadingMore={activityLoadingMore.scanRuns}
              onLoadMore={loadMoreScanRunsData}
            />
          ) : mainView === 'notifications' ? (
            <NotificationsView
              notifications={notifications}
              timeZone={displayTimeZone}
              pagination={notificationPagination}
              loadingMore={activityLoadingMore.notifications}
              onLoadMore={loadMoreNotificationsData}
            />
          ) : mainView === 'dns' ? (
            <DNSActivityView
              timeZone={displayTimeZone}
              onSelectDevice={openDevicePage}
              onError={showErrorNotification}
            />
          ) : mainView === 'dashboard' ? (
            <DashboardView
              counters={counters}
              appSettings={appSettings}
              networkRanges={configuredNetworkRanges}
              networkRangeLabels={configuredNetworkRangeLabels}
              scanStatus={scanStatus}
              scanVisibility={scanVisibility}
              timeZone={displayTimeZone}
              onOpenScanDetails={scanDetailsModal.open}
              speedtestTrackerPayload={speedtestTrackerPayload}
              events={dashboardEvents}
              devices={mapDevices}
              onSelectDevice={openDevicePage}
              onOpenAttentionDevices={openAttentionDevices}
              onOpenRecentChanges={openRecentChanges}
              onError={showErrorNotification}
            />
          ) : (
            <DevicesView
            devices={filteredDevices}
            roleDevices={roleDevices}
            roleDeviceCount={roleDeviceCount}
            inventoryView={inventoryView}
            onInventoryViewChange={setInventoryView}
            filters={{
              deviceStatus,
              onDeviceStatusChange: setDeviceStatus,
              networkRangeOptions,
              networkRangeFilter,
              onNetworkRangeFilterChange: setNetworkRangeFilter,
              firstSeenPeriod,
              onFirstSeenPeriodChange: setFirstSeenPeriod,
              homeBoxLinkStatus,
              onHomeBoxLinkStatusChange: setHomeBoxLinkStatus,
              search,
              onSearchChange: setSearch,
            }}
            bulkEdit={{
              enabled: bulkEditEnabled,
              selectedDeviceIds,
              updating: bulkUpdatingDevices,
              canEditDevices,
              onToggleDevice: toggleBulkDevice,
              onToggleAll: toggleAllBulkDevices,
              onClose: closeBulkEdit,
              onUpdate: updateSelectedDevices,
              onEnable: () => setBulkEditEnabled(true),
            }}
            ordering={{
              value: deviceOrdering,
              onChange: setDeviceOrdering,
            }}
            pagination={{
              data: devicePagination,
              limit: deviceLimit,
              onLimitChange: setDeviceLimit,
              onOffsetChange: setDeviceOffset,
              loading,
              refreshing,
            }}
            showHomeBoxFilter={showHomeBoxFilter}
            showFirstSeen={showFirstSeen}
            timeZone={displayTimeZone}
            listRef={deviceListRef}
            onSelectDevice={openDevicePage}
            />
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
      <Modal
        opened={logoutModalOpened}
        onClose={logoutModal.close}
        title="Log off"
        centered
        closeOnClickOutside={!loggingOut}
        closeOnEscape={!loggingOut}
        withCloseButton={!loggingOut}
      >
        <Stack>
          <Text>Are you sure you want to log off?</Text>
          <Group justify="flex-end">
            <Button variant="default" onClick={logoutModal.close} disabled={loggingOut}>
              Cancel
            </Button>
            <Button
              color="red"
              leftSection={<IconLogout size={18} />}
              onClick={logout}
              loading={loggingOut}
            >
              Log off
            </Button>
          </Group>
        </Stack>
      </Modal>
      <Modal
        opened={changelogOpened}
        onClose={closeChangelog}
        title={`What's new in v${APP_VERSION}`}
        centered
        size="90rem"
      >
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
              <Stack gap={4}>
                {entry.items.map((item) => (
                  <Group key={item} gap="xs" align="flex-start" wrap="nowrap">
                    <span className="changelog-bullet" />
                    <Text size="xs">{item}</Text>
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
