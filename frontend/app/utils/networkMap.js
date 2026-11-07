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
  const graph = new dagre.graphlib.Graph({ multigraph: true });
  graph.setGraph({ rankdir: 'TB', nodesep: 48, ranksep: 90, marginx: 30, marginy: 30 });
  graph.setDefaultEdgeLabel(() => ({}));
  devices.filter((device) => linkedIds.has(device.id)).forEach((device) => graph.setNode(String(device.id), { width: networkNodeWidth, height: networkNodeHeight }));
  links.forEach((link, index) => {
    if (graph.hasNode(String(link.source_device)) && graph.hasNode(String(link.target_device))
      && link.source_device !== link.target_device) {
      graph.setEdge(String(link.source_device), String(link.target_device), {}, String(index));
    }
  });
  if (graph.nodeCount()) dagre.layout(graph);
  const connectedRight = Math.max(0, ...graph.nodes().map((id) => graph.node(id).x + networkNodeWidth / 2));
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
    const node = graph.node(String(device.id));
    const index = unconnectedIndex;
    if (!node) unconnectedIndex++;
    const position = node ? { x: node.x - networkNodeWidth / 2, y: node.y - networkNodeHeight / 2 }
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
