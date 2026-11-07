'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Accordion, ActionIcon, Alert, Badge, Box, Button, Drawer, Group, Loader, Modal,
  Paper, Select, SimpleGrid, Stack, Switch, Text, Title, Tooltip, UnstyledButton,
} from '@mantine/core';
import { useMediaQuery } from '@mantine/hooks';
import {
  ReactFlow, ReactFlowProvider, Controls, MiniMap, useNodesState, useReactFlow, getViewportForBounds,
} from '@xyflow/react';
import { DndContext, DragOverlay, KeyboardSensor, MouseSensor, TouchSensor,
  pointerWithin, rectIntersection, useSensor, useSensors, MeasuringStrategy } from '@dnd-kit/core';
import { IconArrowUpRight, IconCheck, IconLayoutDistributeHorizontal, IconPencil, IconPlus,
  IconRefresh, IconRestore, IconTopologyStar, IconTrash, IconX, IconFocus2, IconListDetails, IconDeviceMobile, IconWorldPlus, IconWorld } from '@tabler/icons-react';

import { DeviceField } from '../devices/DeviceDetailFields';
import { formatDate } from '../utils/date';
import { networkLinkTitle, networkMapConnections, networkNodeWidth, parallelLinkLanes } from '../utils/networkMap';
import { networkTopology, infrastructurePositions, topologyNodeHeight,
  directConnections, isInfrastructure, isMobileDevice, pendingConnectionDevices } from '../utils/networkInfrastructure';
import DeviceIconStack from '../components/DeviceIconStack';
import NetworkDevicesModal from './NetworkDevicesModal';
import { NetworkConnectionEdge, NetworkDeviceNode, NetworkMobileNode, NetworkInternetNode } from './NetworkMapElements';
import NetworkInternetForm from './NetworkInternetForm';
import NetworkLinkForm from './NetworkLinkForm';
import NetworkBulkForm from './NetworkBulkForm';
import NetworkDeviceInventory from './NetworkDeviceInventory';
import NetworkLinkQuickEdit from './NetworkLinkQuickEdit';
import useNetworkMap from './useNetworkMap';

const nodeTypes = { device: NetworkDeviceNode, mobile: NetworkMobileNode, internet: NetworkInternetNode };
const edgeTypes = { connection: NetworkConnectionEdge };

function connectionDropTargets(args) {
  const filtered = { ...args, droppableContainers: args.droppableContainers.filter((container) =>
    container.data.current?.deviceId !== args.active.data.current?.deviceId) };
  return args.pointerCoordinates ? pointerWithin(filtered) : rectIntersection(filtered);
}

