'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import {
  Accordion, ActionIcon, Alert, Badge, Box, Button, Drawer, Group, Loader, Modal,
  Paper, Select, SimpleGrid, Stack, Switch, Text, Title, Tooltip, UnstyledButton,
} from '@mantine/core';
import {
  ReactFlow, ReactFlowProvider, Controls, MiniMap, useNodesState, useReactFlow,
} from '@xyflow/react';
import { IconArrowUpRight, IconCheck, IconLayoutDistributeHorizontal, IconPencil, IconPlus,
  IconRefresh, IconRestore, IconTopologyStar, IconTrash, IconX } from '@tabler/icons-react';

import { DeviceField } from '../devices/DeviceDetailFields';
import { formatDate } from '../utils/date';
import { networkLinkTitle, networkMapConnections, networkMapPositions,
  networkNodeHeight, networkNodeWidth, parallelLinkLanes } from '../utils/networkMap';
import { NetworkConnectionEdge, NetworkDeviceNode } from './NetworkMapElements';
import NetworkLinkForm from './NetworkLinkForm';
import useNetworkMap from './useNetworkMap';

const nodeTypes = { device: NetworkDeviceNode };
const edgeTypes = { connection: NetworkConnectionEdge };

function MapWorkspace({ canEditLinks, canEditLayout, onSelectDevice, timeZone }) {
  const map = useNetworkMap();
  const flow = useReactFlow();
  const canvasRef = useRef(null);
  const [editing, setEditing] = useState(false);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [selection, setSelection] = useState(null);
  const [form, setForm] = useState(null);
  const [confirmation, setConfirmation] = useState(null);
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const connections = useMemo(() => networkMapConnections(map.data, showSuggestions), [map.data, showSuggestions]);
  const visibleIds = useMemo(() => new Set(connections.flatMap((link) => [link.source_device, link.target_device])), [connections]);
  const graphDevices = useMemo(() => map.data.devices.filter((device) => visibleIds.has(device.id)), [map.data.devices, visibleIds]);
  const renderedPositions = useMemo(() => networkMapPositions(graphDevices, connections, map.positions), [graphDevices, connections, map.positions]);
  const connectedIds = new Set(map.data.links.flatMap((link) => [link.source_device, link.target_device]));
  const disconnected = map.data.devices.filter((device) => !connectedIds.has(device.id));
  const selectedDevice = selection?.type === 'device' ? map.data.devices.find((item) => item.id === selection.id) : null;
  const selectedLink = selection?.type === 'link' ? map.data.links.find((item) => item.id === selection.id)
    : selection?.type === 'suggestion' ? map.data.suggestions.find((item) => item.key === selection.id) : null;
  const selectedSuggestion = selection?.type === 'suggestion';

  useEffect(() => {
    if (!map.dirty) return undefined;
    const warn = (event) => { event.preventDefault(); event.returnValue = ''; };
    window.addEventListener('beforeunload', warn);
    return () => window.removeEventListener('beforeunload', warn);
  }, [map.dirty]);

  function selectLink(link) {
    setSelection({ type: link.suggested ? 'suggestion' : 'link', id: link.suggested ? link.key : link.id });
  }

  useEffect(() => {
    setNodes(graphDevices.map((device) => ({
      id: String(device.id), type: 'device', position: renderedPositions[device.id],
      width: networkNodeWidth, height: networkNodeHeight,
      data: { device, editing: editing && canEditLayout }, dragHandle: '.network-node-grip',
      ariaLabel: `${device.name}, ${device.ip}, ${device.online ? 'Online' : 'Not online'}`,
    })));
  }, [graphDevices, renderedPositions, editing, canEditLayout, setNodes]);

  const graphIdentity = graphDevices.map((device) => device.id).join(',');
  useEffect(() => {
    if (!graphIdentity) return undefined;
    const timer = window.setTimeout(() => flow.fitView({ padding: 0.18, maxZoom: 1 }), 100);
    return () => window.clearTimeout(timer);
  }, [graphIdentity, flow]);

  useEffect(() => {
    if (!canvasRef.current) return undefined;
    let timer;
    const observer = new ResizeObserver(() => {
      window.clearTimeout(timer);
      timer = window.setTimeout(() => flow.fitView({ padding: 0.18, maxZoom: 1 }), 100);
    });
    observer.observe(canvasRef.current);
    return () => { observer.disconnect(); window.clearTimeout(timer); };
  }, [flow]);

  const lanes = parallelLinkLanes(connections);
  const edges = connections.map((link) => ({
    id: link.graphId, source: String(link.source_device), target: String(link.target_device), type: 'connection',
    data: { link, lane: lanes[link.graphId], onSelect: selectLink },
    ariaLabel: networkLinkTitle(link),
  }));

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
    map.changePositions({ ...map.positions, ...networkMapPositions(graphDevices, connections) });
    window.setTimeout(() => flow.fitView({ padding: 0.18, maxZoom: 1 }), 100);
  }

  async function executeConfirmation() {
    if (confirmation === 'discard') {
      map.discardPositions();
      setEditing(false);
      setConfirmation(null);
      await map.load();
    } else if (confirmation === 'restore') {
      if (await map.mutate('suggestions/restored/', 'DELETE')) setConfirmation(null);
    } else if (confirmation?.id) {
      if (await map.mutate(`links/${confirmation.id}/`, 'DELETE', { revision: confirmation.revision })) {
        setSelection(null);
        setConfirmation(null);
      }
    }
  }

  return (
    <Paper className="content-panel network-map-panel" p="lg" radius="md">
      <Stack gap="md">
        <Group justify="space-between">
          <Group gap="sm"><IconTopologyStar size={26} /><Title order={3}>Network Map</Title></Group>
          <Group gap="xs"><Badge variant="light">{map.data.devices.length} devices</Badge>
            <Badge variant="light" color="teal">{map.data.links.length} connections</Badge></Group>
        </Group>
        {map.error && <Alert color="red" title="Network map">{map.error}</Alert>}
        <Group justify="space-between" align="flex-end">
          <Select aria-label="Find device" placeholder="Find device" searchable clearable w={260} maw="100%"
            value={null} data={map.data.devices.map((device) => ({ value: String(device.id), label: `${device.name} · ${device.ip}` }))}
            onChange={(id) => {
              if (!id) return;
              setSelection({ type: 'device', id: Number(id) });
              const node = flow.getNode(id);
              if (node) flow.setCenter(node.position.x + networkNodeWidth / 2, node.position.y + networkNodeHeight / 2, { zoom: 1, duration: 250 });
            }} />
          <Group gap="xs">
            <Switch label={`LLDP suggestions (${map.data.suggestions.length})`} checked={showSuggestions} onChange={(event) => setShowSuggestions(event.currentTarget.checked)} />
            <Tooltip label="Refresh map"><ActionIcon variant="default" aria-label="Refresh map" loading={map.loading}
              disabled={map.busy} onClick={() => map.dirty ? setConfirmation('discard') : map.load()}><IconRefresh size={18} /></ActionIcon></Tooltip>
            {editing && canEditLayout && (
              <Tooltip label="Automatic layout"><ActionIcon variant="default" aria-label="Automatic layout" disabled={map.busy || !graphDevices.length} onClick={arrange}><IconLayoutDistributeHorizontal size={18} /></ActionIcon></Tooltip>
            )}
            {editing && canEditLinks && <Button size="xs" leftSection={<IconPlus size={16} />} disabled={map.busy || map.loading} onClick={() => setForm({})}>Add connection</Button>}
            {editing && <Tooltip label="Discard unsaved positions"><ActionIcon aria-label="Cancel editing" variant="default" disabled={map.busy}
              onClick={() => map.dirty ? setConfirmation('discard') : setEditing(false)}><IconX size={18} /></ActionIcon></Tooltip>}
            {(canEditLinks || canEditLayout) && <Button size="xs" variant={editing ? 'filled' : 'light'} loading={map.busy}
              disabled={map.loading} leftSection={editing ? <IconCheck size={16} /> : <IconPencil size={16} />}
              onClick={() => editing ? finishEditing() : setEditing(true)}>{editing ? 'Done' : 'Edit map'}</Button>}
          </Group>
        </Group>
        <Group gap="md" className="network-map-legend">
          <span className="manual">Manual</span><span className="lldp">LLDP confirmed</span>
          <span className="suggested">Suggestion</span><span className="stale">Stale observation</span>
          {map.dirty && <Badge color="orange" variant="light">Unsaved positions</Badge>}
        </Group>
        <div className="network-map-canvas" ref={canvasRef}>
          <ReactFlow nodes={nodes} edges={edges} nodeTypes={nodeTypes} edgeTypes={edgeTypes}
            onNodesChange={onNodesChange} nodesDraggable={editing && canEditLayout} nodesConnectable={editing && canEditLinks}
            onNodeClick={(_, node) => setSelection({ type: 'device', id: Number(node.id) })}
            onEdgeClick={(_, edge) => selectLink(edge.data.link)}
            onNodeDragStop={(_, node) => map.changePositions({ ...map.positions, [node.id]: node.position })}
            onConnect={({ source, target }) => {
              if (source !== target) setForm({ source: Number(source), target: Number(target) });
            }}
            deleteKeyCode={null} minZoom={0.12} maxZoom={2} fitView fitViewOptions={{ padding: 0.18, maxZoom: 1 }}
            onlyRenderVisibleElements aria-label="Network connections">
            <Controls showInteractive={false} />
            <MiniMap className="network-map-minimap" pannable zoomable />
          </ReactFlow>
          {map.loading && !map.data.devices.length && <div className="network-map-empty"><Loader size="sm" /></div>}
          {!map.loading && !nodes.length && <div className="network-map-empty"><IconTopologyStar size={36} /><Text c="dimmed">No connections to display.</Text></div>}
        </div>
        {map.data.hidden_links > 0 && <Alert color="gray">{map.data.hidden_links} connections are hidden because their endpoints are archived, excluded, or merged into the same device.</Alert>}
        <Accordion variant="default">
          <Accordion.Item value="unconnected"><Accordion.Control>Unconnected devices ({disconnected.length})</Accordion.Control>
            <Accordion.Panel><ul className="network-map-device-list">
              {disconnected.map((device) => <li key={device.id}><UnstyledButton onClick={() => setSelection({ type: 'device', id: device.id })}>
                <span>{device.name}</span><Text size="xs" c="dimmed">{device.ip} · {device.interfaces.length} interfaces</Text>
              </UnstyledButton></li>)}
              {!disconnected.length && <li><Text size="sm" c="dimmed">No unconnected devices.</Text></li>}
            </ul></Accordion.Panel>
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
      <Drawer opened={Boolean(selectedDevice || selectedLink)} onClose={() => setSelection(null)} title={selectedDevice ? 'Device' : 'Connection'} size="min(100vw, 460px)">
        {map.error && <Alert color="red" mb="md">{map.error}</Alert>}
        {selectedDevice && <Stack>
          <Title order={4} className="wrap-text">{selectedDevice.name}</Title>
          <SimpleGrid cols={1}><DeviceField label="IP" value={selectedDevice.ip} /><DeviceField label="Room" value={selectedDevice.room || 'Unassigned'} />
            <DeviceField label="Status" value={selectedDevice.online ? 'Online' : 'Not online'} /></SimpleGrid>
          <Button leftSection={<IconArrowUpRight size={18} />} onClick={() => onSelectDevice(selectedDevice)}>Open device</Button>
          {editing && canEditLinks && <Button variant="light" leftSection={<IconPlus size={18} />} onClick={() => { setForm({ source: selectedDevice.interfaces[0].id }); setSelection(null); }}>Add connection</Button>}
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
          {editing && canEditLinks && (selectedSuggestion ? <Group>
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
      {form && <NetworkLinkForm key={form.id || `${form.source}-${form.target}`} initial={form} devices={map.data.devices} busy={map.busy} error={map.error}
        onClose={() => setForm(null)} onSave={async (body) => {
          if (await map.mutate(form.id ? `links/${form.id}/` : 'links/', form.id ? 'PUT' : 'POST', body)) setForm(null);
        }} />}
      <Modal opened={Boolean(confirmation)} onClose={() => !map.busy && setConfirmation(null)} title={confirmation === 'discard' ? 'Discard unsaved positions?' : confirmation === 'restore' ? 'Restore dismissed suggestions?' : 'Delete connection?'} centered size="sm">
        {map.error && <Alert color="red" mb="md">{map.error}</Alert>}
        <Text size="sm" mb="lg">{confirmation === 'discard' ? 'Saved connections will not be changed.' : confirmation === 'restore' ? 'Dismissed observations will become available for review again.' : 'This removes the connection, not either device.'}</Text>
        <Group justify="flex-end"><Button variant="default" disabled={map.busy} onClick={() => setConfirmation(null)}>Cancel</Button>
          <Button color={confirmation?.id ? 'red' : 'indigo'} loading={map.busy} onClick={executeConfirmation}>
            {confirmation === 'discard' ? 'Discard positions' : confirmation === 'restore' ? 'Restore' : 'Delete connection'}
          </Button></Group>
      </Modal>
    </Paper>
  );
}

export default function NetworkMapView(props) {
  return <ReactFlowProvider><MapWorkspace {...props} /></ReactFlowProvider>;
}
