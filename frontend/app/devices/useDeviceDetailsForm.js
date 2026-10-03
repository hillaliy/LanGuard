import { useState } from 'react';

export default function useDeviceDetailsForm() {
  const [icon, setIcon] = useState('');
  const [secondaryIcon, setSecondaryIcon] = useState('');
  const [name, setName] = useState('');
  const [role, setRole] = useState('device');
  const [room, setRoom] = useState('');
  const [known, setKnown] = useState(false);
  const [isVisitor, setIsVisitor] = useState(false);
  const [onlineNotificationPreference, setOnlineNotificationPreference] = useState('inherit');
  const [offlineNotificationPreference, setOfflineNotificationPreference] = useState('inherit');
  const [presenceExpectation, setPresenceExpectation] = useState('automatic');
  const [offlineAttentionAfterDays, setOfflineAttentionAfterDays] = useState('');
  const [comments, setComments] = useState('');
  const [externalUrl, setExternalUrl] = useState('');
  const [externalUrlFollowDeviceIp, setExternalUrlFollowDeviceIp] = useState(false);
  const [homeboxItemId, setHomeboxItemId] = useState(null);
  const [attentionAcknowledged, setAttentionAcknowledged] = useState(false);
  const [editing, setEditing] = useState(false);

  function populate(nextDevice) {
    setIcon(nextDevice?.icon || '');
    setSecondaryIcon(nextDevice?.secondary_icon || '');
    setName(nextDevice?.name || '');
    setRole(nextDevice?.role || 'device');
    setRoom(nextDevice?.room || '');
    setKnown(Boolean(nextDevice?.known));
    setIsVisitor(Boolean(nextDevice?.is_visitor));
    setOnlineNotificationPreference(nextDevice?.online_notification_preference || 'inherit');
    setOfflineNotificationPreference(nextDevice?.offline_notification_preference || 'inherit');
    setPresenceExpectation(nextDevice?.presence_expectation || 'automatic');
    setOfflineAttentionAfterDays(nextDevice?.offline_attention_after_days ?? '');
    setComments(nextDevice?.comments || '');
    setExternalUrl(
      nextDevice?.external_url_follow_device_ip
        ? nextDevice?.effective_external_url || nextDevice?.external_url || ''
        : nextDevice?.external_url || ''
    );
    setExternalUrlFollowDeviceIp(Boolean(nextDevice?.external_url_follow_device_ip));
    setHomeboxItemId(nextDevice?.homebox_item_id || null);
    setAttentionAcknowledged(Boolean(nextDevice?.attention_acknowledged));
  }

  function startEditing(detectedWebUrl = '') {
    if (!externalUrl.trim() && detectedWebUrl) {
      setExternalUrl(detectedWebUrl);
      setExternalUrlFollowDeviceIp(true);
    }
    setEditing(true);
  }

  function cancelEditing(device) {
    populate(device);
    setEditing(false);
  }

  function buildPayload() {
    return {
      icon,
      secondary_icon: secondaryIcon || '',
      name,
      role,
      room,
      known,
      is_visitor: isVisitor,
      online_notification_preference: onlineNotificationPreference,
      offline_notification_preference: offlineNotificationPreference,
      presence_expectation: presenceExpectation,
      offline_attention_after_days: ['always', 'occasional'].includes(presenceExpectation)
        ? offlineAttentionAfterDays || null
        : null,
      comments,
      external_url: externalUrl.trim(),
      external_url_follow_device_ip: externalUrlFollowDeviceIp,
      homebox_item_id: homeboxItemId,
      acknowledge_attention: known && attentionAcknowledged,
    };
  }

  return {
    attentionAcknowledged,
    buildPayload,
    cancelEditing,
    editing,
    externalUrl,
    externalUrlFollowDeviceIp,
    known,
    name,
    populate,
    setEditing,
    startEditing,
    controller: {
      attentionAcknowledged,
      comments,
      editing,
      externalUrl,
      externalUrlFollowDeviceIp,
      homeboxItemId,
      icon,
      isVisitor,
      known,
      name,
      offlineAttentionAfterDays,
      offlineNotificationPreference,
      onlineNotificationPreference,
      presenceExpectation,
      role,
      room,
      secondaryIcon,
      setAttentionAcknowledged,
      setComments,
      setExternalUrl,
      setExternalUrlFollowDeviceIp,
      setHomeboxItemId,
      setIcon,
      setIsVisitor,
      setKnown,
      setName,
      setOfflineAttentionAfterDays,
      setOfflineNotificationPreference,
      setOnlineNotificationPreference,
      setPresenceExpectation,
      setRole,
      setRoom,
      setSecondaryIcon,
    },
  };
}
