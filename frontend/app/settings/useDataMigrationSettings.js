import { useState } from 'react';
import { apiRequest } from '../api';
import { showErrorNotification, showServerNotification } from '../utils/notifications';

export default function useDataMigrationSettings({ onSaved, setError }) {
  const [exporting, setExporting] = useState(false);
  const [importing, setImporting] = useState(false);
  const [importingNetAlertX, setImportingNetAlertX] = useState(false);
  const [importingWatchYourLan, setImportingWatchYourLan] = useState(false);

  async function exportInventory() {
    setExporting(true);
    setError('');
    try {
      const payload = await apiRequest('devices/export/');
      const { notification: exportNotification, ...inventory } = payload;
      const json = JSON.stringify(inventory, null, 2);
      const blob = new Blob([json], { type: 'application/json' });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      const date = new Date().toISOString().slice(0, 10);
      link.href = url;
      link.download = `languard-inventory-${date}.json`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      showServerNotification({ notification: exportNotification });
    } catch (err) {
      setError(err.message);
      showErrorNotification(err);
    } finally {
      setExporting(false);
    }
  }

  async function importInventoryFile(file) {
    if (!file) return;
    setImporting(true);
    setError('');
    try {
      const text = await file.text();
      const payload = JSON.parse(text);
      const result = await apiRequest('devices/import/', { method: 'POST', body: payload });
      await onSaved({});
      showServerNotification(result);
    } catch (err) {
      const message = err instanceof SyntaxError
        ? 'Choose a valid LanGuard JSON inventory file.'
        : err.message;
      setError(message);
      showErrorNotification('Could not import inventory', message);
    } finally {
      setImporting(false);
    }
  }

  async function importWatchYourLanFile(file) {
    if (!file) return;
    setImportingWatchYourLan(true);
    setError('');
    try {
      const text = await file.text();
      const payload = JSON.parse(text);
      const result = await apiRequest('devices/import/watchyourlan/', {
        method: 'POST', body: payload,
      });
      await onSaved({});
      showServerNotification(result);
    } catch (err) {
      const message = err instanceof SyntaxError
        ? 'Choose a valid JSON file downloaded from the WatchYourLAN /api/all endpoint.'
        : err.message;
      setError(message);
      showErrorNotification('Could not import WatchYourLAN devices', message);
    } finally {
      setImportingWatchYourLan(false);
    }
  }

  async function importNetAlertXFile(file) {
    if (!file) return;
    setImportingNetAlertX(true);
    setError('');
    try {
      const content = await file.text();
      const result = await apiRequest('devices/import/netalertx/', {
        method: 'POST', body: { content },
      });
      await onSaved({});
      showServerNotification(result);
    } catch (err) {
      setError(err.message);
      showErrorNotification('Could not import NetAlertX devices', err.message);
    } finally {
      setImportingNetAlertX(false);
    }
  }

  return {
    exportInventory, exporting, importInventoryFile, importNetAlertXFile,
    importWatchYourLanFile, importing, importingNetAlertX, importingWatchYourLan,
  };
}
