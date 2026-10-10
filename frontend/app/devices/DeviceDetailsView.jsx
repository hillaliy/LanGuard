'use client';

import { useEffect, useState } from 'react';
import { Alert, LoadingOverlay, Paper, Stack, Tabs } from '@mantine/core';
import { useDisclosure } from '@mantine/hooks';
import {
  IconAlertCircle,
  IconHistory,
  IconNetwork,
  IconWorldSearch,
} from '@tabler/icons-react';

import { apiRequest } from '../api';
import {
  deviceStatus,
  resolveExternalUrl,
} from '../utils/device';
import DeviceDetailsHeader from './DeviceDetailsHeader';
import DeviceDetailsModals from './DeviceDetailsModals';
import DeviceDnsActivityTab from './DeviceDnsActivityTab';
import DeviceHistoryTab from './DeviceHistoryTab';
import useDeviceInterfaces from './useDeviceInterfaces';
import DeviceOverviewTab from './DeviceOverviewTab';
import useDeviceActions from './useDeviceActions';
import useDeviceDetailsForm from './useDeviceDetailsForm';
import useDeviceDnsActivity from './useDeviceDnsActivity';
import useDeviceHistory from './useDeviceHistory';
import useDevicePortScan from './useDevicePortScan';

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
  const [relatedLinks, setRelatedLinks] = useState([]);
  const [detectedWebUrl, setDetectedWebUrl] = useState('');
  const [detectingWebUrl, setDetectingWebUrl] = useState(false);
  const [loading, setLoading] = useState(true);
  const [activeDeviceTab, setActiveDeviceTab] = useState('overview');
  const [deleteConfirmOpened, deleteConfirm] = useDisclosure(false);
  const [archiveConfirmOpened, archiveConfirm] = useDisclosure(false);

  const form = useDeviceDetailsForm();
  const history = useDeviceHistory({ activeDeviceTab, deviceId, onError });
  const dns = useDeviceDnsActivity({
    activeDeviceTab,
    deviceId,
    dnsActivityEnabled,
    onError,
    setActiveDeviceTab,
  });
  const portScan = useDevicePortScan({
    device,
    deviceId,
    loadDevice,
    onError,
    onSaved,
    onSuccess,
  });
  const actions = useDeviceActions({
    archiveConfirm,
    deleteConfirm,
    device,
    form,
    loadDevice,
    onDeleted,
    onError,
    onSaved,
    onSuccess,
  });
  const interfaces = useDeviceInterfaces({
    device,
    loadDevice,
    onError,
    onSaved,
    onSuccess,
  });

  async function loadDevice({ quiet = false } = {}) {
    if (!quiet) setLoading(true);
    actions.setError('');
    try {
      const payload = await apiRequest('device/', { params: { id: deviceId } });
      const nextDevice = payload.data;
      setDevice(nextDevice);
      setRelatedLinks(nextDevice.related_links || []);
      form.populate(nextDevice);
      return nextDevice;
    } catch (err) {
      actions.setError(err.message);
      return null;
    } finally {
      if (!quiet) setLoading(false);
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
        if (!active) return;
        setDevice(devicePayload.data);
        setRelatedLinks(devicePayload.data.related_links || []);
        form.populate(devicePayload.data);
        history.hydrateEvents(eventPayload);
        actions.setError('');
      })
      .catch((err) => {
        if (active) actions.setError(err.message);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [deviceId]);

  useEffect(() => {
    setActiveDeviceTab('overview');
  }, [deviceId]);

  useEffect(() => {
    if (!device) return undefined;
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
        if (active) setDetectedWebUrl(payload?.url || '');
      })
      .catch(() => {})
      .finally(() => {
        if (active) setDetectingWebUrl(false);
      });
    return () => {
      active = false;
    };
  }, [device]);

  function startEditing() {
    setActiveDeviceTab('overview');
    form.startEditing(detectedWebUrl);
  }

  function cancelEditing() {
    form.cancelEditing(device);
    actions.setError('');
  }

  const currentStatus = device ? deviceStatus(device) : null;
  const externalUrlCandidate = form.externalUrl.trim() || detectedWebUrl;
  const activeUrl = resolveExternalUrl(
    externalUrlCandidate,
    device?.ip || '',
    form.externalUrl.trim()
      ? form.externalUrlFollowDeviceIp
      : Boolean(detectedWebUrl)
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
          editing={form.editing}
          onBack={onBack}
          openPortScan={portScan.open}
          openMerge={interfaces.openMerge}
          save={actions.save}
          saving={actions.saving}
          startEditing={startEditing}
          wake={actions.wake}
          waking={actions.waking}
        />

        {actions.error && (
          <Alert color="red" icon={<IconAlertCircle size={18} />}>
            {actions.error}
          </Alert>
        )}
        {device && (
          <Tabs value={activeDeviceTab} onChange={setActiveDeviceTab} keepMounted={false}>
            <Tabs.List>
              <Tabs.Tab value="overview" leftSection={<IconNetwork size={17} />}>
                Overview
              </Tabs.Tab>
              {!form.editing && (
                <Tabs.Tab value="history" leftSection={<IconHistory size={17} />}>
                  History
                </Tabs.Tab>
              )}
              {!form.editing && dnsActivityEnabled && (
                <Tabs.Tab value="dns" leftSection={<IconWorldSearch size={17} />}>
                  DNS activity
                </Tabs.Tab>
              )}
            </Tabs.List>

            <DeviceOverviewTab
              {...form.controller}
              activeUrl={activeUrl}
              canEditDevices={canEditDevices}
              currentStatus={currentStatus}
              deleteConfirm={deleteConfirm}
              detectedWebUrl={detectedWebUrl}
              detectingWebUrl={detectingWebUrl}
              device={device}
              roomOptions={roomOptions}
              onSeparateInterface={interfaces.confirmSeparate}
              onError={onError}
              relatedLinks={relatedLinks}
              setRelatedLinks={setRelatedLinks}
              onSuccess={onSuccess}
              timeZone={timeZone}
            />

            <DeviceHistoryTab {...history.controller} timeZone={timeZone} />

            {dnsActivityEnabled && (
              <DeviceDnsActivityTab {...dns.controller} timeZone={timeZone} />
            )}
          </Tabs>
        )}
      </Stack>
      <DeviceDetailsModals
        {...portScan.modalProps}
        archiveConfirm={archiveConfirm}
        archiveConfirmOpened={archiveConfirmOpened}
        changeArchiveState={actions.changeArchiveState}
        deleteConfirm={deleteConfirm}
        deleteConfirmOpened={deleteConfirmOpened}
        device={device}
        remove={actions.remove}
        saving={actions.saving}
        {...interfaces.modalProps}
      />
    </Paper>
  );
}
