import { useCallback, useEffect, useRef, useState } from 'react';

import { apiRequest } from '../api';

function requestId() {
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  bytes[6] = (bytes[6] & 15) | 64;
  bytes[8] = (bytes[8] & 63) | 128;
  const hex = [...bytes].map((value) => value.toString(16).padStart(2, '0')).join('');
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

const emptyMap = { devices: [], links: [], suggestions: [], unresolved: [], hidden_links: 0,
  dismissed_count: 0, internet: null, layout: { positions: {}, revision: 0 }, preferences: { show_lldp_suggestions: false } };

export default function useNetworkMap() {
  const [data, setData] = useState(emptyMap);
  const [positions, setPositions] = useState({});
  const [dirty, setDirty] = useState(false);
  const dirtyRef = useRef(false);
  const draftRef = useRef({});
  const baseRevision = useRef(0);
  const requestVersion = useRef(0);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [commands, setCommands] = useState([]);
  const pendingLayoutRef = useRef(null);
  const seenResults = useRef(new Set());
  const initializedCommands = useRef(false);
  const alive = useRef(true);
  const refreshedAt = useRef(0);

  const load = useCallback(async (quiet = false) => {
    const version = ++requestVersion.current;
    if (!quiet) setLoading(true);
    try {
      const payload = await apiRequest('network-map/', { timeoutMs: 5000 });
      if (requestVersion.current !== version) return;
      setData(payload.data);
      refreshedAt.current = Date.now();
      if (!dirtyRef.current) {
        setPositions(pendingLayoutRef.current?.body.positions || payload.data.layout.positions || {});
        baseRevision.current = payload.data.layout.revision;
      }
      if (!quiet) setError('');
      return payload.data;
    } catch (err) {
      if (requestVersion.current === version && !quiet) setError(err.message);
    } finally {
      if (requestVersion.current === version) setLoading(false);
    }
  }, []);

  useEffect(() => {
    alive.current = true;
    load();
    return () => { alive.current = false; requestVersion.current++; };
  }, [load]);

  const pollCommands = useCallback(async () => {
    const payload = await apiRequest('network-map/commands/', { timeoutMs: 5000 });
    if (!alive.current) return;
    const jobs = payload.data.commands;
    setCommands((current) => current.length === jobs.length
      && current.every((job, index) => job.id === jobs[index].id && job.status === jobs[index].status) ? current : jobs);
    const pendingLayout = jobs.find((job) => job.path === 'layout/' && job.status === 'queued');
    pendingLayoutRef.current = pendingLayout || null;
    if (pendingLayout && !dirtyRef.current) setPositions(pendingLayout.body.positions);
    const completed = jobs.filter((job) => job.status !== 'queued' && !seenResults.current.has(job.id));
    completed.forEach((job) => seenResults.current.add(job.id));
    const failed = initializedCommands.current ? completed.find((job) => job.status === 'failed')
      : jobs[0]?.status === 'failed' ? jobs[0] : null;
    initializedCommands.current = true;
    const latestLayout = jobs.find((job) => job.path === 'layout/');
    const failedLayout = latestLayout?.status === 'failed' && completed.some((job) => job.id === latestLayout.id) ? latestLayout : null;
    if (failedLayout && !dirtyRef.current) {
      dirtyRef.current = true;
      setDirty(true);
      setPositions(failedLayout.body.positions);
      draftRef.current = failedLayout.body.positions;
      baseRevision.current = failedLayout.body.revision;
    }
    const savedDraft = completed.find((job) => job.path === 'layout/' && job.status === 'succeeded'
      && job.body.revision === baseRevision.current
      && Object.keys(draftRef.current).length === Object.keys(job.body.positions).length
      && Object.entries(job.body.positions).every(([id, point]) => draftRef.current[id]?.x === point.x && draftRef.current[id]?.y === point.y));
    if (savedDraft) { dirtyRef.current = false; setDirty(false); }
    if (failed) {
      setError(`A background change was not saved: ${failed.error || 'Review the save history.'}`);
    }
    if (completed.some((job) => job.status === 'succeeded') || Date.now() - refreshedAt.current > 15000) {
      await load(true);
      if (failed) setError('A background change could not be applied. Review the save history.');
    }
  }, [load]);

  useEffect(() => {
    let stopped = false;
    let timer;
    const poll = async () => {
      try { await pollCommands(); } catch { /* Keep accepted requests pending during a connection loss. */ }
      if (!stopped) timer = setTimeout(poll, 2000);
    };
    poll();
    return () => { stopped = true; clearTimeout(timer); };
  }, [pollCommands]);

  function changePositions(next) {
    draftRef.current = next;
    dirtyRef.current = true;
    setDirty(true);
    setPositions(next);
  }

  function discardPositions() {
    dirtyRef.current = false;
    setDirty(false);
    setPositions(data.layout.positions || {});
    baseRevision.current = data.layout.revision;
  }

  async function savePositions() {
    const accepted = await mutate('layout/', 'PUT', { positions, revision: baseRevision.current, mode: 'infrastructure' });
    if (accepted) {
      dirtyRef.current = false;
      setDirty(false);
      load();
    }
    return accepted;
  }

  async function mutate(path, method, body) {
    setBusy(true);
    const request = { request_id: requestId(), path, method, body: body || {} };
    try {
      let payload;
      // Retrying intake with the same ID is safe even if its first response was lost.
      for (let attempt = 0; attempt < 3; attempt++) {
        try {
          payload = await apiRequest('network-map/commands/', { method: 'POST', body: request, timeoutMs: 4000 });
          break;
        } catch (err) {
          if (attempt === 2 || (err.status >= 400 && err.status < 500)) throw err;
          await new Promise((resolve) => setTimeout(resolve, 500));
        }
      }
      const job = payload.data.command;
      if (job.status === 'failed') {
        setError('This change could not be applied. Review the save history.');
        return false;
      }
      if (alive.current) {
        setCommands((current) => [job, ...current.filter((item) => item.id !== job.id)]);
        if (path === 'layout/' && job.status === 'queued') pendingLayoutRef.current = job;
        setError('');
      }
      return true;
    } catch (err) {
      setError(`${err.message} Your change was not confirmed. Check save history before submitting it again.`);
      return false;
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

  const pending = commands.filter((job) => job.status === 'queued');
  return { data, positions, changePositions, discardPositions, dirty, loading, busy, error, commands, pending,
    load, savePositions, mutate, savePreference };
}
