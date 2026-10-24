import { useState } from 'react';

import { apiRequest } from '../api';
import { showServerNotification } from '../utils/notifications';

export default function useDhcpIntegrationSettings({ runAction, reloadSettings }) {
  const [dhcpEnabled, setDhcpEnabled] = useState(false);
  const [dhcpFormat, setDhcpFormat] = useState('dnsmasq');
  const [dhcpLeaseFile, setDhcpLeaseFile] = useState('');
  const [dhcpCreateDevices, setDhcpCreateDevices] = useState(false);
  const [dhcpSyncInterval, setDhcpSyncInterval] = useState(5);
  const [dhcpLastSyncAt, setDhcpLastSyncAt] = useState(null);
  const [dhcpLastError, setDhcpLastError] = useState('');
  const [dhcpLastSyncSummary, setDhcpLastSyncSummary] = useState({});
  const [savedSource, setSavedSource] = useState(null);
  const [testingDhcp, setTestingDhcp] = useState(false);
  const [syncingDhcp, setSyncingDhcp] = useState(false);

  function hydrate(data) {
    setDhcpEnabled(Boolean(data.dhcp_enabled));
    setDhcpFormat(data.dhcp_format || 'dnsmasq');
    setDhcpLeaseFile(data.dhcp_lease_file || '');
    setDhcpCreateDevices(Boolean(data.dhcp_create_devices));
    setDhcpSyncInterval(Number(data.dhcp_sync_interval || 5));
    setDhcpLastSyncAt(data.dhcp_last_sync_at || null);
    setDhcpLastError(data.dhcp_last_error || '');
    setDhcpLastSyncSummary(data.dhcp_last_sync_summary || {});
    setSavedSource({
      enabled: Boolean(data.dhcp_enabled), format: data.dhcp_format || 'dnsmasq',
      file: data.dhcp_lease_file || '', create: Boolean(data.dhcp_create_devices),
    });
  }

  function buildPayload() {
    return {
      dhcp_enabled: dhcpEnabled, dhcp_format: dhcpFormat, dhcp_lease_file: dhcpLeaseFile.trim(),
      dhcp_create_devices: dhcpCreateDevices, dhcp_sync_interval: dhcpSyncInterval,
    };
  }

  function testDhcpSource() {
    return runAction(setTestingDhcp, async () => {
      const payload = await apiRequest('integrations/dhcp/test/', {
        method: 'POST', body: { lease_file: dhcpLeaseFile.trim(), format: dhcpFormat },
      });
      showServerNotification(payload);
    });
  }

  function syncDhcpNow() {
    return runAction(setSyncingDhcp, async () => {
      const payload = await apiRequest('integrations/dhcp/sync/', { method: 'POST' });
      await reloadSettings();
      showServerNotification(payload);
    });
  }

  const dhcpSyncReady = Boolean(savedSource?.enabled && savedSource.file
    && savedSource.enabled === dhcpEnabled && savedSource.file === dhcpLeaseFile.trim()
    && savedSource.format === dhcpFormat && savedSource.create === dhcpCreateDevices);

  return {
    hydrate, buildPayload,
    controller: {
      dhcpEnabled, setDhcpEnabled, dhcpFormat, setDhcpFormat, dhcpLeaseFile, setDhcpLeaseFile,
      dhcpCreateDevices, setDhcpCreateDevices, dhcpSyncInterval, setDhcpSyncInterval,
      dhcpLastSyncAt, dhcpLastError, dhcpLastSyncSummary, dhcpSyncReady,
      testDhcpSource, syncDhcpNow, testingDhcp, syncingDhcp,
    },
  };
}
