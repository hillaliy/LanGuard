import assert from 'node:assert/strict';
import test from 'node:test';
import { networkMapMutationMatches as matches } from './networkMapMutation.js';

const first = { source: 1, target: 2, source_port: 'LAN 1', target_port: 'eth0', kind: 'ethernet', label: '' };
const second = { source: 1, target: 3, kind: 'wifi' };
const snapshot = { links: [{ ...first, id: 10, revision: 2, origin: 'manual' }], suggestions: [], dismissed_count: 0,
  layout: { revision: 2, positions: { 1: { x: 5, y: 10 } } } };

test('lost bulk responses are confirmed only if every connection is present', () => {
  assert.equal(matches(snapshot, 'links/bulk/', 'POST', { connections: [first, second] }), false);
  assert.equal(matches({ ...snapshot, links: [...snapshot.links, second] }, 'links/bulk/', 'POST', { connections: [first, second] }), true);
  assert.equal(matches(snapshot, 'links/bulk/', 'POST', { connections: [] }), false);
});

test('connection reconciliation compares actual interfaces, ports, type and label', () => {
  assert.equal(matches(snapshot, 'links/', 'POST', first), true);
  assert.equal(matches(snapshot, 'links/', 'POST', { ...first, source: 2, target: 1, source_port: 'eth0', target_port: 'LAN 1' }), true);
  for (const change of [{ target: 40 }, { source_port: 'LAN 2' }, { kind: 'wifi' }, { label: 'different' }]) {
    assert.equal(matches(snapshot, 'links/', 'POST', { ...first, ...change }), false);
  }
});

test('edit confirmation requires a newer revision and the requested values', () => {
  assert.equal(matches(snapshot, 'links/10/', 'PUT', { ...first, revision: 1 }), true);
  assert.equal(matches(snapshot, 'links/10/', 'PUT', { ...first, revision: 2 }), false);
  assert.equal(matches(snapshot, 'links/10/', 'PUT', { ...first, revision: 1, label: 'not saved' }), false);
  assert.equal(matches(snapshot, 'links/10/', 'DELETE', { revision: 1 }), false);
  assert.equal(matches(snapshot, 'links/11/', 'DELETE', { revision: 1 }), true);
});

test('layout drafts are confirmed only by newer matching server coordinates', () => {
  assert.equal(matches(snapshot, 'layout/', 'PUT', { revision: 1, positions: { 1: { x: 5, y: 10 } } }), true);
  assert.equal(matches(snapshot, 'layout/', 'PUT', { revision: 2, positions: { 1: { x: 5, y: 10 } } }), false);
  assert.equal(matches(snapshot, 'layout/', 'PUT', { revision: 1, positions: { 1: { x: 6, y: 10 } } }), false);
});

test('suggestion confirmation does not confuse manual links with LLDP evidence', () => {
  const previous = { suggestions: [{ ...first, key: 'key' }] };
  assert.equal(matches(snapshot, 'suggestions/key/accept/', 'POST', undefined, previous), false);
  assert.equal(matches({ ...snapshot, links: [{ ...first, origin: 'lldp' }] }, 'suggestions/key/accept/', 'POST', undefined, previous), true);
  assert.equal(matches(snapshot, 'suggestions/key/dismiss/', 'POST', undefined, previous), true);
  assert.equal(matches(snapshot, 'suggestions/restored/', 'DELETE'), true);
  assert.equal(matches(snapshot, 'unrecognized/', 'POST', {}, previous), false);
});
