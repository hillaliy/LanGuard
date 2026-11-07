import assert from 'node:assert/strict';
import test from 'node:test';
import { networkMapConnections, networkMapPositions, parallelLinkLanes, networkLinkTitle, networkMapBranches } from './networkMap.js';

const devices = [{ id: 1 }, { id: 2 }, { id: 3 }];
const links = [{ id: 10, source_device: 1, target_device: 2 }, { id: 20, source_device: 2, target_device: 3 }];

test('Dagre places connected devices without overlapping', () => {
  const positions = networkMapPositions(devices, links);
  assert.equal(Object.keys(positions).length, 3);
  assert.ok(positions[1].y < positions[2].y);
  assert.ok(positions[2].y < positions[3].y);
  assert.ok(Object.values(positions).every((point) => Number.isFinite(point.x) && Number.isFinite(point.y)));
});

test('large endpoint groups wrap into at most four columns rather than one wide rank', () => {
  const largeDevices = [{ id: 1, role: 'router' }, ...Array.from({ length: 60 }, (_, index) => ({ id: index + 2 }))];
  const largeLinks = largeDevices.slice(1).map((device) => ({ source_device: 1, target_device: device.id }));
  const positions = networkMapPositions(largeDevices, largeLinks);
  const clients = largeDevices.slice(1).map((device) => positions[device.id]);
  assert.equal(Object.keys(positions).length, 61);
  assert.equal(new Set(clients.map((point) => point.x)).size, 4);
  assert.ok(Math.max(...clients.map((point) => point.x)) - Math.min(...clients.map((point) => point.x)) < 1000);
  assert.ok(clients.every((point) => point.y > positions[1].y + 116));
  for (const [index, first] of Object.values(positions).entries()) {
    for (const second of Object.values(positions).slice(index + 1)) {
      assert.ok(Math.abs(first.x - second.x) >= 244 || Math.abs(first.y - second.y) >= 116);
    }
  }
});

test('branch groups preserve infrastructure, loops, multi-homed devices and parallel links', () => {
  const nodes = [{ id: 1, role: 'mesh_router' }, { id: 2, role: 'accessPoint' }, { id: 3 }, { id: 4 }, { id: 5 }];
  const edges = [[1, 2], [1, 3], [2, 3], [2, 4], [2, 4], [4, 2], [1, 5]].map(([source_device, target_device]) => ({ source_device, target_device }));
  const result = networkMapBranches(nodes, edges);
  assert.deepEqual(result.groups, { 1: [5], 2: [4] });
  assert.equal(result.parents[2], undefined);
  assert.equal(result.parents[3], undefined);
  assert.equal(edges.length, 7);
  const positions = networkMapPositions(nodes, edges, { 3: { x: -900, y: 800 }, 4: { x: 2000, y: -100 } });
  assert.deepEqual(positions[3], { x: -900, y: 800 });
  assert.deepEqual(positions[4], { x: 2000, y: -100 });
  assert.equal(Object.keys(positions).length, 5);
});

test('multiple compact hub footprints do not overlap their endpoint grids', () => {
  const nodes = [{ id: 1, role: 'router' }, { id: 2, role: 'switch' }, { id: 3, role: 'switch' }];
  const edges = [{ source_device: 1, target_device: 2 }, { source_device: 1, target_device: 3 }];
  for (let id = 4; id < 40; id++) { nodes.push({ id }); edges.push({ source_device: id < 22 ? 2 : 3, target_device: id }); }
  const positions = Object.values(networkMapPositions(nodes, edges));
  for (let i = 0; i < positions.length; i++) for (let j = i + 1; j < positions.length; j++) {
    assert.ok(Math.abs(positions[i].x - positions[j].x) >= 244 || Math.abs(positions[i].y - positions[j].y) >= 116);
  }
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
