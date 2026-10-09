import { useState } from 'react';
import { useDisclosure } from '@mantine/hooks';

import { apiRequest } from '../api';

export default function useDeviceInterfaces({
  device,
  loadDevice,
  onError,
  onSaved,
  onSuccess,
}) {
  const [mergeOpened, mergeModal] = useDisclosure(false);
  const [separateOpened, separateModal] = useDisclosure(false);
  const [candidates, setCandidates] = useState([]);
  const [selectedIds, setSelectedIds] = useState([]);
  const [selectedInterface, setSelectedInterface] = useState(null);
  const [loadingCandidates, setLoadingCandidates] = useState(false);
  const [saving, setSaving] = useState(false);

  async function openMerge() {
    if (!device) return;
    setSelectedIds([]);
    mergeModal.open();
    setLoadingCandidates(true);
    try {
      const payload = await apiRequest('device/merge-candidates/', {
        params: { id: device.id },
      });
      setCandidates(payload.data || []);
    } catch (error) {
      mergeModal.close();
      onError(error);
    } finally {
      setLoadingCandidates(false);
    }
  }

  async function merge() {
    if (!device || !selectedIds.length) return;
    setSaving(true);
    try {
      const payload = await apiRequest('device/merge/', {
        method: 'POST',
        body: {
          target_id: device.id,
          source_ids: selectedIds.map(Number),
        },
      });
      const updatedDevice = await loadDevice({ quiet: true });
      await onSaved(updatedDevice);
      mergeModal.close();
      onSuccess(payload);
    } catch (error) {
      onError(error);
    } finally {
      setSaving(false);
    }
  }

  function confirmSeparate(networkInterface) {
    setSelectedInterface(networkInterface);
    separateModal.open();
  }

  async function separate() {
    if (!device || !selectedInterface) return;
    setSaving(true);
    try {
      const payload = await apiRequest('device/unmerge/', {
        method: 'POST',
        body: {
          target_id: device.id,
          interface_id: selectedInterface.id,
        },
      });
      const updatedDevice = await loadDevice({ quiet: true });
      await onSaved(updatedDevice);
      separateModal.close();
      setSelectedInterface(null);
      onSuccess(payload);
    } catch (error) {
      onError(error);
    } finally {
      setSaving(false);
    }
  }

  return {
    confirmSeparate,
    merge,
    mergeModal,
    mergeOpened,
    openMerge,
    separate,
    separateModal,
    separateOpened,
    modalProps: {
      candidates,
      loadingCandidates,
      merge,
      mergeModal,
      mergeOpened,
      savingInterfaces: saving,
      selectedIds,
      selectedInterface,
      separate,
      separateModal,
      separateOpened,
      setSelectedIds,
    },
  };
}
