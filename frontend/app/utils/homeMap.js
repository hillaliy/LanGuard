export const homeMapFilterOptions = [
  { value: 'all', label: 'All' },
  { value: 'online', label: 'Online' },
  { value: 'offline', label: 'Offline' },
];

export const unassignedRoomLabel = 'Unassigned';
export const homeMapLayoutStorageKey = 'languard_home_map_layout_v1';

function getDeviceRoomLabel(device) {
  const room = String(device.room || '').trim();
  return room || unassignedRoomLabel;
}

function buildRoomSections(devices) {
  const sectionsByRoom = new Map();
  devices.forEach((device) => {
    const room = getDeviceRoomLabel(device);
    if (!sectionsByRoom.has(room)) sectionsByRoom.set(room, []);
    sectionsByRoom.get(room).push(device);
  });
  return Array.from(sectionsByRoom.entries())
    .map(([room, roomDevices]) => ({
      room,
      devices: roomDevices.sort((left, right) =>
        String(left.name || left.ip || '').localeCompare(String(right.name || right.ip || ''))
      ),
    }))
    .sort((left, right) => {
      if (left.room === unassignedRoomLabel) return 1;
      if (right.room === unassignedRoomLabel) return -1;
      return left.room.localeCompare(right.room);
    });
}

export function homeMapDeviceStatusClass(device) {
  const risk = String(device.risk || '').toLowerCase();
  if (risk === 'high') return 'high-risk';
  if (risk === 'medium') return 'medium-risk';
  if (!device.online) return 'offline';
  return 'healthy';
}

function homeMapAttentionCount(devices = []) {
  return devices.filter((device) => {
    const risk = String(device.risk || '').toLowerCase();
    return !device.online || risk === 'medium' || risk === 'high';
  }).length;
}

function homeMapDeviceMatchesFilter(device, filter) {
  const risk = String(device.risk || '').toLowerCase();
  if (filter === 'online') return Boolean(device.online);
  if (filter === 'offline') return !device.online;
  if (filter === 'attention') {
    return !device.online || risk === 'medium' || risk === 'high';
  }
  return true;
}

export function buildHomeMapRooms(devices, filter = 'all') {
  return buildRoomSections(devices.filter((device) => !device.is_visitor)).map((section) => ({
    ...section,
    visibleDevices: section.devices.filter((device) => homeMapDeviceMatchesFilter(device, filter)),
    attentionCount: homeMapAttentionCount(section.devices),
  }));
}

export function normalizeHomeMapLayout(layout, rooms) {
  const roomNames = new Set(rooms.map((section) => section.room));
  const order = Array.isArray(layout?.order)
    ? layout.order.filter((room, index, values) =>
      roomNames.has(room) && values.indexOf(room) === index
    )
    : [];
  rooms.forEach((section) => {
    if (!order.includes(section.room)) order.push(section.room);
  });

  const parents = {};
  if (layout?.parents && typeof layout.parents === 'object') {
    Object.entries(layout.parents).forEach(([room, parent]) => {
      if (roomNames.has(room) && roomNames.has(parent) && room !== parent) parents[room] = parent;
    });
  }
  Object.keys(parents).forEach((room) => {
    const seen = new Set([room]);
    let parent = parents[room];
    while (parent) {
      if (seen.has(parent)) {
        delete parents[room];
        return;
      }
      seen.add(parent);
      parent = parents[parent];
    }
  });
  return { order, parents };
}

export function orderHomeMapRooms(rooms, order) {
  const orderIndex = new Map(order.map((room, index) => [room, index]));
  return [...rooms].sort((left, right) => {
    const leftIndex = orderIndex.has(left.room) ? orderIndex.get(left.room) : Number.MAX_SAFE_INTEGER;
    const rightIndex = orderIndex.has(right.room) ? orderIndex.get(right.room) : Number.MAX_SAFE_INTEGER;
    if (leftIndex !== rightIndex) return leftIndex - rightIndex;
    return left.room.localeCompare(right.room);
  });
}

export function isHomeMapDescendant(room, maybeDescendant, parents) {
  let current = parents[maybeDescendant];
  while (current) {
    if (current === room) return true;
    current = parents[current];
  }
  return false;
}
