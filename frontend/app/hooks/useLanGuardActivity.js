import { useEffect, useState } from 'react';
import { apiRequest } from '../api';
import { appendUniqueById, hasNextActivityPage } from '../utils/activity';
import { showErrorNotification } from '../utils/notifications';

const activityPageLimit = 500;

export function useLanGuardActivity({ mainView, eventType }) {
  const [scanRuns, setScanRuns] = useState([]);
  const [scanRunPagination, setScanRunPagination] = useState(null);
  const [dashboardEvents, setDashboardEvents] = useState([]);
  const [events, setEvents] = useState([]);
  const [eventPagination, setEventPagination] = useState(null);
  const [notifications, setNotifications] = useState([]);
  const [notificationPagination, setNotificationPagination] = useState(null);
  const [activityLoadingMore, setActivityLoadingMore] = useState({
    events: false,
    scanRuns: false,
    notifications: false,
  });

  async function loadEventsData({ notifyOnError = false, offset = 0, append = false } = {}) {
    try {
      const payload = await apiRequest('events/', {
        params: { event_type: eventType || undefined, limit: activityPageLimit, offset },
      });
      const nextEvents = payload.data || [];
      setEvents((current) => (append ? appendUniqueById(current, nextEvents) : nextEvents));
      setEventPagination(payload.pagination || null);
    } catch (err) {
      if (notifyOnError) showErrorNotification(err);
    }
  }

  async function loadScanRunsData({ notifyOnError = false, offset = 0, append = false } = {}) {
    try {
      const payload = await apiRequest('scan/runs/', {
        params: { limit: activityPageLimit, offset },
      });
      const nextRuns = payload.data || [];
      setScanRuns((current) => (append ? appendUniqueById(current, nextRuns) : nextRuns));
      setScanRunPagination(payload.pagination || null);
    } catch (err) {
      if (notifyOnError) showErrorNotification(err);
    }
  }

  async function loadNotificationsData({
    notifyOnError = false,
    offset = 0,
    append = false,
  } = {}) {
    try {
      const payload = await apiRequest('notifications/', {
        params: { limit: activityPageLimit, offset },
      });
      const nextNotifications = payload.data || [];
      setNotifications((current) => (
        append ? appendUniqueById(current, nextNotifications) : nextNotifications
      ));
      setNotificationPagination(payload.pagination || null);
    } catch (err) {
      if (notifyOnError) showErrorNotification(err);
    }
  }

  async function loadMoreEventsData() {
    if (!hasNextActivityPage(eventPagination) || activityLoadingMore.events) return;
    setActivityLoadingMore((current) => ({ ...current, events: true }));
    try {
      await loadEventsData({
        notifyOnError: true,
        offset: eventPagination.next_offset,
        append: true,
      });
    } finally {
      setActivityLoadingMore((current) => ({ ...current, events: false }));
    }
  }

  async function loadMoreScanRunsData() {
    if (!hasNextActivityPage(scanRunPagination) || activityLoadingMore.scanRuns) return;
    setActivityLoadingMore((current) => ({ ...current, scanRuns: true }));
    try {
      await loadScanRunsData({
        notifyOnError: true,
        offset: scanRunPagination.next_offset,
        append: true,
      });
    } finally {
      setActivityLoadingMore((current) => ({ ...current, scanRuns: false }));
    }
  }

  async function loadMoreNotificationsData() {
    if (!hasNextActivityPage(notificationPagination) || activityLoadingMore.notifications) return;
    setActivityLoadingMore((current) => ({ ...current, notifications: true }));
    try {
      await loadNotificationsData({
        notifyOnError: true,
        offset: notificationPagination.next_offset,
        append: true,
      });
    } finally {
      setActivityLoadingMore((current) => ({ ...current, notifications: false }));
    }
  }

  useEffect(() => {
    if (mainView === 'events') loadEventsData({ notifyOnError: true });
  }, [mainView, eventType]);

  useEffect(() => {
    if (mainView === 'history') loadScanRunsData({ notifyOnError: true });
  }, [mainView]);

  useEffect(() => {
    if (mainView === 'notifications') loadNotificationsData({ notifyOnError: true });
  }, [mainView]);

  return {
    scanRuns, scanRunPagination, dashboardEvents, setDashboardEvents,
    events, eventPagination, notifications, notificationPagination,
    activityLoadingMore, loadMoreEventsData, loadMoreScanRunsData,
    loadMoreNotificationsData,
  };
}
