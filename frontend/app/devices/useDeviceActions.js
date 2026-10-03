import { useState } from 'react';
import { apiRequest } from '../api';
import { externalUrlUsesIPv4, validExternalUrl } from '../utils/device';

export default function useDeviceActions({
  archiveConfirm,
  deleteConfirm,
  device,
  form,
  loadDevice,
  onDeleted,
  onError,
  onSaved,
  onSuccess,
}) {
  const [saving, setSaving] = useState(false);
  const [waking, setWaking] = useState(false);
  const [error, setError] = useState('');

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
      form.setEditing(false);
      onSuccess(payload);
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  async function save() {
    if (!device || !form.name.trim()) {
      if (!form.name.trim()) setError('Device name is required.');
      return;
    }
    setSaving(true);
    setError('');
    if (!validExternalUrl(form.externalUrl)) {
      const message = 'Enter a valid HTTP or HTTPS URL.';
      setError(message);
      onError('Could not save device', message);
      setSaving(false);
      return;
    }
    if (form.externalUrlFollowDeviceIp && !externalUrlUsesIPv4(form.externalUrl)) {
      const message = 'Follow device IP requires an External link with an IPv4 address.';
      setError(message);
      onError('Could not save device', message);
      setSaving(false);
      return;
    }
    try {
      const payload = await apiRequest(`device/?id=${device.id}`, {
        method: 'PUT',
        body: form.buildPayload(),
      });
      const updatedDevice = await loadDevice({ quiet: true });
      await onSaved(updatedDevice);
      onSuccess(payload);
      form.setEditing(false);
    } catch (err) {
      setError(err.message);
      onError(err);
    } finally {
      setSaving(false);
    }
  }

  async function remove() {
    if (!device) return;
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
    if (!device) return;
    setWaking(true);
    try {
      const payload = await apiRequest('device/wake/', {
        method: 'POST', body: { id: device.id },
      });
      onSuccess(payload);
    } catch (err) {
      onError(err);
    } finally {
      setWaking(false);
    }
  }

  return {
    changeArchiveState,
    error,
    remove,
    save,
    saving,
    setError,
    wake,
    waking,
  };
}
