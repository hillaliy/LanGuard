import dagre from '@dagrejs/dagre';

export const networkNodeWidth = 244;
export const networkNodeHeight = 116;
export const networkLinkKinds = [
  { value: 'ethernet', label: 'Ethernet' },
  { value: 'wifi', label: 'Wi-Fi' },
  { value: 'unknown', label: 'Unknown' },
];

export function networkLinkTitle(link) {
  const kind = networkLinkKinds.find((item) => item.value === link.kind)?.label || 'Unknown';
  return link.label || [kind, [link.source_port, link.target_port].filter(Boolean).join(' ↔ ')].filter(Boolean).join(' · ');
}

export function networkMapConnections(data, includeSuggestions = false) {
  return [
    ...data.links.map((link) => ({ ...link, graphId: `link-${link.id}` })),
    ...(includeSuggestions ? data.suggestions.map((link) => ({ ...link, graphId: `suggestion-${link.key}`, suggested: true })) : []),
  ];
}

export function networkMapPositions(devices, links, saved = {}) {
  if (!devices.length) return {};
  const linkedIds = new Set(links.flatMap((link) => [link.source_device, link.target_device]));
  const { groups, parents } = networkMapBranches(devices, links);
  const graph = new dagre.graphlib.Graph({ multigraph: true });
  graph.setGraph({ rankdir: 'TB', nodesep: 64, ranksep: 80, marginx: 30, marginy: 30 });
  graph.setDefaultEdgeLabel(() => ({}));
  devices.filter((device) => linkedIds.has(device.id) && !parents[device.id]).forEach((device) => {
    const count = groups[device.id]?.length || 0;
    const columns = count > 12 ? 4 : Math.min(3, Math.ceil(Math.sqrt(count)));
    graph.setNode(String(device.id), {
      width: count ? Math.max(networkNodeWidth, columns * (networkNodeWidth + 24) - 24 + 32) : networkNodeWidth,
      height: count ? networkNodeHeight + 56 + Math.ceil(count / columns) * (networkNodeHeight + 24) - 24 : networkNodeHeight,
      columns,
    });
  });
  links.forEach((link, index) => {
    if (graph.hasNode(String(link.source_device)) && graph.hasNode(String(link.target_device))
      && link.source_device !== link.target_device) {
      graph.setEdge(String(link.source_device), String(link.target_device), {}, String(index));
    }
  });
  if (graph.nodeCount()) dagre.layout(graph);
  const automatic = {};
  graph.nodes().forEach((id) => {
    const node = graph.node(id);
    const left = node.x - node.width / 2, top = node.y - node.height / 2;
    automatic[id] = { x: node.x - networkNodeWidth / 2, y: top };
    (groups[id] || []).forEach((child, index) => {
      automatic[child] = { x: left + 16 + (index % node.columns) * (networkNodeWidth + 24),
        y: top + networkNodeHeight + 56 + Math.floor(index / node.columns) * (networkNodeHeight + 24) };
    });
  });
  const connectedRight = Math.max(0, ...Object.values(automatic).map((point) => point.x + networkNodeWidth));
  const stagingX = graph.nodeCount() ? connectedRight + 100 : 30;
  const positions = {};
  const occupied = [];
  const isPosition = (value) => value && Number.isFinite(value.x) && Number.isFinite(value.y);
  devices.filter((device) => isPosition(saved[String(device.id)])).forEach((device) => {
    positions[device.id] = { ...saved[device.id] };
    occupied.push(positions[device.id]);
  });
  let unconnectedIndex = 0;
  devices.filter((device) => !positions[device.id]).forEach((device) => {
    const point = automatic[device.id];
    const index = unconnectedIndex;
    if (!point) unconnectedIndex++;
    const position = point ? { ...point }
      : { x: stagingX + (index % 3) * (networkNodeWidth + 40), y: 30 + Math.floor(index / 3) * (networkNodeHeight + 40) };
    // New devices must not cover nodes the user has already positioned.
    while (occupied.some((other) => Math.abs(other.x - position.x) < networkNodeWidth + 16
      && Math.abs(other.y - position.y) < networkNodeHeight + 24)) {
      position.y += networkNodeHeight + 60;
    }
    positions[device.id] = position;
    occupied.push(position);
  });
  return positions;
}

export function networkMapBranches(devices, links) {
  const byId = new Map(devices.map((device) => [device.id, device]));
  const adjacent = new Map(devices.map((device) => [device.id, new Set()]));
  const incoming = new Set();
  links.forEach((link) => {
    if (!byId.has(link.source_device) || !byId.has(link.target_device) || link.source_device === link.target_device) return;
    adjacent.get(link.source_device).add(link.target_device);
    adjacent.get(link.target_device).add(link.source_device);
    incoming.add(link.target_device);
  });
  const infrastructure = (device) => /^(router|meshrouter|switch|accesspoint|wirelessaccesspoint|gateway|firewall|modem|bridge)$/
    .test((device?.role || '').toLowerCase().replace(/[\s_-]/g, ''));
  const groups = {}, parents = {};
  devices.forEach((device) => {
    const peers = adjacent.get(device.id);
    if (infrastructure(device) || peers.size !== 1) return;
    const parent = [...peers][0];
    if (!incoming.has(device.id) && !infrastructure(byId.get(parent))) return;
    if (adjacent.get(parent).size === 1 && !infrastructure(byId.get(parent)) && incoming.has(parent)) return;
    parents[device.id] = parent;
    (groups[parent] ||= []).push(device.id);
  });
  return { groups, parents };
}

export function parallelLinkLanes(links) {
  const groups = new Map();
  links.forEach((link) => {
    const key = [link.source_device, link.target_device].sort((a, b) => a - b).join(':');
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(link.graphId);
  });
  return Object.fromEntries([...groups.values()].flatMap((items) =>
    items.map((id, index) => [id, index - (items.length - 1) / 2])
  ));
}
