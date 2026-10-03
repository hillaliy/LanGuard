import { useEffect, useRef, useState } from 'react';
import { useDisclosure } from '@mantine/hooks';
import { apiRequest } from '../api';

export default function useDevicePortScan({
  device,
  deviceId,
  loadDevice,
  onError,
  onSaved,
  onSuccess,
}) {
  const [portScan, setPortScan] = useState(null);
  const [portScanSpec, setPortScanSpec] = useState('1-1024');
  const [portScanLoading, setPortScanLoading] = useState(false);
  const [portScanError, setPortScanError] = useState('');
  const [portScanOpened, portScanModal] = useDisclosure(false);
  const completedPortScanRef = useRef(null);

  useEffect(() => {
    if (!portScanOpened) return undefined;
    let active = true;

    async function refreshPortScan() {
      try {
        const payload = await apiRequest('device/port-scan/', {
          params: { device: deviceId },
        });
        if (!active) return;
        const nextScan = payload.data || null;
        setPortScan(nextScan);
        setPortScanError('');
        if (
          nextScan?.status === 'success'
          && completedPortScanRef.current !== nextScan.id
        ) {
          completedPortScanRef.current = nextScan.id;
          const updatedDevice = await loadDevice({ quiet: true });
          if (updatedDevice) await onSaved(updatedDevice);
        }
      } catch (err) {
        if (active) setPortScanError(err.message);
      }
    }

    setPortScanLoading(true);
    refreshPortScan().finally(() => {
      if (active) setPortScanLoading(false);
    });
    const scanIsActive = portScan?.status === 'queued' || portScan?.status === 'running';
    const timer = scanIsActive ? window.setInterval(refreshPortScan, 1000) : null;
    return () => {
      active = false;
      if (timer) window.clearInterval(timer);
    };
  }, [deviceId, portScan?.id, portScan?.status, portScanOpened]);

  async function startDetailedPortScan() {
    setPortScanLoading(true);
    setPortScanError('');
    try {
      const payload = await apiRequest('device/port-scan/', {
        method: 'POST',
        body: { device: device.id, ports: portScanSpec },
      });
      setPortScan(payload.data || null);
      onSuccess(payload);
    } catch (err) {
      setPortScanError(err.message);
      onError(err);
    } finally {
      setPortScanLoading(false);
    }
  }

  async function cancelDetailedPortScan() {
    if (!portScan) return;
    setPortScanLoading(true);
    setPortScanError('');
    try {
      const payload = await apiRequest('device/port-scan/cancel/', {
        method: 'POST',
        body: { id: portScan.id },
      });
      setPortScan(payload.data || portScan);
      onSuccess(payload);
    } catch (err) {
      setPortScanError(err.message);
      onError(err);
    } finally {
      setPortScanLoading(false);
    }
  }

  return {
    open: portScanModal.open,
    modalProps: {
      cancelDetailedPortScan,
      portScan,
      portScanError,
      portScanLoading,
      portScanModal,
      portScanOpened,
      portScanSpec,
      setPortScanSpec,
      startDetailedPortScan,
    },
  };
}
