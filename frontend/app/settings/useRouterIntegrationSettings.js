import { useState } from 'react';

import { apiRequest } from '../api';
import { showServerNotification } from '../utils/notifications';

const defaults = {
  enabled: false, url: '', username: '', password: '', verifySsl: true, createDevices: false,
  syncInterval: 5, configured: false, lastSyncAt: null, summary: {}, lastError: '', authFailed: false,
};

export default function useRouterIntegrationSettings(provider, { runAction, reloadSettings }) {
  const [form, setForm] = useState(defaults);
  const [saved, setSaved] = useState(null);
  const [testing, setTesting] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const timeoutMs = provider === 'openwrt' ? 35000 : undefined;

  function hydrate(data) {
    const value = (key) => data[`${provider}_${key}`];
    const state = {
      enabled: Boolean(value('enabled')), url: value('url') || '',
      username: value('username') || '', password: '', verifySsl: value('verify_ssl') !== false,
      createDevices: Boolean(value('create_devices')), syncInterval: Number(value('sync_interval') || 5),
      configured: Boolean(value('configured')), lastSyncAt: value('last_sync_at'),
      summary: value('last_sync_summary') || {}, lastError: value('last_error') || '',
      authFailed: Boolean(value('auth_failed')),
    };
    setForm(state);
    setSaved(state);
  }

  function setField(field, value) {
    setForm((current) => ({ ...current, [field]: value }));
  }

  function buildPayload() {
    const payload = {
      [`${provider}_enabled`]: form.enabled, [`${provider}_url`]: form.url.trim(),
      [`${provider}_username`]: form.username.trim(), [`${provider}_verify_ssl`]: form.verifySsl,
      [`${provider}_create_devices`]: form.createDevices, [`${provider}_sync_interval`]: form.syncInterval,
    };
    if (form.password) payload[`${provider}_password`] = form.password;
    return payload;
  }

  function testConnection() {
    return runAction(setTesting, async () => {
      const payload = await apiRequest(`integrations/${provider}/test/`, {
        timeoutMs,
        method: 'POST', body: { url: form.url.trim(), username: form.username.trim(),
          password: form.password, verify_ssl: form.verifySsl },
      });
      showServerNotification(payload);
    });
  }

  function syncNow() {
    return runAction(setSyncing, async () => {
      try {
        const payload = await apiRequest(`integrations/${provider}/sync/`, { method: 'POST', timeoutMs });
        showServerNotification(payload);
      } finally {
        await reloadSettings();
      }
    });
  }

  const syncReady = Boolean(saved?.enabled && saved.configured && !form.password
    && ['enabled', 'url', 'username', 'verifySsl', 'createDevices', 'syncInterval']
      .every((field) => saved[field] === form[field]));
  const testReady = Boolean(form.url.trim() && form.username.trim()
    && (form.password || (saved?.configured && saved.url === form.url.trim()
      && saved.username === form.username.trim())));

  return { hydrate, buildPayload, controller: {
    consoleUrl: saved?.configured ? saved.url : '',
    form, setField, testing, syncing, syncReady, testReady, testConnection, syncNow,
  } };
}
