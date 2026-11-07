import dagre from '@dagrejs/dagre';
import { networkNodeWidth } from './networkMap.js';

export const infrastructureNodeHeight = 156;
export const internetNodeHeight = 196;
export const topologyNodeHeight = (device) => device?.internetConnection ? internetNodeHeight : infrastructureNodeHeight;

const normalized = (value) => String(value || '').toLowerCase().replace(/[\s_.-]/g, '');

export function isInfrastructure(device) {
  return Boolean(device.is_gateway) || /^(router|meshrouter|switch|accesspoint|wirelessaccesspoint|ap|gateway|firewall|modem|bridge|hub|smarthub|smarthome|smarthomehub|networkhub|zigbeehub|matterhub|threadborderrouter)$/
    .test(normalized(device.role)) || [device.icon, device.secondary_icon].some((value) =>
      ['router', 'wifirouter', 'smarthub', 'hub', 'smarthome', 'aqara', 'aqura', 'cpu',
        'point3connectedtrianglepathdotted', 'sensortagradiowavesforward', 'switch2'].includes(normalized(value)));
}

export function isMobileDevice(device) {
  return !isInfrastructure(device) && [device.role, device.icon, device.secondary_icon].some((value) =>
    /^(phone|mobile|iphone|tablet|ipad|pad|laptop|macbook|smartwatch|watch|applewatch|wearable)$/.test(normalized(value)));
}

export function directConnections(deviceId, devices, links) {
  const peers = new Map();
  links.forEach((link) => {
    const id = link.source_device === deviceId ? link.target_device : link.target_device === deviceId ? link.source_device : null;
    if (id == null || id === deviceId) return;
    if (!peers.has(id)) peers.set(id, []);
    peers.get(id).push(link);
  });
  return devices.filter((device) => peers.has(device.id)).map((device) => ({ device, links: peers.get(device.id) }));
}

export function infrastructureGraph(devices, links) {
  const visible = devices.filter(isInfrastructure);
  const ids = new Set(visible.map((device) => device.id));
  return { devices: visible, links: links.filter((link) => ids.has(link.source_device) && ids.has(link.target_device)) };
}

export function pendingConnectionDevices(devices, commands) {
  const interfaces = new Set(commands.filter((job) => job.status === 'queued').flatMap((job) => job.pending_interfaces || []));
  return devices.filter((device) => device.interfaces.some((item) => interfaces.has(item.id))).map((device) => device.id);
}

export function networkTopology(devices, links, includeMobiles = true, internet = null) {
  const infrastructure = infrastructureGraph(devices, links);
  const withInternet = (graph) => {
    if (!internet?.enabled) return graph;
    const target = devices.find((device) => device.id === internet.target_device);
    const nodes = [...graph.devices];
    if (target && !nodes.some((device) => device.id === target.id)) nodes.push(target);
    const connection = { ...internet, targetName: target?.name || '' };
    nodes.push({ id: 'internet', name: 'Internet', interfaces: [], role: 'internet', internetConnection: connection });
    const uplink = target ? [{ id: 'internet-uplink', graphId: 'internet-uplink', source_device: 'internet', target_device: target.id,
      kind: internet.kind, origin: 'manual', source_port: '', target_port: '', label: 'Internet uplink', internetConnection: connection }] : [];
    return { devices: nodes, links: [...graph.links, ...uplink] };
  };
  if (!includeMobiles) return withInternet(infrastructure);
  const infrastructureIds = new Set(infrastructure.devices.map((device) => device.id));
  const groups = new Map();
  devices.filter(isMobileDevice).forEach((device) => {
    const associations = links.filter((link) => !link.suggested && ((link.source_device === device.id && infrastructureIds.has(link.target_device))
      || (link.target_device === device.id && infrastructureIds.has(link.source_device))));
    const memberships = associations.length ? associations : [null];
    memberships.forEach((link) => {
      const parent = link ? link.source_device === device.id ? link.target_device : link.source_device : null;
      const kind = link?.kind || 'unknown';
      const id = parent == null ? 'mobile-unassigned' : `mobile-${parent}-${kind}`;
      if (!groups.has(id)) groups.set(id, { id, parent, kind, members: new Map(), links: [] });
      const group = groups.get(id);
      group.members.set(device.id, device);
      if (link) group.links.push(link);
    });
  });
  const nodes = [], edges = [];
  groups.forEach((group) => {
    const members = [...group.members.values()];
    const parent = devices.find((device) => device.id === group.parent);
    const title = parent ? `${parent.name} · Mobile devices` : 'Unassigned mobile devices';
    nodes.push({ id: group.id, name: title, role: 'mobileGroup', icon: 'phone', interfaces: [],
      online: members.some((device) => device.online), mobileGroup: { ...group, members, title } });
    if (parent) edges.push({ graphId: group.id, id: group.id, source_device: parent.id, target_device: group.id,
      kind: group.kind, source_port: '', target_port: '', label: `${group.kind === 'wifi' ? 'Wi-Fi' : group.kind === 'ethernet' ? 'Ethernet' : 'Unknown'} · ${members.length} mobile`,
      origin: group.links.every((link) => link.origin === 'lldp') ? 'lldp' : 'manual', stale: group.links.every((link) => link.stale),
      mobileGroup: { members, title } });
  });
  return withInternet({ devices: [...infrastructure.devices, ...nodes], links: [...infrastructure.links, ...edges] });
}

