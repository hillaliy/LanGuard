export function normalizeMacText(value) {
  return String(value || '').trim().toLowerCase();
}

export function compactMac(value) {
  return normalizeMacText(value).replace(/[:-]/g, '');
}

export function isMacAddressText(value) {
  const compact = compactMac(value);
  return compact.length === 12 && /^[0-9a-f]+$/.test(compact);
}

export function isLocallyAdministeredMac(value) {
  const compact = compactMac(value);
  if (compact.length < 2 || !/^[0-9a-f]{2}/.test(compact)) {
    return false;
  }
  return (Number.parseInt(compact.slice(0, 2), 16) & 0x02) === 0x02;
}

export function macSuffix(value) {
  return compactMac(value).slice(-4).toUpperCase();
}

export function displayDeviceName(device) {
  const name = String(device?.name || '').trim();
  if (name && !isMacAddressText(name)) {
    return name;
  }

  const suffix = macSuffix(device?.mac || name);
  if (!suffix) {
    return name || 'Unknown Device';
  }

  return isLocallyAdministeredMac(device?.mac || name)
    ? `Private Device ${suffix}`
    : `Unknown Device ${suffix}`;
}

export function formatRoleLabel(value) {
  return String(value || 'device')
    .replace(/([a-z0-9])([A-Z])/g, '$1 $2')
    .replace(/[-_]+/g, ' ')
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export function deviceStatus(device) {
  const statusValue = device?.status || (device?.online ? 'online' : 'offline');
  const labels = {
    online: 'Online',
    recently_seen: 'Recently seen',
    sleeping: 'Sleeping',
    offline: 'Offline',
  };
  const colors = {
    online: 'teal',
    recently_seen: 'blue',
    sleeping: 'yellow',
    offline: 'gray',
  };
  const dot = statusValue.replace('_', '-');
  return {
    value: statusValue,
    label: device?.status_display || labels[statusValue] || (device?.online ? 'Online' : 'Offline'),
    color: colors[statusValue] || (device?.online ? 'teal' : 'gray'),
    dot,
    reason: device?.status_reason || '',
  };
}

export function buildRoomOptions(devices = [], currentRoom = '') {
  return Array.from(
    new Set(
      [...devices.map((device) => device.room), currentRoom]
        .map((value) => String(value || '').trim())
        .filter(Boolean)
    )
  )
    .sort((left, right) => left.localeCompare(right))
    .map((value) => ({ value, label: value }));
}

export function validExternalUrl(value) {
  const candidate = String(value || '').trim();
  if (!candidate) {
    return true;
  }
  try {
    const url = new URL(candidate);
    return (
      (url.protocol === 'http:' || url.protocol === 'https:')
      && Boolean(url.hostname)
      && !url.username
      && !url.password
    );
  } catch {
    return false;
  }
}

export function externalUrlUsesIPv4(value) {
  const candidate = String(value || '').trim();
  if (!candidate || !validExternalUrl(candidate)) {
    return false;
  }
  const parts = new URL(candidate).hostname.split('.');
  return parts.length === 4 && parts.every((part) => {
    if (!/^\d{1,3}$/.test(part)) {
      return false;
    }
    const number = Number(part);
    return number >= 0 && number <= 255;
  });
}

export function resolveExternalUrl(value, deviceIp, followDeviceIp) {
  const candidate = String(value || '').trim();
  if (!followDeviceIp || !externalUrlUsesIPv4(candidate)) {
    return candidate;
  }
  try {
    const url = new URL(candidate);
    const authorityStart = candidate.indexOf('//') + 2;
    const authorityEndMatch = candidate.slice(authorityStart).search(/[/?#]/);
    const authorityEnd = authorityEndMatch === -1
      ? candidate.length
      : authorityStart + authorityEndMatch;
    const port = url.port ? `:${url.port}` : '';
    return `${candidate.slice(0, authorityStart)}${deviceIp}${port}${candidate.slice(authorityEnd)}`;
  } catch {
    return candidate;
  }
}