function MapWorkspace({ canEditLinks, canEditLayout, onSelectDevice, timeZone, speedtestTrackerPayload }) {
  const map = useNetworkMap();
  const flow = useReactFlow();
  const canvasRef = useRef(null);
  const initializedViewport = useRef(false);
  const canvasSize = useRef(null);
  const nodeDragging = useRef(false);
  const [clientModal, setClientModal] = useState(null);
  const [editing, setEditing] = useState(false);
  const [showInventory, setShowInventory] = useState(false);
  const smallScreen = useMediaQuery('(max-width: 700px)', true);
  const showSuggestions = map.data.preferences.show_lldp_suggestions;
  const [selection, setSelection] = useState(null);
  const [form, setForm] = useState(null);
  const [internetForm, setInternetForm] = useState(null);
  const [bulk, setBulk] = useState(null);
  const [selectedIds, setSelectedIds] = useState([]);
  const [draggingId, setDraggingId] = useState(null);
  const sensors = useSensors(useSensor(MouseSensor, { activationConstraint: { distance: 6 } }),
    useSensor(TouchSensor, { activationConstraint: { delay: 250, tolerance: 6 } }), useSensor(KeyboardSensor));
  const [confirmation, setConfirmation] = useState(null);
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const graph = useMemo(() => networkTopology(map.data.devices, networkMapConnections(map.data, showSuggestions), !smallScreen,
    map.data.internet ? { ...map.data.internet, speedtestTrackerPayload, timeZone } : null), [map.data, showSuggestions, smallScreen, speedtestTrackerPayload, timeZone]);
  const graphDevices = graph.devices;
  const connections = graph.links;
  const renderedPositions = useMemo(() => infrastructurePositions(graphDevices, connections, map.positions), [graphDevices, connections, map.positions]);
  const mobileDevices = map.data.devices.filter(isMobileDevice);
  const pendingLayout = map.pending.some((job) => job.path === 'layout/');
  const pendingInternet = map.pending.some((job) => job.path === 'internet/');
  const toggleBranch = useCallback((id) => setClientModal({ id }), []);
  const connectedIds = useMemo(() => new Set([...map.data.links.flatMap((link) => [link.source_device, link.target_device]),
    ...pendingConnectionDevices(map.data.devices, map.commands),
    ...(map.data.internet?.enabled && map.data.internet.target_device != null ? [map.data.internet.target_device] : [])]),
  [map.data.links, map.data.devices, map.commands, map.data.internet]);
  const disconnected = map.data.devices.filter((device) => !connectedIds.has(device.id));
  const selectedUnconnected = selectedIds.filter((id) => disconnected.some((device) => device.id === id));
  const canDrop = editing && canEditLinks && !map.busy && !map.loading && !form && !bulk;
  const selectedDevice = selection?.type === 'device' ? map.data.devices.find((item) => item.id === selection.id) : null;
  const selectedLink = selection?.type === 'link' ? map.data.links.find((item) => item.id === selection.id)
    : selection?.type === 'suggestion' ? map.data.suggestions.find((item) => item.key === selection.id) : null;
  const selectedSuggestion = selection?.type === 'suggestion';

  const focusLayoutStart = useCallback((positions) => {
    const points = graphDevices.map((device) => positions[device.id]).filter(Boolean);
    if (!points.length) return;
    const left = Math.min(...points.map((point) => point.x)), top = Math.min(...points.map((point) => point.y));
    const bounds = { x: left, y: top,
      width: Math.max(...points.map((point) => point.x)) - left + networkNodeWidth,
      height: Math.max(...graphDevices.map((device) => positions[device.id].y + topologyNodeHeight(device))) - top };
    flow.setViewport(getViewportForBounds(bounds, canvasRef.current?.clientWidth || 900,
      canvasRef.current?.clientHeight || 700, 0.85, 1, 0.1));
  }, [graphDevices, flow]);

  useEffect(() => {
    if (!map.dirty) return undefined;
    const warn = (event) => { event.preventDefault(); event.returnValue = ''; };
    window.addEventListener('beforeunload', warn);
    return () => window.removeEventListener('beforeunload', warn);
  }, [map.dirty]);

  function selectLink(link) {
    if (link.internetConnection) { openInternet(); return; }
    if (link.mobileGroup) {
      setClientModal({ mobile: true, title: link.mobileGroup.title, memberIds: link.mobileGroup.members.map((device) => device.id) });
      return;
    }
    setSelection({ type: link.suggested ? 'suggestion' : 'link', id: link.suggested ? link.key : link.id });
  }

  function openInternet(target) {
    setInternetForm({ target, connection: map.data.internet || null });
  }

  useEffect(() => {
    if (nodeDragging.current) return;
    setNodes(graphDevices.map((device) => {
      const peers = directConnections(device.id, map.data.devices, map.data.links);
      const summary = { online: peers.filter((row) => row.device.online).length,
        ...Object.fromEntries(['wifi', 'ethernet', 'unknown'].map((kind) => [kind,
          peers.filter((row) => row.links.some((link) => link.kind === kind)).length])) };
      return ({
      id: String(device.id), type: device.internetConnection ? 'internet' : device.mobileGroup ? 'mobile' : 'device', position: renderedPositions[device.id],
      width: networkNodeWidth, height: topologyNodeHeight(device),
      data: { device, summary, editing: editing && canEditLayout && !pendingLayout, connected: connectedIds.has(device.id), canDrop,
        clientCount: peers.length, onToggleBranch: toggleBranch }, dragHandle: '.network-node-grip',
      ariaLabel: device.internetConnection ? 'Internet - manual uplink' : `${device.name}${device.ip ? `, ${device.ip}` : ''}, ${device.online ? 'Online' : 'Not online'}`,
    }); }));
  }, [graphDevices, renderedPositions, editing, canEditLayout, connectedIds, canDrop, setNodes, toggleBranch, map.data.devices, map.data.links, pendingLayout]);

  const graphIdentity = `${graphDevices.map((device) => device.id).join(',')}|${connections.map((link) => link.graphId).join(',')}`;
  useEffect(() => {
    if (!graphDevices.length || initializedViewport.current) return undefined;
    const timer = window.setTimeout(() => {
      focusLayoutStart(renderedPositions);
      initializedViewport.current = true;
    }, 100);
    return () => window.clearTimeout(timer);
  }, [graphIdentity, graphDevices.length, focusLayoutStart, renderedPositions]);

  useEffect(() => {
    if (!canvasRef.current) return undefined;
    const observer = new ResizeObserver(([entry]) => {
      const size = { width: entry.contentRect.width, height: entry.contentRect.height };
      const previous = canvasSize.current;
      canvasSize.current = size;
      if (initializedViewport.current && previous && size.width !== previous.width) {
        const viewport = flow.getViewport();
        flow.setViewport({ ...viewport, x: viewport.x + (size.width - previous.width) / 2 });
      }
    });
    observer.observe(canvasRef.current);
    return () => observer.disconnect();
  }, [flow]);

  const lanes = parallelLinkLanes(connections);
  const edges = connections.map((link) => {
    const source = link.mobileGroup || link.internetConnection || renderedPositions[link.source_device].y <= renderedPositions[link.target_device].y ? link.source_device : link.target_device;
    const target = source === link.source_device ? link.target_device : link.source_device;
    return {
      id: link.graphId, source: String(source), target: String(target), type: 'connection',
      selected: selection?.type === (link.suggested ? 'suggestion' : 'link') && selection.id === (link.suggested ? link.key : link.id),
      data: { link, lane: lanes[link.graphId], onSelect: selectLink,
        busX: null },
      ariaLabel: networkLinkTitle(link),
    };
  });

  function endpointText(link, side) {
    const device = map.data.devices.find((item) => item.id === link[`${side}_device`]);
    const networkInterface = device?.interfaces.find((item) => item.id === link[side]);
    return `${device?.name || '-'} · ${networkInterface?.mac || '-'} · ${networkInterface?.ip || '-'}`;
  }

  async function finishEditing() {
    if (map.dirty && !(await map.savePositions())) return;
    setEditing(false);
  }

  function arrange() {
    const next = { ...map.positions, ...infrastructurePositions(graphDevices, connections) };
    map.changePositions(next);
    window.setTimeout(() => focusLayoutStart(next), 100);
  }

  function openDevice(device) {
    if (isInfrastructure(device)) setClientModal({ id: device.id });
    else setSelection({ type: 'device', id: device.id });
    const point = renderedPositions[device.id];
    if (point) {
      flow.setViewport({ x: (canvasRef.current?.clientWidth || 600) / 2 - point.x - networkNodeWidth / 2, y: 48 - point.y, zoom: 1 }, { duration: 250 });
    }
  }

  async function connectDrop({ active, over }) {
    setDraggingId(null);
    if (!canDrop || !over) return;
    const child = map.data.devices.find((device) => device.id === active.data.current?.deviceId);
    const parent = map.data.devices.find((device) => device.id === over.data.current?.deviceId);
    if (!child || !parent || child.id === parent.id) return;
    const body = { source: parent.interfaces[0].id, target: child.interfaces[0].id, kind: 'unknown' };
    if (parent.interfaces.length > 1 || child.interfaces.length > 1) setForm(body);
    else await map.mutate('links/', 'POST', body);
  }

  async function executeConfirmation() {
    if (confirmation === 'discard') {
      map.discardPositions();
      setEditing(false);
      setConfirmation(null);
      await map.load();
    } else if (confirmation === 'restore') {
      if (await map.mutate('suggestions/restored/', 'DELETE')) setConfirmation(null);
    } else if (confirmation === 'internet') {
      if (await map.mutate('internet/', 'DELETE', { revision: map.data.internet.revision })) setConfirmation(null);
    } else if (confirmation?.id) {
      if (await map.mutate(`links/${confirmation.id}/`, 'DELETE', { revision: confirmation.revision })) {
        setSelection(null);
        setConfirmation(null);
      }
    }
  }

  return (
    <DndContext sensors={sensors} collisionDetection={connectionDropTargets}
      measuring={{ droppable: { strategy: MeasuringStrategy.Always } }}
      onDragStart={({ active }) => setDraggingId(active.data.current?.deviceId)}
      onDragCancel={() => setDraggingId(null)} onDragEnd={connectDrop}>
    <Paper className="content-panel network-map-panel" p="lg" radius="md">
      <Stack gap="md">
        <Group justify="space-between">
          <Group gap="sm"><IconTopologyStar size={26} /><Title order={3}>Network Map</Title></Group>
          <Group gap="xs"><Badge variant="light">{map.data.devices.length} devices</Badge>
            <Badge variant="light" color="teal">{map.data.links.length + (map.data.internet?.enabled && map.data.internet.target_device != null ? 1 : 0)} connections</Badge></Group>
        </Group>
        {map.error && <Alert color="red" title="Network map">{map.error}</Alert>}
        {map.pending.length > 0 && <Alert color="blue" icon={<Loader size="sm" />} title="Saving in the background">
          {map.pending.length} changes queued{pendingLayout ? ' · Layout pending' : ''}
        </Alert>}
        <Group justify="space-between" align="flex-end">
          <Select aria-label="Find device" placeholder="Find device" searchable clearable w={260} maw="100%"
            value={null} data={map.data.devices.map((device) => ({ value: String(device.id), label: `${device.name} · ${device.ip}` }))}
            onChange={(id) => {
              if (!id) return;
              openDevice(map.data.devices.find((device) => device.id === Number(id)));
            }} />
          <Group gap="xs">
            <Button size="xs" variant={showInventory ? 'light' : 'default'} aria-expanded={showInventory}
              leftSection={<IconListDetails size={16} />} onClick={() => setShowInventory((current) => !current)}>Unconnected ({disconnected.length})</Button>
            {!smallScreen && mobileDevices.length > 0 && <Tooltip label="All mobile devices"><ActionIcon aria-label="All mobile devices" variant="default" onClick={() => setClientModal({ mobile: true })}><IconDeviceMobile size={18} /></ActionIcon></Tooltip>}
            {(canEditLinks || map.data.internet?.enabled) && <Tooltip label={map.data.internet?.enabled ? 'Internet connection' : 'Add Internet'}>
              <ActionIcon variant="default" aria-label={map.data.internet?.enabled ? 'Internet connection' : 'Add Internet'} disabled={pendingInternet || map.busy || map.loading}
                onClick={() => openInternet()}>{map.data.internet?.enabled ? <IconWorld size={18} /> : <IconWorldPlus size={18} />}</ActionIcon></Tooltip>}
            <Switch label={`LLDP suggestions (${map.data.suggestions.length})`} checked={showSuggestions}
              disabled={map.loading || map.busy} onChange={(event) => map.savePreference(event.currentTarget.checked)} />
            <Tooltip label="Refresh map"><ActionIcon variant="default" aria-label="Refresh map" loading={map.loading}
              disabled={map.busy} onClick={() => map.dirty ? setConfirmation('discard') : map.load()}><IconRefresh size={18} /></ActionIcon></Tooltip>
            <Tooltip label="Center map"><ActionIcon variant="default" aria-label="Center map" disabled={!nodes.length}
              onClick={() => focusLayoutStart(renderedPositions)}><IconFocus2 size={18} /></ActionIcon></Tooltip>
            {canEditLayout && (
              <Tooltip label="Compact automatic layout"><ActionIcon variant="default" aria-label="Automatic layout" disabled={map.busy || pendingLayout || !graphDevices.length} onClick={() => { setEditing(true); arrange(); }}><IconLayoutDistributeHorizontal size={18} /></ActionIcon></Tooltip>
            )}
            {editing && canEditLinks && <Button size="xs" leftSection={<IconPlus size={16} />} disabled={map.busy || map.loading} onClick={() => setForm({})}>Add connection</Button>}
            {editing && canEditLinks && <Button size="xs" variant="light" leftSection={<IconPlus size={16} />} disabled={map.busy || map.loading || map.data.devices.length < 2}
              onClick={() => setBulk({ targets: selectedUnconnected })}>Connect devices</Button>}
            {editing && <Tooltip label="Discard unsaved positions"><ActionIcon aria-label="Cancel editing" variant="default" disabled={map.busy}
              onClick={() => map.dirty ? setConfirmation('discard') : setEditing(false)}><IconX size={18} /></ActionIcon></Tooltip>}
            {(canEditLinks || canEditLayout) && <Button size="xs" variant={editing ? 'filled' : 'light'} loading={map.busy}
              disabled={map.loading || pendingLayout} leftSection={editing ? <IconCheck size={16} /> : <IconPencil size={16} />}
              onClick={() => editing ? finishEditing() : setEditing(true)}>{editing ? 'Done' : 'Edit map'}</Button>}
          </Group>
        </Group>
        <Group gap="md" className="network-map-legend">
          <span className="manual">Manual</span><span className="lldp">LLDP confirmed</span>
          <span className="suggested">Suggestion</span><span className="stale">Stale observation</span>
          {map.dirty && <Badge color="orange" variant="light">Unsaved positions</Badge>}
          {!map.pending.length && map.commands[0]?.status === 'succeeded' && <Badge color="teal" variant="light">Latest change saved</Badge>}
          <Badge variant="light" color="gray">{graphDevices.filter((device) => !device.mobileGroup && !device.internetConnection).length} infrastructure devices</Badge>
        </Group>
        <Group gap="md" className="network-map-legend network-transport-legend"><span className="ethernet">Ethernet</span><span className="wifi">Wi-Fi</span><span className="unknown">Unknown connection</span>
          <Text size="xs" c="dimmed"><IconDeviceMobile size={13} /> Mobile group</Text></Group>
        {smallScreen && mobileDevices.length > 0 && <div className="network-mobile-band">
          <UnstyledButton onClick={() => setClientModal({ mobile: true })}><Group gap="xs"><Text fw={600} size="sm">Mobile devices</Text><Badge variant="light">{mobileDevices.filter((device) => device.online).length} online / {mobileDevices.length}</Badge></Group></UnstyledButton>
          <Group gap="xs">{mobileDevices.slice(0, 5).map((device) => <Tooltip key={device.id} label={`${device.name} · ${device.ip} · ${device.online ? 'Online' : 'Not online'}`}><ActionIcon aria-label={`View ${device.name}`} variant="subtle" onClick={() => openDevice(device)}><DeviceIconStack device={device} size={22} /></ActionIcon></Tooltip>)}
            <Button variant="subtle" size="xs" onClick={() => setClientModal({ mobile: true })}>View all ({mobileDevices.length})</Button></Group>
        </div>}
        <div className={`network-map-workspace ${showInventory ? 'has-inventory' : ''}`}>
        {showInventory && <div className="network-map-sidebar">
        <NetworkDeviceInventory devices={disconnected} editable={editing && canEditLinks} busy={map.busy || map.loading}
          selected={selectedUnconnected} onSelect={(id) => setSelectedIds((current) => current.includes(id) ? current.filter((item) => item !== id) : [...current, id].slice(0, 200))}
          onSelectAll={(ids, checked) => setSelectedIds((current) => checked ? [...new Set([...current, ...ids])].slice(0, 200) : current.filter((id) => !ids.includes(id)))}
          onConnect={() => setBulk({ targets: selectedUnconnected })} onOpen={openDevice} />
        <div className="network-overview"><MiniMap className="network-map-minimap" style={{ width: 200, height: 130 }} pannable zoomable /></div>
        </div>}
        <div className="network-map-canvas" ref={canvasRef}>
          <ReactFlow nodes={nodes} edges={edges} nodeTypes={nodeTypes} edgeTypes={edgeTypes}
            onNodesChange={onNodesChange} nodesDraggable={!draggingId && editing && canEditLayout && !pendingLayout} nodesConnectable={!draggingId && editing && canEditLinks}
            panOnDrag={!draggingId} elementsSelectable={!draggingId}
            onNodeClick={(_, node) => {
              if (node.data.device.internetConnection) openInternet();
              else if (node.data.device.mobileGroup) setClientModal({ mobile: true, title: node.data.device.mobileGroup.title, memberIds: node.data.device.mobileGroup.members.map((device) => device.id) });
              else setClientModal({ id: Number(node.id) });
            }}
            onEdgeClick={(_, edge) => selectLink(edge.data.link)}
            onNodeDragStart={() => { nodeDragging.current = true; }}
            onNodeDragStop={(_, node) => { nodeDragging.current = false; map.changePositions({ ...map.positions, [node.id]: node.position }); }}
            onConnect={({ source, target }) => {
              if (source === 'internet' || target === 'internet') {
                const device = map.data.devices.find((item) => String(item.id) === (source === 'internet' ? target : source));
                if (device) openInternet(device.interfaces[0].id);
                return;
              }
              if (source !== target) setForm({ source: Number(source), target: Number(target) });
            }}
            deleteKeyCode={null} minZoom={0.08} maxZoom={2}
            onlyRenderVisibleElements aria-label="Network connections">
            <Controls showInteractive={false} showFitView={false} />
          </ReactFlow>
          {map.loading && !map.data.devices.length && <div className="network-map-empty"><Loader size="sm" /></div>}
          {!map.loading && !nodes.length && <div className="network-map-empty"><IconTopologyStar size={36} /><Text c="dimmed">No infrastructure devices.</Text></div>}
        </div>
        </div>
        {map.data.hidden_links > 0 && <Alert color="gray">{map.data.hidden_links} connections are hidden because their endpoints are archived, excluded, or merged into the same device.</Alert>}
        <Accordion variant="default">
          <Accordion.Item value="saves"><Accordion.Control>Save history ({map.commands.length})</Accordion.Control>
            <Accordion.Panel><Stack gap="xs">{map.commands.slice(0, 30).map((job) => <Group key={job.id} justify="space-between" className="network-observation-row">
              <div><Text size="sm">{job.path === 'layout/' ? 'Map layout' : job.path === 'internet/' ? 'Internet connection' : 'Network connection'} · {formatDate(job.created_at, timeZone)}</Text>
                {job.status === 'failed' && <Text size="xs" c="red" className="wrap-text">{job.error || 'The change could not be applied.'}</Text>}</div>
              <Badge variant="light" color={job.status === 'failed' ? 'red' : job.status === 'queued' ? 'orange' : 'teal'}>{job.status === 'succeeded' ? 'Saved' : job.status === 'queued' ? 'Pending' : 'Not saved'}</Badge>
            </Group>)}{!map.commands.length && <Text size="sm" c="dimmed">No recent changes.</Text>}</Stack></Accordion.Panel>
          </Accordion.Item>
          <Accordion.Item value="suggestions"><Accordion.Control>LLDP observations ({map.data.suggestions.length})</Accordion.Control>
            <Accordion.Panel><Stack gap="xs">
              {map.data.suggestions.map((item) => <UnstyledButton key={item.key} className="network-observation-row"
                onClick={() => setSelection({ type: 'suggestion', id: item.key })}>
                <Text size="sm">{endpointText(item, 'source')} ↔ {endpointText(item, 'target')}</Text>
                <Text size="xs" c="dimmed">{item.source_port || '-'} ↔ {item.target_port || '-'} · {item.stale ? 'Stale' : 'Unconfirmed'} · {formatDate(item.observed_at, timeZone)}</Text>
              </UnstyledButton>)}
              {!map.data.suggestions.length && <Text size="sm" c="dimmed">No unmatched connection suggestions.</Text>}
              {map.data.dismissed_count > 0 && canEditLinks && editing && <Button variant="subtle" size="xs" leftSection={<IconRestore size={16} />}
                disabled={map.busy} onClick={() => setConfirmation('restore')}>Restore dismissed suggestions ({map.data.dismissed_count})</Button>}
            </Stack></Accordion.Panel>
          </Accordion.Item>
          {map.data.unresolved.length > 0 && <Accordion.Item value="unresolved"><Accordion.Control>Unmatched LLDP neighbors ({map.data.unresolved.length})</Accordion.Control>
            <Accordion.Panel><Stack gap="xs">{map.data.unresolved.map((item, index) => <Box key={index} className="network-observation-row">
              <Text size="sm">{map.data.devices.find((device) => device.id === item.device_id)?.name} · {item.local_port || '-'}</Text>
              <Text size="xs" className="wrap-text" c="dimmed">{item.system_name || item.chassis_id || '-'} · {item.reason}</Text>
            </Box>)}</Stack></Accordion.Panel></Accordion.Item>}
        </Accordion>
      </Stack>
      {clientModal && (clientModal.mobile || map.data.devices.some((device) => device.id === clientModal.id)) && <NetworkDevicesModal
        key={clientModal.mobile ? 'mobile' : clientModal.id} mobile={clientModal.mobile} node={map.data.devices.find((device) => device.id === clientModal.id)}
        memberIds={clientModal.memberIds} title={clientModal.title}
        devices={map.data.devices} links={map.data.links} timeZone={timeZone} editable={canEditLinks} pending={map.pending.length}
        onClose={() => setClientModal(null)} onOpen={(device) => { setClientModal(null); onSelectDevice(device); }}
        onConnect={(device, targets) => { setClientModal(null); setBulk({ source: device?.id, targets: targets || [] }); }}
        onManage={(device) => { setClientModal(null); setSelection({ type: 'device', id: device.id }); }}
        onEditLink={(link) => { setClientModal(null); setForm(link); }}
        onLink={(link) => { setClientModal(null); selectLink(link); }} />}
      <Drawer opened={Boolean(selectedDevice || selectedLink)} onClose={() => setSelection(null)} title={selectedDevice ? 'Device' : 'Connection'} size="min(100vw, 460px)">
        {map.error && <Alert color="red" mb="md">{map.error}</Alert>}
        {selectedDevice && <Stack>
          <Title order={4} className="wrap-text">{selectedDevice.name}</Title>
          <SimpleGrid cols={1}><DeviceField label="IP" value={selectedDevice.ip} /><DeviceField label="Room" value={selectedDevice.room || 'Unassigned'} />
            <DeviceField label="Status" value={selectedDevice.online ? 'Online' : 'Not online'} /></SimpleGrid>
          <Button leftSection={<IconArrowUpRight size={18} />} onClick={() => onSelectDevice(selectedDevice)}>Open device</Button>
          {editing && canEditLinks && <Button variant="light" leftSection={<IconPlus size={18} />} onClick={() => { setForm({ source: selectedDevice.interfaces[0].id }); setSelection(null); }}>Add connection</Button>}
          {editing && canEditLinks && <Button variant="light" leftSection={<IconPlus size={18} />} onClick={() => { setBulk({ source: selectedDevice.id, targets: selectedUnconnected }); setSelection(null); }}>Connect devices</Button>}
        </Stack>}
        {selectedLink && <Stack>
          <Badge color={selectedSuggestion ? 'orange' : selectedLink.origin === 'lldp' ? 'teal' : 'gray'} variant="light">
            {selectedSuggestion ? 'LLDP · Unconfirmed' : selectedLink.origin === 'lldp' ? 'LLDP · Confirmed' : 'Manual'}
          </Badge>
          {selectedLink.stale && <Alert color="orange">This connection has not been recently reported. It remains saved until explicitly changed.</Alert>}
          <DeviceField label="From interface" value={endpointText(selectedLink, 'source')} />
          <DeviceField label="To interface" value={endpointText(selectedLink, 'target')} />
          <DeviceField label="Connection" value={networkLinkTitle(selectedLink)} />
          {selectedLink.observed_at && <DeviceField label="Reported at" value={formatDate(selectedLink.observed_at, timeZone)} />}
          {selectedLink.updated_at && <DeviceField label="Last edited" value={formatDate(selectedLink.updated_at, timeZone)} />}
          {canEditLinks && !selectedSuggestion && <NetworkLinkQuickEdit key={`${selectedLink.id}-${selectedLink.revision}`}
            link={selectedLink} busy={map.busy} onSave={(body) => map.mutate(`links/${selectedLink.id}/`, 'PUT', body)} />}
          {canEditLinks && (selectedSuggestion ? <Group>
            <Button loading={map.busy} leftSection={<IconCheck size={18} />} onClick={async () => {
              if (await map.mutate(`suggestions/${selectedLink.key}/accept/`, 'POST')) setSelection(null);
            }}>Confirm connection</Button>
            <Button variant="default" disabled={map.busy} onClick={async () => {
              if (await map.mutate(`suggestions/${selectedLink.key}/dismiss/`, 'POST')) setSelection(null);
            }}>Dismiss</Button>
          </Group> : <Group>
            <Button variant="light" disabled={map.busy} leftSection={<IconPencil size={18} />} onClick={() => { setForm(selectedLink); setSelection(null); }}>Edit connection</Button>
            <Button color="red" variant="subtle" disabled={map.busy} leftSection={<IconTrash size={18} />} onClick={() => setConfirmation(selectedLink)}>Delete connection</Button>
          </Group>)}
        </Stack>}
      </Drawer>
      {internetForm && <NetworkInternetForm initial={internetForm} connection={internetForm.connection}
        devices={map.data.devices.filter((device) => isInfrastructure(device) || device.id === map.data.internet?.target_device)}
        editable={canEditLinks && !pendingInternet} busy={map.busy} error={map.error} onClose={() => setInternetForm(null)}
        onSave={async (body) => { if (await map.mutate('internet/', 'PUT', body)) setInternetForm(null); }}
        onRemove={() => { setInternetForm(null); setConfirmation('internet'); }} />}
      {form && <NetworkLinkForm key={form.id || `${form.source}-${form.target}`} initial={form} devices={map.data.devices} busy={map.busy} error={map.error}
        onClose={() => setForm(null)} onSave={async (body) => {
          if (await map.mutate(form.id ? `links/${form.id}/` : 'links/', form.id ? 'PUT' : 'POST', body)) setForm(null);
        }} />}
      {bulk && <NetworkBulkForm initialSource={bulk.source} initialTargets={bulk.targets} devices={map.data.devices} connectedIds={connectedIds} busy={map.busy} error={map.error}
        onClose={() => setBulk(null)} onSave={async (body) => {
          if (await map.mutate('links/bulk/', 'POST', body)) { setBulk(null); setSelectedIds([]); }
        }} />}
      <Modal opened={Boolean(confirmation)} onClose={() => !map.busy && setConfirmation(null)} title={confirmation === 'discard' ? 'Discard unsaved positions?' : confirmation === 'restore' ? 'Restore dismissed suggestions?' : confirmation === 'internet' ? 'Remove Internet?' : 'Delete connection?'} centered size="sm">
        {map.error && <Alert color="red" mb="md">{map.error}</Alert>}
        <Text size="sm" mb="lg">{confirmation === 'discard' ? 'Saved connections will not be changed.' : confirmation === 'restore' ? 'Dismissed observations will become available for review again.' : confirmation === 'internet' ? 'This removes the Internet node and its uplink, not any devices.' : 'This removes the connection, not either device.'}</Text>
        <Group justify="flex-end"><Button variant="default" disabled={map.busy} onClick={() => setConfirmation(null)}>Cancel</Button>
          <Button color={confirmation?.id || confirmation === 'internet' ? 'red' : 'indigo'} loading={map.busy} onClick={executeConfirmation}>
            {confirmation === 'discard' ? 'Discard positions' : confirmation === 'restore' ? 'Restore' : confirmation === 'internet' ? 'Remove Internet' : 'Delete connection'}
          </Button></Group>
      </Modal>
    </Paper>
    <DragOverlay>{draggingId && <div className="network-drag-preview">{map.data.devices.find((device) => device.id === draggingId)?.name}</div>}</DragOverlay>
    </DndContext>
  );
}

export default function NetworkMapView(props) {
  return <ReactFlowProvider><MapWorkspace {...props} /></ReactFlowProvider>;
}
