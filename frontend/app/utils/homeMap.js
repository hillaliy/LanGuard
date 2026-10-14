export const homeMapFilterOptions = [
  { value: 'all', label: 'All' },
  { value: 'online', label: 'Online' },
  { value: 'offline', label: 'Offline' },
  { value: 'attention', label: 'Attention' },
];

export const homeMapRoomIconOptions = [
  { value: 'home', label: 'Room' },
  { value: 'living-room', label: 'Living room' },
  { value: 'bedroom', label: 'Bedroom' },
  { value: 'kitchen', label: 'Kitchen' },
  { value: 'dining-room', label: 'Dining room' },
  { value: 'office', label: 'Office' },
  { value: 'bathroom', label: 'Bathroom' },
  { value: 'entrance', label: 'Entrance' },
  { value: 'garage', label: 'Garage' },
  { value: 'basement', label: 'Basement' },
  { value: 'garden', label: 'Garden' },
  { value: 'outside', label: 'Outside' },
  { value: 'laundry', label: 'Laundry' },
  { value: 'storage', label: 'Storage' },
  { value: 'server-room', label: 'Server or network room' },
];

export const homeMapRoomIconIds = homeMapRoomIconOptions.map((option) => option.value);
export const homeMapRoomSpanOptions = Array.from({ length: 11 }, (_, index) => index + 2);

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
    onlineCount: section.devices.filter((device) => device.online).length,
  }));
}

export function filterHomeMapRoomTree(roomTree, filter, editMode = false) {
  if (filter === 'all' || editMode) return roomTree;

  return roomTree.reduce((visibleRooms, section) => {
    const children = filterHomeMapRoomTree(section.children || [], filter, false);
    if ((section.visibleDevices || []).length > 0 || children.length > 0) {
      visibleRooms.push({ ...section, children });
    }
    return visibleRooms;
  }, []);
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
  const icons = {};
  if (layout?.icons && typeof layout.icons === 'object' && !Array.isArray(layout.icons)) {
    Object.entries(layout.icons).forEach(([room, icon]) => {
      if (typeof room === 'string' && room.trim() && homeMapRoomIconIds.includes(icon)) {
        icons[room] = icon;
      }
    });
  }
  const placements = {};
  if (
    layout?.placements
    && typeof layout.placements === 'object'
    && !Array.isArray(layout.placements)
  ) {
    Object.entries(layout.placements).forEach(([room, slot]) => {
      if (
        typeof room === 'string'
        && room.trim()
        && Number.isInteger(slot)
        && slot >= 0
        && slot <= 99
      ) {
        placements[room] = slot;
      }
    });
  }
  const sizes = {};
  const parentRooms = new Set(Object.values(parents));
  if (layout?.sizes && typeof layout.sizes === 'object' && !Array.isArray(layout.sizes)) {
    Object.entries(layout.sizes).forEach(([room, span]) => {
      if (
        typeof room === 'string'
        && room.trim()
        && homeMapRoomSpanOptions.includes(span)
      ) {
        sizes[room] = parentRooms.has(room) ? Math.max(4, span) : span;
      }
    });
  }
  return { order, parents, icons, placements, sizes };
}

export function buildHomeMapGridSlots(
  sections,
  placements = {},
  { columns = 3, includeDropRow = false } = {}
) {
  const slotsByIndex = new Map();
  const pendingSections = [];

  sections.forEach((section) => {
    const requestedSlot = placements[section.room];
    if (Number.isInteger(requestedSlot) && requestedSlot >= 0 && !slotsByIndex.has(requestedSlot)) {
      slotsByIndex.set(requestedSlot, section);
    } else {
      pendingSections.push(section);
    }
  });

  pendingSections.forEach((section) => {
    let slot = 0;
    while (slotsByIndex.has(slot)) slot += 1;
    slotsByIndex.set(slot, section);
  });

  const highestSlot = slotsByIndex.size ? Math.max(...slotsByIndex.keys()) : -1;
  let slotCount = highestSlot + 1;
  if (includeDropRow) {
    const safeColumns = Math.max(columns, 1);
    slotCount = Math.ceil(Math.max(slotCount, 1) / safeColumns) * safeColumns + safeColumns;
  }

  return Array.from({ length: slotCount }, (_, slot) => ({
    section: slotsByIndex.get(slot) || null,
    slot,
  }));
}

export function getHomeMapVisualDropIndex(target) {
  const grid = target?.parentElement;
  if (!grid) return null;
  const targetRect = target.getBoundingClientRect();
  const rooms = Array.from(grid.children).filter((element) =>
    element.classList.contains('home-map-room')
  );

  return rooms.filter((room) => {
    const roomRect = room.getBoundingClientRect();
    if (roomRect.top < targetRect.top - 4) return true;
    return Math.abs(roomRect.top - targetRect.top) <= 4
      && roomRect.left < targetRect.left;
  }).length;
}

export function moveHomeMapRoomToSlot(
  layout,
  rooms,
  sourceRoom,
  targetParent,
  targetSlot,
  targetSpan = null
) {
  if (
    !Number.isInteger(targetSlot)
    || targetSlot < 0
    || targetSlot > 99
    || sourceRoom === targetParent
    || (targetParent && isHomeMapDescendant(sourceRoom, targetParent, layout.parents))
  ) {
    return layout;
  }

  const parents = { ...layout.parents };
  const sourceParent = parents[sourceRoom] || null;
  const orderedSections = orderHomeMapRooms(rooms, layout.order);
  const targetSiblings = orderedSections.filter(
    (section) => (parents[section.room] || null) === targetParent && section.room !== sourceRoom
  );
  const targetSlots = buildHomeMapGridSlots(targetSiblings, layout.placements);
  const targetOccupant = targetSlots.find((entry) => entry.slot === targetSlot)?.section;
  const placements = { ...layout.placements };
  const sourceSlot = buildHomeMapGridSlots(
    orderedSections.filter(
      (section) => (parents[section.room] || null) === sourceParent
    ),
    layout.placements
  ).find((entry) => entry.section?.room === sourceRoom)?.slot;

  if (targetOccupant) {
    if (sourceParent === targetParent && Number.isInteger(sourceSlot)) {
      placements[targetOccupant.room] = sourceSlot;
    } else {
      const usedSlots = new Set(
        targetSlots
          .filter((entry) => entry.section?.room !== targetOccupant.room)
          .map((entry) => entry.slot)
      );
      let nextSlot = targetSlot + 1;
      while (usedSlots.has(nextSlot)) nextSlot += 1;
      if (nextSlot > 99) return layout;
      placements[targetOccupant.room] = nextSlot;
    }
  }

  placements[sourceRoom] = targetSlot;
  const sizes = { ...layout.sizes };
  if (homeMapRoomSpanOptions.includes(targetSpan)) sizes[sourceRoom] = targetSpan;
  if (targetParent) {
    parents[sourceRoom] = targetParent;
  } else {
    delete parents[sourceRoom];
  }
  return { ...layout, parents, placements, sizes };
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
