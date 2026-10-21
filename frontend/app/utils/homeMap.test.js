import assert from 'node:assert/strict';
import test from 'node:test';

import {
  buildHomeMapGridSlots,
  buildHomeMapRooms,
  filterHomeMapRoomTree,
  getHomeMapVisualDropIndex,
  homeMapDeviceStatusClass,
  moveHomeMapRoomToSlot,
  normalizeHomeMapLayout,
} from './homeMap.js';

const devices = [
  { id: 1, name: 'Online laptop', room: 'Office', online: true, risk_level: 'low', needs_attention: false },
  { id: 2, name: 'Offline printer', room: 'Office', online: false, risk_level: 'low', needs_attention: true },
  { id: 3, name: 'Risky server', room: 'Lab', online: true, risk_level: 'high', needs_attention: true },
];

test('attention uses server decisions independently of offline status and risk', () => {
  const inventory = [
    { id: 1, room: 'Office', online: false, needs_attention: false, risk_level: 'low' },
    { id: 2, room: 'Office', online: false, needs_attention: true, risk_level: 'low' },
    { id: 3, room: 'Office', online: true, needs_attention: true, risk_level: 'high' },
    { id: 4, room: 'Office', online: true, needs_attention: false, risk_level: 'high', attention_acknowledged: true },
    { id: 5, room: 'Office', online: true, needs_attention: true, risk_level: 'low' },
    { id: 6, room: 'Office', online: true, needs_attention: true, is_visitor: true },
  ];
  const attention = buildHomeMapRooms(inventory, 'attention')[0];
  const offline = buildHomeMapRooms(inventory, 'offline')[0];
  assert.deepEqual(attention.visibleDevices.map((device) => device.id), [2, 3, 5]);
  assert.deepEqual(offline.visibleDevices.map((device) => device.id), [1, 2]);
  assert.equal(attention.attentionCount, 3);
  assert.equal(offline.attentionCount, 3);
  assert.equal(attention.devices.length, 5);
});

test('home map risk indicators read the API risk_level field', () => {
  assert.equal(homeMapDeviceStatusClass({ online: true, risk_level: 'high' }), 'high-risk');
  assert.equal(homeMapDeviceStatusClass({ online: true, risk_level: 'medium' }), 'medium-risk');
  assert.equal(homeMapDeviceStatusClass({ online: false, risk_level: 'low' }), 'offline');
});

test('buildHomeMapRooms keeps full room counts while filtering visible devices', () => {
  const rooms = buildHomeMapRooms(devices, 'attention');
  const office = rooms.find((room) => room.room === 'Office');
  const lab = rooms.find((room) => room.room === 'Lab');

  assert.equal(office.devices.length, 2);
  assert.equal(office.visibleDevices.length, 1);
  assert.equal(office.onlineCount, 1);
  assert.equal(office.attentionCount, 1);
  assert.equal(lab.visibleDevices.length, 1);
  assert.equal(lab.attentionCount, 1);
});

test('filterHomeMapRoomTree hides empty rooms and retains parents of matching rooms', () => {
  const roomTree = [
    {
      room: 'Ground floor',
      visibleDevices: [],
      children: [
        { room: 'Office', visibleDevices: [devices[1]], children: [] },
      ],
    },
    { room: 'Garage', visibleDevices: [], children: [] },
  ];

  const filtered = filterHomeMapRoomTree(roomTree, 'offline');

  assert.deepEqual(filtered.map((room) => room.room), ['Ground floor']);
  assert.deepEqual(filtered[0].children.map((room) => room.room), ['Office']);
  assert.equal(filterHomeMapRoomTree(roomTree, 'offline', true), roomTree);
});

