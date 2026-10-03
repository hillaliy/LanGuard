import { useEffect, useState } from 'react';
import { apiRequest } from '../api';
import { appendUniqueById, hasNextActivityPage } from '../utils/activity';

export default function useDeviceHistory({ activeDeviceTab, deviceId, onError }) {
  const [events, setEvents] = useState([]);
  const [eventPagination, setEventPagination] = useState(null);
  const [availabilityPeriod, setAvailabilityPeriod] = useState('week');
  const [availability, setAvailability] = useState(null);
  const [loadingAvailability, setLoadingAvailability] = useState(false);
  const [loadingMoreEvents, setLoadingMoreEvents] = useState(false);

  function hydrateEvents(payload) {
    setEvents(payload.data || []);
    setEventPagination(payload.pagination || null);
  }

  async function loadDeviceEvents({ offset = 0, append = false } = {}) {
    const payload = await apiRequest('events/', {
      params: { device: deviceId, limit: 100, offset },
    });
    const nextEvents = payload.data || [];
    setEvents((current) => (append ? appendUniqueById(current, nextEvents) : nextEvents));
    setEventPagination(payload.pagination || null);
  }

  useEffect(() => {
    setAvailabilityPeriod('week');
    setAvailability(null);
  }, [deviceId]);

  useEffect(() => {
    if (activeDeviceTab !== 'history') return undefined;
    let active = true;
    setLoadingAvailability(true);
    apiRequest('device/availability/', {
      params: { device: deviceId, period: availabilityPeriod },
    })
      .then((payload) => {
        if (active) setAvailability(payload.data || null);
      })
      .catch((err) => {
        if (active) onError(err);
      })
      .finally(() => {
        if (active) setLoadingAvailability(false);
      });
    return () => {
      active = false;
    };
  }, [activeDeviceTab, availabilityPeriod, deviceId]);

  async function loadMoreEvents() {
    if (!hasNextActivityPage(eventPagination) || loadingMoreEvents) return;
    setLoadingMoreEvents(true);
    try {
      await loadDeviceEvents({ offset: eventPagination.next_offset, append: true });
    } catch (err) {
      onError(err);
    } finally {
      setLoadingMoreEvents(false);
    }
  }

  return {
    hydrateEvents,
    controller: {
      availability,
      availabilityPeriod,
      eventPagination,
      events,
      loadMoreEvents,
      loadingAvailability,
      loadingMoreEvents,
      setAvailabilityPeriod,
    },
  };
}
