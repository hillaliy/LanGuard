import test from 'node:test';
import assert from 'node:assert/strict';
import { isInfrastructure, isMobileDevice, infrastructureGraph, infrastructurePositions, directConnections, pendingConnectionDevices, networkTopology, internetNodeHeight } from './networkInfrastructure.js';

test('infrastructure includes network and smart home hubs, never regular endpoint devices', () => {
  for (const role of ['router', 'meshRouter', 'switch', 'accessPoint', 'hub', 'smart-hub', 'Zigbee hub', 'Matter hub']) assert.ok(isInfrastructure({ role }), role);
  assert.ok(isInfrastructure({ role: 'device', icon: 'smart-hub' }));
  assert.ok(isInfrastructure({ role: 'camera', icon: 'security-camera', secondary_icon: 'smart-hub' }));
  assert.ok(isInfrastructure({ role: 'device', icon: 'cpu' }));
  assert.ok(isInfrastructure({ role: 'device', is_gateway: true }));
  assert.equal(isInfrastructure({ role: 'phone' }), false);
  assert.equal(isInfrastructure({ role: 'light' }), false);
});

test('mobile grouping uses type/icon, not IP, vendor, name or connection guesses', () => {
  for (const role of ['phone', 'tablet', 'laptop', 'smartWatch']) assert.ok(isMobileDevice({ role }));
  assert.ok(isMobileDevice({ role: 'computer', icon: 'laptop' }));
  assert.equal(isMobileDevice({ name: 'iPhone', role: 'device', vendor: 'Apple' }), false);
  assert.equal(isMobileDevice({ role: 'router', icon: 'phone' }), false);
});

test('only actual infrastructure links are drawn; existing client links are untouched', () => {
  const devices = [{ id: 1, role: 'router' }, { id: 2, role: 'hub' }, { id: 3, role: 'phone' }];
  const links = [{ id: 1, source_device: 1, target_device: 2 }, { id: 2, source_device: 1, target_device: 3 }, { id: 3, source_device: 1, target_device: 3 }];
  const graph = infrastructureGraph(devices, links);
  assert.deepEqual(graph.devices.map((device) => device.id), [1, 2]);
  assert.equal(graph.links.length, 1);
  assert.equal(links.length, 3);
  const peers = directConnections(1, devices, links);
  assert.equal(peers.length, 2);
  assert.equal(peers.find((row) => row.device.id === 3).links.length, 2);
});

test('compact positions ignore old endpoint footprints and preserve explicit infrastructure positions', () => {
  const devices = [{ id: 1, role: 'router' }, { id: 2, role: 'hub' }, { id: 3, role: 'switch' }];
  const links = [{ source_device: 1, target_device: 2 }, { source_device: 1, target_device: 3 }];
  const automatic = infrastructurePositions(devices, links);
  assert.equal(Object.keys(automatic).length, 3);
  assert.ok(automatic[2].y > automatic[1].y);
  const saved = infrastructurePositions(devices, links, { 1: { x: 50, y: 100 } });
  assert.deepEqual(saved[1], { x: 50, y: 100 });
  assert.equal(new Set(Object.values(saved).map((point) => `${point.x},${point.y}`)).size, 3);
});

test('accepted pending connections leave the unconnected picker, including merged interfaces', () => {
  const devices = [{ id: 1, interfaces: [{ id: 1 }, { id: 10 }] }, { id: 2, interfaces: [{ id: 2 }] }];
  const commands = [{ status: 'queued', pending_interfaces: [10, 2] }, { status: 'failed', pending_interfaces: [1] }];
  assert.deepEqual(pendingConnectionDevices(devices, commands), [1, 2]);
  assert.deepEqual(pendingConnectionDevices(devices, [{ status: 'failed', pending_interfaces: [1] }]), []);
});

test('disconnected infrastructure is packed into three columns instead of one long rank', () => {
  const devices = Array.from({ length: 8 }, (_, id) => ({ id: id + 1, role: 'hub' }));
  const positions = infrastructurePositions(devices, []);
  assert.equal(new Set(Object.values(positions).map((point) => point.x)).size, 3);
  assert.ok(Math.max(...Object.values(positions).map((point) => point.x)) < 700);
  assert.ok(Math.max(...Object.values(positions).map((point) => point.y)) < 500);
});

test('mobile groups use only real associations, preserve parallel links and distinguish transport', () => {
  const devices = [{ id: 1, role: 'router', name: 'Router' }, { id: 2, role: 'phone' }, { id: 3, role: 'laptop' }, { id: 4, role: 'tablet' }];
  const links = [{ id: 1, source_device: 1, target_device: 2, kind: 'wifi', origin: 'manual' },
    { id: 2, source_device: 3, target_device: 1, kind: 'ethernet', origin: 'manual' }];
  const topology = networkTopology(devices, links);
  assert.deepEqual(topology.devices.map((device) => device.id), [1, 'mobile-1-wifi', 'mobile-1-ethernet', 'mobile-unassigned']);
  assert.equal(topology.links.length, 2);
  assert.ok(!topology.links.some((link) => link.target_device === 'mobile-unassigned'));
  assert.equal(topology.devices.find((device) => device.id === 'mobile-1-wifi').mobileGroup.members.length, 1);
  assert.equal(networkTopology(devices, links, false).devices.length, 1);
  assert.equal(links.length, 2);
  const positions = infrastructurePositions(topology.devices, topology.links);
  assert.equal(Object.keys(positions).length, 4);
});

test('Internet is a saved virtual uplink, not an invented inventory or availability result', () => {
  const devices = [{ id: 1, name: 'Gateway', role: 'router' }];
  assert.equal(networkTopology(devices, [], false).devices.length, 1);
  const graph = networkTopology(devices, [], false, { enabled: true, target: 1, target_device: 1, kind: 'ethernet', revision: 1 });
  assert.equal(graph.devices.length, 2);
  assert.equal(graph.devices[1].id, 'internet');
  assert.equal(graph.devices[1].online, undefined);
  assert.equal(graph.links[0].source_device, 'internet');
  assert.equal(graph.links[0].target_device, 1);
  assert.equal(devices.length, 1);
  const unavailable = networkTopology(devices, [], true, { enabled: true, target_device: null, kind: 'unknown', revision: 2 });
  assert.equal(unavailable.links.length, 0);
  assert.ok(unavailable.devices.some((device) => device.id === 'internet'));
  assert.ok(!networkTopology(devices, [], true, { enabled: false }).devices.some((device) => device.id === 'internet'));
});

test('Internet measurement height is reserved in layout and new nodes avoid saved positions', () => {
  const graph = networkTopology([{ id: 1, role: 'router' }], [], false, { enabled: true, target_device: 1, kind: 'ethernet' });
  const positions = infrastructurePositions(graph.devices, graph.links);
  assert.ok(positions[1].y >= positions.internet.y + internetNodeHeight + 50);
  const saved = infrastructurePositions(graph.devices, graph.links, { 1: { x: 32, y: 190 } });
  assert.deepEqual(saved[1], { x: 32, y: 190 });
  assert.ok(saved.internet.y >= saved[1].y + 156 + 24 || saved.internet.y + internetNodeHeight + 24 <= saved[1].y);
});
