import { useEffect, useState } from 'react';
import { apiRequest } from '../api';
import { showErrorNotification, showServerNotification } from '../utils/notifications';
import useDataMigrationSettings from './useDataMigrationSettings';
import useIntegrationSettings from './useIntegrationSettings';
import useMaintenanceSettings from './useMaintenanceSettings';
import useNotificationSettings from './useNotificationSettings';
import useScanningSettings from './useScanningSettings';

export default function useSettingsController({ onSaved }) {
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [settingsCategory, setSettingsCategory] = useState('scanning');

  const scanning = useScanningSettings();
  const notification = useNotificationSettings({ setError });
  const maintenance = useMaintenanceSettings({ onSaved, setError });
  const dataMigrationSettings = useDataMigrationSettings({ onSaved, setError });
  const integration = useIntegrationSettings({
    onSaved,
    reloadSettings: loadSettings,
    setError,
    timeZone: scanning.timeZone,
  });

  const showSettingsSave =
    settingsCategory === 'scanning'
    || settingsCategory === 'notifications'
    || (settingsCategory === 'integrations'
      && integration.integrationCategory === 'network-services');
  const settingsSaveLabel = settingsCategory === 'integrations'
    ? 'Save integration settings'
    : 'Save changes';

  async function loadSettings() {
    setLoading(true);
    setError('');
    try {
      const payload = await apiRequest('settings/');
      const data = payload.data || {};
      scanning.hydrate(data);
      notification.hydrate(data);
      integration.hydrate(data);
      maintenance.hydrate(data);
    } catch (err) {
      setError(err.message);
      showErrorNotification(err);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadSettings();
  }, []);

  async function saveSettings() {
    setSaving(true);
    setError('');
    try {
      const body = {
        ...scanning.buildPayload(),
        ...notification.buildPayload(),
        ...integration.buildPayload(),
        activity_cleanup_retention_days: maintenance.cleanupDays,
      };
      const savedSettings = await apiRequest('settings/', { method: 'PUT', body });
      await loadSettings();
      await onSaved(savedSettings.data || {});
      showServerNotification(savedSettings);
    } catch (err) {
      setError(err.message);
      showErrorNotification(err);
    } finally {
      setSaving(false);
    }
  }

  return {
    loading,
    error,
    settingsCategory,
    setSettingsCategory,
    scanningSettings: scanning.controller,
    notificationSettings: notification.controller,
    integrationSettings: integration.controller,
    maintenanceSettings: maintenance.controller,
    dataMigrationSettings,
    showSettingsSave,
    saveSettings,
    saving,
    settingsSaveLabel,
  };
}
