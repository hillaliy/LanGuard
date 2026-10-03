import { useState } from 'react';
import { notifications } from '@mantine/notifications';
import { apiRequest } from '../api';
import { showErrorNotification, showServerNotification } from '../utils/notifications';

export default function useIntegrationSettings({ onSaved, reloadSettings, setError, timeZone }) {
  const [adguardEnabled, setAdguardEnabled] = useState(false);
  const [adguardConfigured, setAdguardConfigured] = useState(false);
  const [adguardUrl, setAdguardUrl] = useState('');
  const [adguardUsername, setAdguardUsername] = useState('');
  const [adguardPassword, setAdguardPassword] = useState('');
  const [adguardSyncInterval, setAdguardSyncInterval] = useState(5);
  const [adguardRetentionDays, setAdguardRetentionDays] = useState(90);
  const [adguardLastSyncAt, setAdguardLastSyncAt] = useState(null);
  const [adguardLastError, setAdguardLastError] = useState('');
  const [piholeEnabled, setPiholeEnabled] = useState(false);
  const [piholeConfigured, setPiholeConfigured] = useState(false);
  const [piholeUrl, setPiholeUrl] = useState('');
  const [piholePassword, setPiholePassword] = useState('');
  const [piholeSyncInterval, setPiholeSyncInterval] = useState(5);
  const [piholeRetentionDays, setPiholeRetentionDays] = useState(90);
  const [piholeLastSyncAt, setPiholeLastSyncAt] = useState(null);
  const [piholeLastError, setPiholeLastError] = useState('');
  const [speedtestTrackerEnabled, setSpeedtestTrackerEnabled] = useState(false);
  const [speedtestTrackerConfigured, setSpeedtestTrackerConfigured] = useState(false);
  const [speedtestTrackerUrl, setSpeedtestTrackerUrl] = useState('');
  const [speedtestTrackerApiToken, setSpeedtestTrackerApiToken] = useState('');
  const [homeboxEnabled, setHomeboxEnabled] = useState(false);
  const [homeboxConfigured, setHomeboxConfigured] = useState(false);
  const [homeboxUrl, setHomeboxUrl] = useState('');
  const [homeboxToken, setHomeboxToken] = useState('');
  const [integrationCategory, setIntegrationCategory] = useState('network-services');
  const [testingAdguard, setTestingAdguard] = useState(false);
  const [syncingAdguard, setSyncingAdguard] = useState(false);
  const [testingPihole, setTestingPihole] = useState(false);
  const [syncingPihole, setSyncingPihole] = useState(false);
  const [testingSpeedtestTracker, setTestingSpeedtestTracker] = useState(false);
  const [testingHomebox, setTestingHomebox] = useState(false);

  function hydrate(data) {
    setAdguardEnabled(Boolean(data.adguard_enabled));
    setAdguardConfigured(Boolean(data.adguard_configured));
    setAdguardUrl(data.adguard_url || '');
    setAdguardUsername(data.adguard_username || '');
    setAdguardPassword('');
    setAdguardSyncInterval(Number(data.adguard_sync_interval || 5));
    setAdguardRetentionDays(Number(data.adguard_retention_days || 90));
    setAdguardLastSyncAt(data.adguard_last_sync_at || null);
    setAdguardLastError(data.adguard_last_error || '');
    setPiholeEnabled(Boolean(data.pihole_enabled));
    setPiholeConfigured(Boolean(data.pihole_configured));
    setPiholeUrl(data.pihole_url || '');
    setPiholePassword('');
    setPiholeSyncInterval(Number(data.pihole_sync_interval || 5));
    setPiholeRetentionDays(Number(data.pihole_retention_days || 90));
    setPiholeLastSyncAt(data.pihole_last_sync_at || null);
    setPiholeLastError(data.pihole_last_error || '');
    setSpeedtestTrackerEnabled(Boolean(data.speedtest_tracker_enabled));
    setSpeedtestTrackerConfigured(Boolean(data.speedtest_tracker_configured));
    setSpeedtestTrackerUrl(data.speedtest_tracker_url || '');
    setSpeedtestTrackerApiToken('');
    setHomeboxEnabled(Boolean(data.homebox_enabled));
    setHomeboxConfigured(Boolean(data.homebox_configured));
    setHomeboxUrl(data.homebox_url || '');
    setHomeboxToken('');
  }

  function buildPayload() {
    const payload = {
      adguard_enabled: adguardEnabled,
      adguard_url: adguardUrl.trim(),
      adguard_username: adguardUsername.trim(),
      adguard_sync_interval: adguardSyncInterval,
      adguard_retention_days: adguardRetentionDays,
      pihole_enabled: piholeEnabled,
      pihole_url: piholeUrl.trim(),
      pihole_sync_interval: piholeSyncInterval,
      pihole_retention_days: piholeRetentionDays,
      speedtest_tracker_enabled: speedtestTrackerEnabled,
      speedtest_tracker_url: speedtestTrackerUrl.trim(),
      homebox_enabled: homeboxEnabled,
      homebox_url: homeboxUrl.trim(),
    };
    if (adguardPassword) payload.adguard_password = adguardPassword;
    if (piholePassword) payload.pihole_password = piholePassword;
    if (speedtestTrackerApiToken) {
      payload.speedtest_tracker_api_token = speedtestTrackerApiToken;
    }
    if (homeboxToken) payload.homebox_api_token = homeboxToken;
    return payload;
  }

  async function runAction(setBusy, action) {
    setBusy(true);
    setError('');
    try {
      await action();
    } catch (err) {
      setError(err.message);
      showErrorNotification(err);
    } finally {
      setBusy(false);
    }
  }

  function testAdguardConnection() {
    return runAction(setTestingAdguard, async () => {
      const body = { url: adguardUrl.trim(), username: adguardUsername.trim() };
      if (adguardPassword) body.password = adguardPassword;
      const payload = await apiRequest('integrations/adguard/test/', { method: 'POST', body });
      showServerNotification(payload);
    });
  }

  function syncAdguardNow() {
    return runAction(setSyncingAdguard, async () => {
      const payload = await apiRequest('integrations/adguard/sync/', { method: 'POST' });
      await reloadSettings();
      showServerNotification(payload);
    });
  }

  function testPiholeConnection() {
    return runAction(setTestingPihole, async () => {
      const body = { url: piholeUrl.trim() };
      if (piholePassword) body.password = piholePassword;
      const payload = await apiRequest('integrations/pihole/test/', { method: 'POST', body });
      showServerNotification(payload);
    });
  }

  function syncPiholeNow() {
    return runAction(setSyncingPihole, async () => {
      const payload = await apiRequest('integrations/pihole/sync/', { method: 'POST' });
      await reloadSettings();
      showServerNotification(payload);
    });
  }

  function testSpeedtestTrackerConnection() {
    return runAction(setTestingSpeedtestTracker, async () => {
      const body = { url: speedtestTrackerUrl.trim() };
      if (speedtestTrackerApiToken) body.api_token = speedtestTrackerApiToken;
      const payload = await apiRequest('integrations/speedtest-tracker/test/', {
        method: 'POST', body,
      });
      showServerNotification(payload);
    });
  }

  async function testHomeboxConnection() {
    setTestingHomebox(true);
    setError('');
    try {
      await apiRequest('integrations/homebox/test/', {
        method: 'POST', body: { url: homeboxUrl.trim(), api_token: homeboxToken },
      });
      notifications.show({ title: 'HomeBox', message: 'Connection successful', color: 'teal' });
    } catch (err) {
      setError(err.message);
    } finally {
      setTestingHomebox(false);
    }
  }

  return {
    hydrate,
    buildPayload,
    integrationCategory,
    controller: {
      adguardConfigured, adguardEnabled, adguardLastError, adguardLastSyncAt,
      adguardPassword, adguardRetentionDays, adguardSyncInterval, adguardUrl,
      adguardUsername, homeboxConfigured, homeboxEnabled, homeboxToken, homeboxUrl,
      integrationCategory, onSaved, piholeConfigured, piholeEnabled, piholeLastError,
      piholeLastSyncAt, piholePassword, piholeRetentionDays, piholeSyncInterval,
      piholeUrl, setAdguardEnabled, setAdguardPassword, setAdguardRetentionDays,
      setAdguardSyncInterval, setAdguardUrl, setAdguardUsername, setHomeboxEnabled,
      setHomeboxToken, setHomeboxUrl, setIntegrationCategory, setPiholeEnabled,
      setPiholePassword, setPiholeRetentionDays, setPiholeSyncInterval, setPiholeUrl,
      setSpeedtestTrackerApiToken, setSpeedtestTrackerEnabled, setSpeedtestTrackerUrl,
      speedtestTrackerApiToken, speedtestTrackerConfigured, speedtestTrackerEnabled,
      speedtestTrackerUrl, syncAdguardNow, syncPiholeNow, syncingAdguard, syncingPihole,
      testAdguardConnection, testHomeboxConnection, testPiholeConnection,
      testSpeedtestTrackerConnection, testingAdguard, testingHomebox, testingPihole,
      testingSpeedtestTracker, timeZone,
    },
  };
}
