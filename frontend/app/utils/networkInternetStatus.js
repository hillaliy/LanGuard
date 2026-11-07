import { normalizeApiDate } from './date.js';

export const INTERNET_VERIFICATION_MAX_AGE_MS = 15 * 60 * 1000;

function metric(value) {
  if (!['number', 'string'].includes(typeof value) || String(value).trim() === '') return null;
  const number = Number(value);
  return Number.isFinite(number) && number >= 0 ? number : null;
}

export function formatInternetMetric(value, unit) {
  const number = metric(value);
  return number == null ? '-' : `${new Intl.NumberFormat('en', { maximumFractionDigits: 1 }).format(number)} ${unit}`;
}

export function internetSpeedtestStatus(payload, now = Date.now()) {
  const integration = payload?.integration || {};
  const enabled = integration.enabled === true && integration.configured === true;
  const result = enabled && payload?.data && typeof payload.data === 'object' ? payload.data : {};
  const download = metric(result.download_mbps), upload = metric(result.upload_mbps);
  const ping = metric(result.ping_ms), loss = metric(result.packet_loss_percent);
  const testedAt = result.tested_at ? new Date(normalizeApiDate(result.tested_at)).getTime() : NaN;
  const age = now - testedAt;
  const recent = Number.isFinite(age) && age >= -60000 && age <= INTERNET_VERIFICATION_MAX_AGE_MS;
  const completed = ['', 'completed', 'success'].includes(String(result.status || '').toLowerCase());
  const verified = enabled && integration.available === true && recent && completed && (download > 0 || upload > 0);
  const degraded = verified && result.healthy === false;
  const label = !enabled ? 'Manual uplink' : verified ? degraded ? 'Degraded' : 'Verified recently'
    : integration.available !== true ? 'Unverified' : Number.isFinite(testedAt) ? 'Last test only' : 'Unverified';
  const explanation = !enabled ? 'No Speedtest verification is configured.'
    : verified ? 'Internet access was measured by the recent completed Speedtest. This is not a live or per-router/WAN reachability probe.'
      : integration.available !== true ? 'Speedtest Tracker could not be read. This does not establish an Internet outage.'
        : 'There is no recent completed Speedtest with a positive speed measurement to verify Internet access.';
  return { enabled, verified, degraded, label, explanation, color: verified ? degraded ? 'orange' : 'teal' : 'gray',
    download, upload, ping, loss, hasSpeeds: download != null || upload != null,
    testedAt: Number.isFinite(testedAt) ? result.tested_at : null };
}
