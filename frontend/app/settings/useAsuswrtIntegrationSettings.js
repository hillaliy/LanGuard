import { useState } from 'react';

import { apiRequest } from '../api';
import { showServerNotification } from '../utils/notifications';

const defaults = {
  enabled: false, url: '', username: '', password: '', verifySsl: true, createDevices: false,
  syncInterval: 5, configured: false, lastSyncAt: null, summary: {}, lastError: '', authFailed: false,
};

export default function useAsuswrtIntegrationSettings({ runAction, reloadSettings }) {
  const [asuswrt, setAsuswrt] = useState(defaults);
  const [saved, setSaved] = useState(null);
  const [testingAsuswrt, setTestingAsuswrt] = useState(false);
  const [syncingAsuswrt, setSyncingAsuswrt] = useState(false);

  function hydrate(data) {
    const state = {
      enabled: Boolean(data.asuswrt_enabled), url: data.asuswrt_url || '',
      username: data.asuswrt_username || '', password: '', verifySsl: data.asuswrt_verify_ssl !== false,
      createDevices: Boolean(data.asuswrt_create_devices), syncInterval: Number(data.asuswrt_sync_interval || 5),
      configured: Boolean(data.asuswrt_configured), lastSyncAt: data.asuswrt_last_sync_at,
      summary: data.asuswrt_last_sync_summary || {}, lastError: data.asuswrt_last_error || '',
      authFailed: Boolean(data.asuswrt_auth_failed),
    };
    setAsuswrt(state);
    setSaved(state);
  }

  function setAsuswrtField(field, value) {
    setAsuswrt((current) => ({ ...current, [field]: value }));
  }

  function buildPayload() {
    const payload = {
      asuswrt_enabled: asuswrt.enabled, asuswrt_url: asuswrt.url.trim(),
      asuswrt_username: asuswrt.username.trim(), asuswrt_verify_ssl: asuswrt.verifySsl,
      asuswrt_create_devices: asuswrt.createDevices, asuswrt_sync_interval: asuswrt.syncInterval,
    };
    if (asuswrt.password) payload.asuswrt_password = asuswrt.password;
    return payload;
  }

  function testAsuswrtConnection() {
    return runAction(setTestingAsuswrt, async () => {
      const payload = await apiRequest('integrations/asuswrt/test/', {
        method: 'POST', body: { url: asuswrt.url.trim(), username: asuswrt.username.trim(),
          password: asuswrt.password, verify_ssl: asuswrt.verifySsl },
      });
      showServerNotification(payload);
    });
  }

  function syncAsuswrtNow() {
    return runAction(setSyncingAsuswrt, async () => {
      try {
        const payload = await apiRequest('integrations/asuswrt/sync/', { method: 'POST' });
        showServerNotification(payload);
      } finally {
        await reloadSettings();
      }
    });
  }

  const asuswrtSyncReady = Boolean(saved?.enabled && saved.configured && !asuswrt.password
    && ['enabled', 'url', 'username', 'verifySsl', 'createDevices', 'syncInterval']
      .every((field) => saved[field] === asuswrt[field]));
  const asuswrtTestReady = Boolean(asuswrt.url.trim() && asuswrt.username.trim()
    && (asuswrt.password || (saved?.configured && saved.url === asuswrt.url.trim()
      && saved.username === asuswrt.username.trim())));

  return { hydrate, buildPayload, controller: {
    asuswrtConsoleUrl: saved?.configured ? saved.url : '',
    asuswrt, setAsuswrtField, testingAsuswrt, syncingAsuswrt, asuswrtSyncReady, asuswrtTestReady,
    testAsuswrtConnection, syncAsuswrtNow,
  } };
}
