'use client';

import { useEffect, useRef, useState } from 'react';
import {
  Alert,
  LoadingOverlay,
  Paper,
  Stack,
  Tabs,
} from '@mantine/core';
import { useDisclosure } from '@mantine/hooks';
import {
  IconAlertCircle,
  IconHistory,
  IconNetwork,
  IconWorldSearch,
} from '@tabler/icons-react';

import { apiRequest } from '../api';
import {
  appendUniqueById,
  hasNextActivityPage,
} from '../utils/activity';
import {
  deviceStatus,
  externalUrlUsesIPv4,
  resolveExternalUrl,
  validExternalUrl,
} from '../utils/device';
import DeviceDetailsHeader from './DeviceDetailsHeader';
import DeviceHistoryTab from './DeviceHistoryTab';
import DeviceDnsActivityTab from './DeviceDnsActivityTab';
import DeviceDetailsModals from './DeviceDetailsModals';
import DeviceOverviewTab from './DeviceOverviewTab';

export default function DeviceDetailsView({
  deviceId,
  onBack,
  onSaved,
  onDeleted,
  timeZone,
  roomOptions,
  dnsActivityEnabled,
  canEditDevices,
  canRunScans,
  onError,
  onSuccess,
}) {
  const [device, setDevice] = useState(null);
  const [events, setEvents] = useState([]);
  const [eventPagination, setEventPagination] = useState(null);
  const [availabilityPeriod, setAvailabilityPeriod] = useState('week');
  const [availability, setAvailability] = useState(null);
  const [loadingAvailability, setLoadingAvailability] = useState(false);
  const [icon, setIcon] = useState('');
  const [secondaryIcon, setSecondaryIcon] = useState('');
  const [name, setName] = useState('');
  const [role, setRole] = useState('device');
  const [room, setRoom] = useState('');
  const [known, setKnown] = useState(false);
  const [isVisitor, setIsVisitor] = useState(false);
  const [onlineNotificationPreference, setOnlineNotificationPreference] = useState('inherit');
  const [offlineNotificationPreference, setOfflineNotificationPreference] = useState('inherit');
  const [presenceExpectation, setPresenceExpectation] = useState('automatic');
  const [offlineAttentionAfterDays, setOfflineAttentionAfterDays] = useState('');
  const [comments, setComments] = useState('');
  const [externalUrl, setExternalUrl] = useState('');
  const [externalUrlFollowDeviceIp, setExternalUrlFollowDeviceIp] = useState(false);
  const [homeboxItemId, setHomeboxItemId] = useState(null);
  const [detectedWebUrl, setDetectedWebUrl] = useState('');
  const [detectingWebUrl, setDetectingWebUrl] = useState(false);
  const [attentionAcknowledged, setAttentionAcknowledged] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loadingMoreEvents, setLoadingMoreEvents] = useState(false);
  const [activeDeviceTab, setActiveDeviceTab] = useState('overview');
  const [dnsActivity, setDnsActivity] = useState([]);
  const [dnsPagination, setDnsPagination] = useState(null);
  const [dnsSummary, setDnsSummary] = useState(null);
  const [dnsIntegration, setDnsIntegration] = useState(null);
  const [dnsSearch, setDnsSearch] = useState('');
  const [dnsFilter, setDnsFilter] = useState('all');
  const [dnsOrdering, setDnsOrdering] = useState('-last_seen');
  const [loadingDnsActivity, setLoadingDnsActivity] = useState(false);
  const [loadingMoreDnsActivity, setLoadingMoreDnsActivity] = useState(false);
  const [saving, setSaving] = useState(false);
  const [waking, setWaking] = useState(false);
  const [portScan, setPortScan] = useState(null);
  const [portScanSpec, setPortScanSpec] = useState('1-1024');
  const [portScanLoading, setPortScanLoading] = useState(false);
  const [portScanError, setPortScanError] = useState('');
  const [editing, setEditing] = useState(false);
  const [error, setError] = useState('');
  const [deleteConfirmOpened, deleteConfirm] = useDisclosure(false);
  const [archiveConfirmOpened, archiveConfirm] = useDisclosure(false);
  const [portScanOpened, portScanModal] = useDisclosure(false);
  const completedPortScanRef = useRef(null);

  function populateForm(nextDevice) {
    setIcon(nextDevice?.icon || '');
    setSecondaryIcon(nextDevice?.secondary_icon || '');
    setName(nextDevice?.name || '');
    setRole(nextDevice?.role || 'device');
    setRoom(nextDevice?.room || '');
    setKnown(Boolean(nextDevice?.known));
    setIsVisitor(Boolean(nextDevice?.is_visitor));
    setOnlineNotificationPreference(nextDevice?.online_notification_preference || 'inherit');
    setOfflineNotificationPreference(nextDevice?.offline_notification_preference || 'inherit');
    setPresenceExpectation(nextDevice?.presence_expectation || 'automatic');
    setOfflineAttentionAfterDays(nextDevice?.offline_attention_after_days ?? '');
    setComments(nextDevice?.comments || '');
    setExternalUrl(
      nextDevice?.external_url_follow_device_ip
        ? nextDevice?.effective_external_url || nextDevice?.external_url || ''
        : nextDevice?.external_url || ''
    );
    setExternalUrlFollowDeviceIp(Boolean(nextDevice?.external_url_follow_device_ip));
    setHomeboxItemId(nextDevice?.homebox_item_id || null);
    setAttentionAcknowledged(Boolean(nextDevice?.attention_acknowledged));
  }

  function startEditing() {
    setActiveDeviceTab('overview');
    if (!externalUrl.trim() && detectedWebUrl) {
      setExternalUrl(detectedWebUrl);
      setExternalUrlFollowDeviceIp(true);
    }
    setEditing(true);
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

  async function loadDnsActivity({ offset = 0, append = false, quiet = false } = {}) {
    if (!quiet) {
      setLoadingDnsActivity(true);
    }
    const params = {
      id: deviceId,
      limit: 100,
      offset,
      search: dnsSearch.trim(),
      ordering: dnsOrdering,
    };
    if (dnsFilter === 'blocked') {
      params.blocked = true;
    } else if (dnsFilter === 'allowed') {
      params.blocked = false;
    }
    try {
      const payload = await apiRequest('device/dns-activity/', { params });
      const nextActivity = payload.data || [];
      setDnsActivity((current) =>
        append ? appendUniqueById(current, nextActivity) : nextActivity
      );
      setDnsPagination(payload.pagination || null);
      setDnsSummary(payload.summary || null);
      setDnsIntegration(payload.integration || null);
    } finally {
      if (!quiet) {
        setLoadingDnsActivity(false);
      }
    }
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
    if (!portScanOpened) {
      return undefined;
    }
    let active = true;

    async function refreshPortScan() {
      try {
        const payload = await apiRequest('device/port-scan/', {
          params: { device: deviceId },
        });
        if (!active) {
          return;
        }
        const nextScan = payload.data || null;
        setPortScan(nextScan);
        setPortScanError('');
        if (
          nextScan?.status === 'success'
          && completedPortScanRef.current !== nextScan.id
        ) {
          completedPortScanRef.current = nextScan.id;
          const updatedDevice = await loadDevice({ quiet: true });
          if (updatedDevice) {
            await onSaved(updatedDevice);
          }
        }
      } catch (err) {
        if (active) {
          setPortScanError(err.message);
        }
      }
    }

    setPortScanLoading(true);
    refreshPortScan().finally(() => {
      if (active) {
        setPortScanLoading(false);
      }
    });
    const scanIsActive = portScan?.status === 'queued' || portScan?.status === 'running';
    const timer = scanIsActive ? window.setInterval(refreshPortScan, 1000) : null;
    return () => {
      active = false;
      if (timer) {
        window.clearInterval(timer);
      }
    };
  }, [deviceId, portScan?.id, portScan?.status, portScanOpened]);

  useEffect(() => {
    setActiveDeviceTab('overview');
    setAvailabilityPeriod('week');
    setAvailability(null);
    setDnsActivity([]);
    setDnsPagination(null);
    setDnsSummary(null);
    setDnsIntegration(null);
    setDnsSearch('');
    setDnsFilter('all');
    setDnsOrdering('-last_seen');
  }, [deviceId]);

  useEffect(() => {
    if (activeDeviceTab !== 'history') {
      return undefined;
    }
    let active = true;
    setLoadingAvailability(true);
    apiRequest('device/availability/', {
      params: { device: deviceId, period: availabilityPeriod },
    })
      .then((payload) => {
        if (active) {
          setAvailability(payload.data || null);
        }
      })
      .catch((err) => {
        if (active) {
          onError(err);
        }
      })
      .finally(() => {
        if (active) {
          setLoadingAvailability(false);
        }
      });
    return () => {
      active = false;
    };
  }, [activeDeviceTab, availabilityPeriod, deviceId]);

  useEffect(() => {
    if (activeDeviceTab !== 'dns') {
      return undefined;
    }
    const timer = window.setTimeout(() => {
      loadDnsActivity().catch((err) => {
        onError(err);
      });
    }, 250);
    return () => window.clearTimeout(timer);
  }, [activeDeviceTab, deviceId, dnsSearch, dnsFilter, dnsOrdering]);

  useEffect(() => {
    if (!dnsActivityEnabled && activeDeviceTab === 'dns') {
      setActiveDeviceTab('overview');
    }
  }, [activeDeviceTab, dnsActivityEnabled]);

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

  async function changeArchiveState() {
    setSaving(true);
    setError('');
    try {
      const payload = await apiRequest(`device/?id=${device.id}`, {
        method: 'PUT', body: { archived: !device.archived },
      });
      const updatedDevice = await loadDevice({ quiet: true });
      await onSaved(updatedDevice);
      archiveConfirm.close();
      setEditing(false);
      onSuccess(payload);
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

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
      onError('Could not save device', message);
      setSaving(false);
      return;
    }
    if (externalUrlFollowDeviceIp && !externalUrlUsesIPv4(externalUrl)) {
      const message = 'Follow device IP requires an External link with an IPv4 address.';
      setError(message);
      onError('Could not save device', message);
      setSaving(false);
      return;
    }
    try {
      const payload = await apiRequest(`device/?id=${device.id}`, {
        method: 'PUT',
        body: {
          icon,
          secondary_icon: secondaryIcon || '',
          name,
          role,
          room,
          known,
          is_visitor: isVisitor,
          online_notification_preference: onlineNotificationPreference,
          offline_notification_preference: offlineNotificationPreference,
          presence_expectation: presenceExpectation,
          offline_attention_after_days: ['always', 'occasional'].includes(presenceExpectation)
            ? offlineAttentionAfterDays || null
            : null,
          comments,
          external_url: externalUrl.trim(),
          external_url_follow_device_ip: externalUrlFollowDeviceIp,
          homebox_item_id: homeboxItemId,
          acknowledge_attention: known && attentionAcknowledged,
        },
      });
      const updatedDevice = await loadDevice({ quiet: true });
      await onSaved(updatedDevice);
      onSuccess(payload);
      setEditing(false);
    } catch (err) {
      setError(err.message);
      onError(err);
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
    try {
      const payload = await apiRequest(`device/?id=${device.id}`, { method: 'DELETE' });
      onSuccess(payload);
      deleteConfirm.close();
      await onDeleted();
    } catch (err) {
      setError(err.message);
      onError(err);
    } finally {
      setSaving(false);
    }
  }

  async function wake() {
    if (!device) {
      return;
    }
    setWaking(true);
    try {
      const payload = await apiRequest('device/wake/', {
        method: 'POST',
        body: { id: device.id },
      });
      onSuccess(payload);
    } catch (err) {
      onError(err);
    } finally {
      setWaking(false);
    }
  }

  async function startDetailedPortScan() {
    setPortScanLoading(true);
    setPortScanError('');
    try {
      const payload = await apiRequest('device/port-scan/', {
        method: 'POST',
        body: { device: device.id, ports: portScanSpec },
      });
      setPortScan(payload.data || null);
      onSuccess(payload);
    } catch (err) {
      setPortScanError(err.message);
      onError(err);
    } finally {
      setPortScanLoading(false);
    }
  }

  async function cancelDetailedPortScan() {
    if (!portScan) {
      return;
    }
    setPortScanLoading(true);
    setPortScanError('');
    try {
      const payload = await apiRequest('device/port-scan/cancel/', {
        method: 'POST',
        body: { id: portScan.id },
      });
      setPortScan(payload.data || portScan);
      onSuccess(payload);
    } catch (err) {
      setPortScanError(err.message);
      onError(err);
    } finally {
      setPortScanLoading(false);
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
      onError(err);
    } finally {
      setLoadingMoreEvents(false);
    }
  }

  async function loadMoreDnsActivity() {
    if (!hasNextActivityPage(dnsPagination) || loadingMoreDnsActivity) {
      return;
    }
    setLoadingMoreDnsActivity(true);
    try {
      await loadDnsActivity({
        offset: dnsPagination.next_offset,
        append: true,
        quiet: true,
      });
    } catch (err) {
      onError(err);
    } finally {
      setLoadingMoreDnsActivity(false);
    }
  }

  const currentStatus = device ? deviceStatus(device) : null;
  const externalUrlCandidate = externalUrl.trim() || detectedWebUrl;
  const activeUrl = resolveExternalUrl(
    externalUrlCandidate,
    device?.ip || '',
    externalUrl.trim() ? externalUrlFollowDeviceIp : Boolean(detectedWebUrl)
  );

  return (
    <Paper className="device-detail-page" radius="md">
      <LoadingOverlay visible={loading} />
      <Stack gap="lg">
        <DeviceDetailsHeader
          archiveConfirm={archiveConfirm}
          canEditDevices={canEditDevices}
          canRunScans={canRunScans}
          cancelEditing={cancelEditing}
          currentStatus={currentStatus}
          device={device}
          editing={editing}
          onBack={onBack}
          openPortScan={portScanModal.open}
          save={save}
          saving={saving}
          startEditing={startEditing}
          wake={wake}
          waking={waking}
        />

        {error && (
          <Alert color="red" icon={<IconAlertCircle size={18} />}>
            {error}
          </Alert>
        )}
        {device && (
          <Tabs value={activeDeviceTab} onChange={setActiveDeviceTab} keepMounted={false}>
            <Tabs.List>
              <Tabs.Tab value="overview" leftSection={<IconNetwork size={17} />}>Overview</Tabs.Tab>
              {!editing && (
                <Tabs.Tab value="history" leftSection={<IconHistory size={17} />}>History</Tabs.Tab>
              )}
              {!editing && dnsActivityEnabled && (
                <Tabs.Tab value="dns" leftSection={<IconWorldSearch size={17} />}>DNS activity</Tabs.Tab>
              )}
            </Tabs.List>

            <DeviceOverviewTab
              activeUrl={activeUrl}
              attentionAcknowledged={attentionAcknowledged}
              canEditDevices={canEditDevices}
              comments={comments}
              currentStatus={currentStatus}
              deleteConfirm={deleteConfirm}
              detectedWebUrl={detectedWebUrl}
              detectingWebUrl={detectingWebUrl}
              device={device}
              editing={editing}
              externalUrl={externalUrl}
              externalUrlFollowDeviceIp={externalUrlFollowDeviceIp}
              homeboxItemId={homeboxItemId}
              icon={icon}
              isVisitor={isVisitor}
              known={known}
              name={name}
              offlineAttentionAfterDays={offlineAttentionAfterDays}
              offlineNotificationPreference={offlineNotificationPreference}
              onlineNotificationPreference={onlineNotificationPreference}
              presenceExpectation={presenceExpectation}
              role={role}
              room={room}
              roomOptions={roomOptions}
              secondaryIcon={secondaryIcon}
              setAttentionAcknowledged={setAttentionAcknowledged}
              setComments={setComments}
              setExternalUrl={setExternalUrl}
              setExternalUrlFollowDeviceIp={setExternalUrlFollowDeviceIp}
              setHomeboxItemId={setHomeboxItemId}
              setIcon={setIcon}
              setIsVisitor={setIsVisitor}
              setKnown={setKnown}
              setName={setName}
              setOfflineAttentionAfterDays={setOfflineAttentionAfterDays}
              setOfflineNotificationPreference={setOfflineNotificationPreference}
              setOnlineNotificationPreference={setOnlineNotificationPreference}
              setPresenceExpectation={setPresenceExpectation}
              setRole={setRole}
              setRoom={setRoom}
              setSecondaryIcon={setSecondaryIcon}
              timeZone={timeZone}
            />

            <DeviceHistoryTab
              availability={availability}
              availabilityPeriod={availabilityPeriod}
              eventPagination={eventPagination}
              events={events}
              loadMoreEvents={loadMoreEvents}
              loadingAvailability={loadingAvailability}
              loadingMoreEvents={loadingMoreEvents}
              setAvailabilityPeriod={setAvailabilityPeriod}
              timeZone={timeZone}
            />

            {dnsActivityEnabled && (
              <DeviceDnsActivityTab
                dnsActivity={dnsActivity}
                dnsFilter={dnsFilter}
                dnsIntegration={dnsIntegration}
                dnsOrdering={dnsOrdering}
                dnsPagination={dnsPagination}
                dnsSearch={dnsSearch}
                dnsSummary={dnsSummary}
                loadMoreDnsActivity={loadMoreDnsActivity}
                loadingDnsActivity={loadingDnsActivity}
                loadingMoreDnsActivity={loadingMoreDnsActivity}
                setDnsFilter={setDnsFilter}
                setDnsOrdering={setDnsOrdering}
                setDnsSearch={setDnsSearch}
                timeZone={timeZone}
              />
            )}
          </Tabs>
        )}
      </Stack>
      <DeviceDetailsModals
        archiveConfirm={archiveConfirm}
        archiveConfirmOpened={archiveConfirmOpened}
        cancelDetailedPortScan={cancelDetailedPortScan}
        changeArchiveState={changeArchiveState}
        deleteConfirm={deleteConfirm}
        deleteConfirmOpened={deleteConfirmOpened}
        device={device}
        portScan={portScan}
        portScanError={portScanError}
        portScanLoading={portScanLoading}
        portScanModal={portScanModal}
        portScanOpened={portScanOpened}
        portScanSpec={portScanSpec}
        remove={remove}
        saving={saving}
        setPortScanSpec={setPortScanSpec}
        startDetailedPortScan={startDetailedPortScan}
      />
    </Paper>
  );
}
