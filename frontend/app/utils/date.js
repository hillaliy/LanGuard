export function normalizeApiDate(value) {
  if (typeof value !== 'string') {
    return value;
  }
  const trimmedValue = value.trim();
  if (!trimmedValue) {
    return trimmedValue;
  }
  const normalizedValue = trimmedValue.replace(
    /^(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2}:\d{2})/,
    '$1T$2'
  );
  const hasTime = normalizedValue.includes('T');
  const hasTimezone = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(normalizedValue);
  return hasTime && !hasTimezone ? `${normalizedValue}Z` : normalizedValue;
}

export function formatDate(value, timeZone) {
  if (!value) {
    return '-';
  }
  const date = new Date(normalizeApiDate(value));
  if (Number.isNaN(date.getTime())) {
    return '-';
  }
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
    ...(timeZone ? { timeZone } : {}),
  }).format(date);
}

export function formatDuration(seconds) {
  const value = Number(seconds);
  if (!Number.isFinite(value) || value < 0) {
    return '-';
  }
  const minutes = Math.floor(value / 60);
  const remainingSeconds = Math.floor(value % 60);
  if (minutes >= 60) {
    const hours = Math.floor(minutes / 60);
    const remainingMinutes = minutes % 60;
    return `${hours}h ${remainingMinutes}m`;
  }
  if (minutes > 0) {
    return `${minutes}m ${remainingSeconds}s`;
  }
  return `${remainingSeconds}s`;
}

export function formatRelativeDate(value, now = Date.now()) {
  if (!value) return '-';
  const timestamp = new Date(normalizeApiDate(value)).getTime();
  if (!Number.isFinite(timestamp)) return '-';
  const seconds = (timestamp - now) / 1000;
  if (Math.abs(seconds) < 60) return 'Just now';
  const formatter = new Intl.RelativeTimeFormat('en', { numeric: 'always' });
  for (const [unit, length] of [['year', 31_536_000], ['month', 2_592_000], ['day', 86_400], ['hour', 3600], ['minute', 60]]) {
    if (Math.abs(seconds) >= length) {
      return formatter.format(Math.trunc(seconds / length), unit);
    }
  }
  return 'Just now';
}