export function infrastructurePositions(devices, links, saved = {}, columns = 3) {
  const byId = new Map(devices.map((device) => [String(device.id), device]));
  const height = (id) => topologyNodeHeight(byId.get(String(id)));
  const overlaps = (id, point, otherId, other) => Math.abs(other.x - point.x) < networkNodeWidth + 24
    && point.y < other.y + height(otherId) + 24 && point.y + height(id) + 24 > other.y;
  const adjacent = new Map([...byId.keys()].map((id) => [id, new Set()]));
  links.forEach((link) => {
    const source = String(link.source_device), target = String(link.target_device);
    if (adjacent.has(source) && adjacent.has(target)) {
      adjacent.get(source).add(target); adjacent.get(target).add(source);
    }
  });
  const visited = new Set(), components = [];
  byId.forEach((device, id) => {
    if (visited.has(id)) return;
    const component = [], pending = [id];
    visited.add(id);
    while (pending.length) {
      const current = pending.pop(); component.push(current);
      adjacent.get(current).forEach((peer) => { if (!visited.has(peer)) { visited.add(peer); pending.push(peer); } });
    }
    components.push(component);
  });
  const gap = 40, laneWidth = networkNodeWidth + gap, heights = Array(columns).fill(32), automatic = {};
  components.sort((a, b) => b.length - a.length).forEach((component) => {
    if (component.length === 1) {
      const rows = [...new Set([32, ...Object.entries(automatic).map(([id, point]) => point.y + height(id) + gap)])].sort((a, b) => a - b);
      let placed = false;
      for (const y of rows) {
        for (let column = 0; column < columns; column++) {
          const point = { x: 32 + column * laneWidth, y };
          if (!Object.entries(automatic).some(([id, other]) => overlaps(component[0], point, id, other))) {
            automatic[component[0]] = point;
            placed = true;
            break;
          }
        }
        if (placed) break;
      }
      return;
    }
    const layout = (direction) => {
      const graph = new dagre.graphlib.Graph({ multigraph: true });
      graph.setGraph({ rankdir: direction, nodesep: 32, ranksep: 72, marginx: 0, marginy: 0 });
      graph.setDefaultEdgeLabel(() => ({}));
      component.forEach((id) => graph.setNode(id, { width: networkNodeWidth, height: height(id) }));
      links.forEach((link, index) => {
        if (graph.hasNode(String(link.source_device)) && graph.hasNode(String(link.target_device)))
          graph.setEdge(String(link.source_device), String(link.target_device), {}, String(index));
      });
      dagre.layout(graph);
      return graph;
    };
    let graph = layout('TB');
    if (graph.graph().width > columns * laneWidth && component.length > 3) {
      const horizontal = layout('LR');
      const score = (candidate) => Math.max(candidate.graph().width / (columns * laneWidth), candidate.graph().height / 750);
      if (score(horizontal) < score(graph)) graph = horizontal;
    }
    const span = Math.min(columns, Math.max(1, Math.ceil((graph.graph().width + gap) / laneWidth)));
    let lane = 0, top = Infinity;
    for (let start = 0; start <= columns - span; start++) {
      const y = Math.max(...heights.slice(start, start + span));
      if (y < top) { top = y; lane = start; }
    }
    component.forEach((id) => {
      const node = graph.node(id);
      automatic[id] = { x: 32 + lane * laneWidth + node.x - networkNodeWidth / 2, y: top + node.y - height(id) / 2 };
    });
    for (let index = lane; index < lane + span; index++) heights[index] = top + graph.graph().height + gap;
  });
  const result = {};
  devices.forEach((device) => {
    const point = saved[device.id];
    if (point && Number.isFinite(point.x) && Number.isFinite(point.y)) result[device.id] = { ...point };
  });
  devices.forEach((device) => {
    if (result[device.id]) return;
    const point = { ...automatic[device.id] };
    let collision = Object.entries(result).find(([id, other]) => overlaps(device.id, point, id, other));
    while (collision) {
      point.y = collision[1].y + height(collision[0]) + 24;
      collision = Object.entries(result).find(([id, other]) => overlaps(device.id, point, id, other));
    }
    result[device.id] = point;
  });
  return result;
}
