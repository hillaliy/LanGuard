import test from 'node:test';
import assert from 'node:assert/strict';
import { internetSpeedtestStatus, formatInternetMetric, INTERNET_VERIFICATION_MAX_AGE_MS } from './networkInternetStatus.js';

const now = Date.parse('2026-11-07T20:00:00Z');
function payload(overrides = {}, integration = {}) {
  return { integration: { enabled: true, configured: true, available: true, ...integration },
    data: { download_mbps: 946.5, upload_mbps: 98.2, ping_ms: 5.1, packet_loss_percent: 0,
      tested_at: '2026-11-07T19:58:00Z', status: 'completed', healthy: true, ...overrides } };
}

test('only a recent positive completed Speedtest verifies access at test time', () => {
  const view = internetSpeedtestStatus(payload(), now);
  assert.equal(view.verified, true);
  assert.equal(view.label, 'Verified recently');
  assert.equal(view.download, 946.5);
  assert.match(view.explanation, /not a live or per-router/);
});

test('degraded thresholds do not imply an Internet outage', () => {
  const view = internetSpeedtestStatus(payload({ healthy: false }), now);
  assert.equal(view.verified, true);
  assert.equal(view.label, 'Degraded');
  assert.equal(view.color, 'orange');
});

test('disabled, unconfigured and unavailable integrations cannot verify Internet', () => {
  assert.equal(internetSpeedtestStatus(null, now).label, 'Manual uplink');
  assert.equal(internetSpeedtestStatus(payload({}, { enabled: false }), now).enabled, false);
  assert.equal(internetSpeedtestStatus(payload({}, { configured: false }), now).enabled, false);
  const unavailable = internetSpeedtestStatus(payload({}, { available: false }), now);
  assert.equal(unavailable.verified, false);
  assert.equal(unavailable.label, 'Unverified');
  assert.match(unavailable.explanation, /does not establish an Internet outage/);
});

test('old, invalid, missing and future timestamps do not become fresh on API refresh', () => {
  const expired = internetSpeedtestStatus(payload(), now + INTERNET_VERIFICATION_MAX_AGE_MS);
  assert.equal(expired.label, 'Last test only');
  assert.equal(expired.download, 946.5);
  for (const tested_at of ['', null, 'bad date', '2026-11-08T12:00:00Z']) {
    assert.equal(internetSpeedtestStatus(payload({ tested_at }), now).verified, false);
  }
  assert.equal(internetSpeedtestStatus(payload({ tested_at: '2026-11-07 19:58:00' }), now).verified, true);
});

test('failed status, zero measurements, ping alone and malformed numbers are not proof', () => {
  assert.equal(internetSpeedtestStatus(payload({ status: 'failed' }), now).verified, false);
  for (const value of [0, null, '', -2, true, Infinity, NaN]) {
    assert.equal(internetSpeedtestStatus(payload({ download_mbps: value, upload_mbps: value }), now).verified, false);
  }
  assert.equal(formatInternetMetric(Infinity, 'Mbps'), '-');
  assert.equal(formatInternetMetric(true, 'Mbps'), '-');
  assert.equal(formatInternetMetric(0, '%'), '0 %');
  assert.equal(formatInternetMetric(946.53, 'Mbps'), '946.5 Mbps');
});
