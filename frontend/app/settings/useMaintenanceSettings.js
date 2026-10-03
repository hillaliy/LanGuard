import { useState } from 'react';
import { useDisclosure } from '@mantine/hooks';
import { apiRequest } from '../api';
import { showErrorNotification, showServerNotification } from '../utils/notifications';

const cleanupTargetLabels = {
  events: 'Events',
  scan_runs: 'Scan history',
  notifications: 'Notifications',
  dns_activity: 'DNS activity',
};

export default function useMaintenanceSettings({ onSaved, setError }) {
  const [exportingDiagnostics, setExportingDiagnostics] = useState(false);
  const [cleanupDays, setCleanupDays] = useState(90);
  const [savedCleanupDays, setSavedCleanupDays] = useState(90);
  const [cleanupRetentionStatus, setCleanupRetentionStatus] = useState('');
  const [cleanupTarget, setCleanupTarget] = useState(null);
  const [cleaningActivity, setCleaningActivity] = useState('');
  const [cleanupConfirmOpened, cleanupConfirm] = useDisclosure(false);

  function hydrate(data) {
    const loadedCleanupDays = Number(data.activity_cleanup_retention_days ?? 90);
    setCleanupDays(loadedCleanupDays);
    setSavedCleanupDays(loadedCleanupDays);
    setCleanupRetentionStatus('');
  }

  async function exportDiagnostics() {
    setExportingDiagnostics(true);
    setError('');
    try {
      const payload = await apiRequest('diagnostics/export/');
      const data = payload.data || {};
      const json = JSON.stringify(data.report || {}, null, 2);
      const blob = new Blob([json], { type: 'application/json' });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = data.filename || 'languard-diagnostics.json';
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      showServerNotification(payload);
    } catch (err) {
      setError(err.message);
      showErrorNotification(err);
    } finally {
      setExportingDiagnostics(false);
    }
  }

  async function cleanupActivity(cleanAll = false) {
    if (!cleanupTarget) return false;

    setCleaningActivity(cleanupTarget);
    setError('');
    try {
      const result = await apiRequest('maintenance/cleanup/', {
        method: 'POST',
        body: cleanAll
          ? { target: cleanupTarget, clean_all: true }
          : { target: cleanupTarget, older_than_days: cleanupDays },
      });
      await onSaved({});
      showServerNotification(result);
      return true;
    } catch (err) {
      setError(err.message);
      showErrorNotification(err);
      return false;
    } finally {
      setCleaningActivity('');
    }
  }

  function openCleanupConfirm(target) {
    setCleanupTarget(target);
    cleanupConfirm.open();
  }

  async function saveCleanupRetention() {
    const normalizedDays = Math.min(3650, Math.max(1, Number(cleanupDays) || 90));
    setCleanupDays(normalizedDays);
    if (normalizedDays === savedCleanupDays) {
      setCleanupRetentionStatus('');
      return;
    }

    setCleanupRetentionStatus('saving');
    try {
      await apiRequest('settings/', {
        method: 'PUT',
        body: { activity_cleanup_retention_days: normalizedDays },
      });
      setSavedCleanupDays(normalizedDays);
      setCleanupRetentionStatus('saved');
    } catch (err) {
      setCleanupRetentionStatus('error');
      setError(err.message);
      showErrorNotification(err);
    }
  }

  return {
    hydrate,
    cleanupDays,
    controller: {
      cleaningActivity, cleanupActivity, cleanupConfirm, cleanupConfirmOpened,
      cleanupDays, cleanupRetentionStatus, cleanupTarget, cleanupTargetLabels,
      exportDiagnostics, exportingDiagnostics, openCleanupConfirm,
      saveCleanupRetention, setCleanupDays, setCleanupRetentionStatus,
    },
  };
}
