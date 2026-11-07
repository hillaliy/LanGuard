import { useCallback, useEffect, useRef, useState } from 'react';

import { apiRequest } from '../api';

const emptyMap = { devices: [], links: [], suggestions: [], unresolved: [], hidden_links: 0,
  dismissed_count: 0, layout: { positions: {}, revision: 0 } };

export default function useNetworkMap() {
  const [data, setData] = useState(emptyMap);
  const [positions, setPositions] = useState({});
  const [dirty, setDirty] = useState(false);
  const dirtyRef = useRef(false);
  const baseRevision = useRef(0);
  const requestVersion = useRef(0);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    const version = ++requestVersion.current;
    setLoading(true);
    try {
      const payload = await apiRequest('network-map/');
      if (requestVersion.current !== version) return;
      setData(payload.data);
      if (!dirtyRef.current) {
        setPositions(payload.data.layout.positions);
        baseRevision.current = payload.data.layout.revision;
      }
      setError('');
    } catch (err) {
      if (requestVersion.current === version) setError(err.message);
    } finally {
      if (requestVersion.current === version) setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    return () => { requestVersion.current++; };
  }, [load]);

  function changePositions(next) {
    dirtyRef.current = true;
    setDirty(true);
    setPositions(next);
  }

  function discardPositions() {
    dirtyRef.current = false;
    setDirty(false);
    setPositions(data.layout.positions);
    baseRevision.current = data.layout.revision;
  }

  async function savePositions() {
    setBusy(true);
    try {
      const payload = await apiRequest('network-map/layout/', {
        method: 'PUT', body: { positions, revision: baseRevision.current },
      });
      dirtyRef.current = false;
      setDirty(false);
      baseRevision.current = payload.data.revision;
      setData((current) => ({ ...current, layout: payload.data }));
      setError('');
      return true;
    } catch (err) {
      setError(err.message);
      return false;
    } finally {
      setBusy(false);
    }
  }

  async function mutate(path, method, body) {
    setBusy(true);
    try {
      await apiRequest(`network-map/${path}`, { method, body });
      await load();
      return true;
    } catch (err) {
      setError(err.message);
      return false;
    } finally {
      setBusy(false);
    }
  }

  return { data, positions, changePositions, discardPositions, dirty, loading, busy, error,
    load, savePositions, mutate };
}
