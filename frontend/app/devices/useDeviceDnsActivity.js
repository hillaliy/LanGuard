import { useEffect, useState } from 'react';
import { apiRequest } from '../api';
import { appendUniqueById, hasNextActivityPage } from '../utils/activity';

export default function useDeviceDnsActivity({
  activeDeviceTab,
  deviceId,
  dnsActivityEnabled,
  onError,
  setActiveDeviceTab,
}) {
  const [dnsActivity, setDnsActivity] = useState([]);
  const [dnsPagination, setDnsPagination] = useState(null);
  const [dnsSummary, setDnsSummary] = useState(null);
  const [dnsIntegration, setDnsIntegration] = useState(null);
  const [dnsSearch, setDnsSearch] = useState('');
  const [dnsFilter, setDnsFilter] = useState('all');
  const [dnsOrdering, setDnsOrdering] = useState('-last_seen');
  const [loadingDnsActivity, setLoadingDnsActivity] = useState(false);
  const [loadingMoreDnsActivity, setLoadingMoreDnsActivity] = useState(false);

  async function loadDnsActivity({ offset = 0, append = false, quiet = false } = {}) {
    if (!quiet) setLoadingDnsActivity(true);
    const params = {
      id: deviceId,
      limit: 100,
      offset,
      search: dnsSearch.trim(),
      ordering: dnsOrdering,
    };
    if (dnsFilter === 'blocked') {
      params.blocked = true;
    } else if (dnsFilter === 'allowed') {
      params.blocked = false;
    }
    try {
      const payload = await apiRequest('device/dns-activity/', { params });
      const nextActivity = payload.data || [];
      setDnsActivity((current) =>
        append ? appendUniqueById(current, nextActivity) : nextActivity
      );
      setDnsPagination(payload.pagination || null);
      setDnsSummary(payload.summary || null);
      setDnsIntegration(payload.integration || null);
    } finally {
      if (!quiet) setLoadingDnsActivity(false);
    }
  }

  useEffect(() => {
    setDnsActivity([]);
    setDnsPagination(null);
    setDnsSummary(null);
    setDnsIntegration(null);
    setDnsSearch('');
    setDnsFilter('all');
    setDnsOrdering('-last_seen');
  }, [deviceId]);

  useEffect(() => {
    if (activeDeviceTab !== 'dns') return undefined;
    const timer = window.setTimeout(() => {
      loadDnsActivity().catch((err) => onError(err));
    }, 250);
    return () => window.clearTimeout(timer);
  }, [activeDeviceTab, deviceId, dnsSearch, dnsFilter, dnsOrdering]);

  useEffect(() => {
    if (!dnsActivityEnabled && activeDeviceTab === 'dns') {
      setActiveDeviceTab('overview');
    }
  }, [activeDeviceTab, dnsActivityEnabled]);

  async function loadMoreDnsActivity() {
    if (!hasNextActivityPage(dnsPagination) || loadingMoreDnsActivity) return;
    setLoadingMoreDnsActivity(true);
    try {
      await loadDnsActivity({
        offset: dnsPagination.next_offset,
        append: true,
        quiet: true,
      });
    } catch (err) {
      onError(err);
    } finally {
      setLoadingMoreDnsActivity(false);
    }
  }

  return {
    dnsActivity,
    controller: {
      dnsActivity,
      dnsFilter,
      dnsIntegration,
      dnsOrdering,
      dnsPagination,
      dnsSearch,
      dnsSummary,
      loadMoreDnsActivity,
      loadingDnsActivity,
      loadingMoreDnsActivity,
      setDnsFilter,
      setDnsOrdering,
      setDnsSearch,
    },
  };
}
