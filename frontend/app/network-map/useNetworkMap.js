import { useCallback, useEffect, useRef, useState } from 'react';

import { apiRequest, BACKEND_UNAVAILABLE_MESSAGE } from '../api';
import { networkMapMutationMatches } from '../utils/networkMapMutation';

const emptyMap = { devices: [], links: [], suggestions: [], unresolved: [], hidden_links: 0,
  dismissed_count: 0, layout: { positions: {}, revision: 0 }, preferences: { show_lldp_suggestions: false } };

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
      const payload = await apiRequest('network-map/', { timeoutMs: 5000 });
      if (requestVersion.current !== version) return;
      setData(payload.data);
      if (!dirtyRef.current) {
        setPositions(payload.data.layout.positions);
        baseRevision.current = payload.data.layout.revision;
      }
      setError('');
      return payload.data;
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

  function applySavedLayout(layout) {
    dirtyRef.current = false;
    setDirty(false);
    baseRevision.current = layout.revision;
    setPositions(layout.positions);
    setData((current) => ({ ...current, layout }));
    setError('');
  }

  async function reconcileMutation(path, method, body, err) {
    if ((err.status >= 400 && err.status < 500)
      || (err.status === 503 && err.message !== BACKEND_UNAVAILABLE_MESSAGE)) {
      setError(err.message);
      return null;
    }
    const snapshot = await load();
    if (snapshot && networkMapMutationMatches(snapshot, path, method, body, data)) return snapshot;
    setError('Could not confirm whether your map changes were saved. Review or refresh the map before trying again.');
    return null;
  }

  async function savePositions() {
    setBusy(true);
    const body = { positions, revision: baseRevision.current };
    try {
      const payload = await apiRequest('network-map/layout/', {
        method: 'PUT', body, timeoutMs: 8000,
      });
      applySavedLayout(payload.data);
      return true;
    } catch (err) {
      const confirmed = await reconcileMutation('layout/', 'PUT', body, err);
      if (confirmed) { applySavedLayout(confirmed.layout); return true; }
      return false;
    } finally {
      setBusy(false);
    }
  }

  async function mutate(path, method, body) {
    setBusy(true);
    try {
      await apiRequest(`network-map/${path}`, { method, body, timeoutMs: 8000 });
      await load();
      return true;
    } catch (err) {
      return Boolean(await reconcileMutation(path, method, body, err));
    } finally {
      setBusy(false);
    }
  }

  async function savePreference(showSuggestions) {
    setBusy(true);
    try {
      const payload = await apiRequest('network-map/preferences/', {
        method: 'PUT', body: { show_lldp_suggestions: showSuggestions }, timeoutMs: 5000,
      });
      setData((current) => ({ ...current, preferences: payload.data }));
      setError('');
    } catch (err) {
      try {
        const current = await apiRequest('network-map/preferences/', { timeoutMs: 3000 });
        setData((value) => ({ ...value, preferences: current.data }));
        setError(current.data.show_lldp_suggestions === showSuggestions ? '' : err.message);
      } catch {
        setError('Could not confirm whether your display preference was saved. Refresh the map before trying again.');
      }
    } finally {
      setBusy(false);
    }
  }

  return { data, positions, changePositions, discardPositions, dirty, loading, busy, error,
    load, savePositions, mutate, savePreference };
}
