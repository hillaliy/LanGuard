import assert from 'node:assert/strict';
import test from 'node:test';
import { networkMapConnections, networkMapPositions, parallelLinkLanes, networkLinkTitle } from './networkMap.js';

const devices = [{ id: 1 }, { id: 2 }, { id: 3 }];
const links = [{ id: 10, source_device: 1, target_device: 2 }, { id: 20, source_device: 2, target_device: 3 }];

test('Dagre places connected devices without overlapping', () => {
  const positions = networkMapPositions(devices, links);
  assert.equal(Object.keys(positions).length, 3);
  assert.ok(positions[1].y < positions[2].y);
  assert.ok(positions[2].y < positions[3].y);
  assert.ok(Object.values(positions).every((point) => Number.isFinite(point.x) && Number.isFinite(point.y)));
});

test('unconnected devices populate a separate grid without invented links', () => {
  const data = Array.from({ length: 9 }, (_, index) => ({ id: index + 1 }));
  const positions = networkMapPositions(data, []);
  assert.equal(Object.keys(positions).length, 9);
  assert.equal(new Set(Object.values(positions).map(({ x, y }) => `${x}:${y}`)).size, 9);
  assert.equal(positions[1].y, positions[2].y);
  assert.ok(positions[4].y > positions[1].y);
  const mixed = networkMapPositions(data, links);
  assert.ok(mixed[4].x > Math.max(mixed[1].x, mixed[2].x, mixed[3].x) + 244);
  assert.deepEqual(networkMapPositions([], []), {});
});

test('saved positions remain exact and new nodes do not cover them', () => {
  const first = networkMapPositions(devices, links);
  const saved = { 1: { ...first[2] } };
  const positions = networkMapPositions(devices, links, saved);
  assert.deepEqual(positions[1], saved[1]);
  assert.notDeepEqual(positions[2], saved[1]);
});

test('physical loops and parallel connections do not break layout', () => {
  const positions = networkMapPositions(devices, [...links, links[0], { source_device: 3, target_device: 1 }]);
  assert.equal(Object.keys(positions).length, 3);
});

test('suggestions are opt-in and do not become saved connections', () => {
  const data = { links, suggestions: [{ key: 'observation', source_device: 1, target_device: 3 }] };
  assert.equal(networkMapConnections(data).length, 2);
  const combined = networkMapConnections(data, true);
  assert.equal(combined.length, 3);
  assert.equal(combined[2].suggested, true);
  assert.equal(data.links.length, 2);
});

test('parallel links get distinct stable visual lanes', () => {
  const lanes = parallelLinkLanes([{ graphId: 'a', source_device: 1, target_device: 2 },
    { graphId: 'b', source_device: 2, target_device: 1 }]);
  assert.equal(lanes.a, -0.5);
  assert.equal(lanes.b, 0.5);
});

test('link labels use connection type and supplied ports without inventing data', () => {
  assert.equal(networkLinkTitle({ kind: 'ethernet', source_port: 'LAN 1', target_port: 'eth0' }), 'Ethernet · LAN 1 ↔ eth0');
  assert.equal(networkLinkTitle({ kind: 'unknown' }), 'Unknown');
  assert.equal(networkLinkTitle({ label: 'Uplink', kind: 'wifi' }), 'Uplink');
});