test('normalizeHomeMapLayout preserves valid icons for temporarily absent rooms', () => {
  const normalized = normalizeHomeMapLayout(
    {
      order: ['Office', 'Missing room'],
      parents: { Office: 'Missing room' },
      icons: {
        Office: 'office',
        'Missing room': 'storage',
        Invalid: 'custom-svg',
      },
      placements: {
        Office: 4,
        'Missing room': 2,
        Invalid: -1,
      },
      sizes: {
        Office: 4,
        'Missing room': 8,
        Invalid: 1,
      },
    },
    [{ room: 'Office' }]
  );

  assert.deepEqual(normalized.order, ['Office']);
  assert.deepEqual(normalized.parents, {});
  assert.deepEqual(normalized.icons, {
    Office: 'office',
    'Missing room': 'storage',
  });
  assert.deepEqual(normalized.placements, {
    Office: 4,
    'Missing room': 2,
  });
  assert.deepEqual(normalized.sizes, {
    Office: 4,
    'Missing room': 8,
  });
});

test('normalizeHomeMapLayout upgrades layouts that predate room icons', () => {
  const normalized = normalizeHomeMapLayout(
    { order: ['Office'], parents: {} },
    [{ room: 'Office' }]
  );

  assert.deepEqual(normalized, {
    order: ['Office'],
    parents: {},
    icons: {},
    placements: {},
    sizes: {},
  });
});

test('normalizeHomeMapLayout keeps parent rooms wide enough for nested rooms', () => {
  const normalized = normalizeHomeMapLayout({
    order: ['Floor', 'Bedroom'],
    parents: { Bedroom: 'Floor' },
    sizes: { Floor: 2, Bedroom: 3 },
  }, [
    { room: 'Floor' },
    { room: 'Bedroom' },
  ]);

  assert.equal(normalized.sizes.Floor, 4);
  assert.equal(normalized.sizes.Bedroom, 3);
});

test('buildHomeMapGridSlots preserves empty positions and adds a complete drop row', () => {
  const office = { room: 'Office' };
  const kitchen = { room: 'Kitchen' };

  const slots = buildHomeMapGridSlots(
    [office, kitchen],
    { Office: 0, Kitchen: 4 },
    { columns: 3, includeDropRow: true }
  );

  assert.equal(slots.length, 9);
  assert.equal(slots[0].section, office);
  assert.equal(slots[1].section, null);
  assert.equal(slots[4].section, kitchen);
  assert.equal(slots[8].section, null);
});

test('moveHomeMapRoomToSlot swaps occupied positions within the same room group', () => {
  const rooms = [{ room: 'Kitchen' }, { room: 'Shir' }, { room: 'Ori' }];
  const layout = {
    order: ['Kitchen', 'Shir', 'Ori'],
    parents: { Shir: 'Floor', Ori: 'Floor' },
    icons: {},
    placements: { Shir: 0, Ori: 3 },
    sizes: {},
  };

  const moved = moveHomeMapRoomToSlot(layout, rooms, 'Ori', 'Floor', 0);

  assert.deepEqual(moved.placements, { Shir: 3, Ori: 0 });
  assert.deepEqual(moved.parents, layout.parents);
});

test('moveHomeMapRoomToSlot moves a room into an empty saved grid position', () => {
  const rooms = [{ room: 'Kitchen' }, { room: 'Shir' }, { room: 'Ori' }];
  const layout = {
    order: ['Kitchen', 'Shir', 'Ori'],
    parents: { Kitchen: 'Floor', Shir: 'Floor', Ori: 'Floor' },
    icons: {},
    placements: { Kitchen: 2, Shir: 0, Ori: 1 },
    sizes: {},
  };

  const moved = moveHomeMapRoomToSlot(layout, rooms, 'Shir', 'Floor', 5, 4);

  assert.equal(moved.placements.Shir, 5);
  assert.equal(moved.placements.Kitchen, 2);
  assert.equal(moved.sizes.Shir, 4);
});

test('getHomeMapVisualDropIndex uses the rendered position of dense-grid targets', () => {
  const room = (top, left) => ({
    classList: { contains: (name) => name === 'home-map-room' },
    getBoundingClientRect: () => ({ top, left }),
  });
  const target = {
    parentElement: { children: [room(0, 0), room(0, 300), room(220, 0)] },
    getBoundingClientRect: () => ({ top: 0, left: 700 }),
  };

  assert.equal(getHomeMapVisualDropIndex(target), 2);
});
