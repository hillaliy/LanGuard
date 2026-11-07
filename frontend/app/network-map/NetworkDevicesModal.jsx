import { useMemo, useState } from 'react';
import { ActionIcon, Badge, Button, Group, Modal, Select, Stack, Table, Text, TextInput, Tooltip, VisuallyHidden } from '@mantine/core';
import { IconArrowUpRight, IconLink, IconPlus, IconSearch, IconPencil } from '@tabler/icons-react';

import DeviceIconStack from '../components/DeviceIconStack';
import { formatDate } from '../utils/date';
import { formatRoleLabel } from '../utils/device';
import { directConnections, isInfrastructure, isMobileDevice } from '../utils/networkInfrastructure';
import NetworkRoamingIndicator from './NetworkRoamingIndicator';

export default function NetworkDevicesModal({ node, mobile = false, memberIds, title, devices, links, timeZone, editable,
  pending, onClose, onOpen, onConnect, onLink, onManage, onEditLink }) {
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState('all');
  const [kind, setKind] = useState('all');
  const [type, setType] = useState('all');
  const rows = useMemo(() => mobile
    ? devices.filter((device) => isMobileDevice(device) && (!memberIds || memberIds.includes(device.id))).map((device) => ({ device, links: links.filter((link) => link.source_device === device.id || link.target_device === device.id) }))
    : directConnections(node.id, devices, links), [mobile, node, devices, links, memberIds]);
  const visible = rows.filter(({ device, links: connections }) => {
    const text = [device.name, device.ip, device.room, device.role, ...device.interfaces.map((item) => item.mac)].join(' ').toLowerCase();
    return text.includes(search.trim().toLowerCase()) && (status === 'all' || device.online === (status === 'online'))
      && (kind === 'all' || (connections.length ? connections.some((link) => link.kind === kind) : kind === 'unknown'))
      && (type === 'all' || (type === 'mobile' ? isMobileDevice(device) : isInfrastructure(device)));
  });
  const online = rows.filter(({ device }) => device.online).length;
  const unassigned = rows.filter((row) => !row.links.length).map((row) => row.device.id);
  return <Modal opened onClose={onClose} title={title || (mobile ? 'Mobile devices' : node.name)} size="min(1240px, calc(100vw - 32px))"
    classNames={{ title: 'network-devices-dialog-title', body: 'network-devices-dialog-body' }} centered>
    <Stack gap="md">
      <Group justify="space-between" align="flex-start">
        <Group gap="xs"><Badge variant="light">{rows.length} devices</Badge><Badge color="teal" variant="light">{online} online</Badge>
          <Badge color="gray" variant="light">{rows.length - online} not online</Badge>
          {pending > 0 && <Badge color="orange" variant="light">{pending} pending changes</Badge>}</Group>
        {!mobile && <Group gap="xs"><Tooltip label="Open device"><ActionIcon aria-label="Open device" variant="default" onClick={() => onOpen(node)}><IconArrowUpRight size={18} /></ActionIcon></Tooltip>
          {editable && <Button size="xs" variant="light" leftSection={<IconPlus size={16} />} onClick={() => onConnect(node)}>Connect devices</Button>}
          <Tooltip label="Connection details"><ActionIcon aria-label="Connection details" variant="default" onClick={() => onManage(node)}><IconLink size={18} /></ActionIcon></Tooltip></Group>}
        {mobile && editable && unassigned.length > 0 && <Button size="xs" variant="light" leftSection={<IconPlus size={16} />}
          onClick={() => onConnect(null, unassigned)}>Connect unassigned ({unassigned.length})</Button>}
      </Group>
      <Group align="flex-end" gap="sm">
        <TextInput aria-label="Search connected devices" placeholder="Search" leftSection={<IconSearch size={16} />} value={search} onChange={(event) => setSearch(event.currentTarget.value)} style={{ flex: '1 1 200px' }} />
        <Select aria-label="Device status" value={status} onChange={setStatus} data={[{ value: 'all', label: 'All statuses' }, { value: 'online', label: 'Online' }, { value: 'offline', label: 'Not online' }]} w={150} />
        <Select aria-label="Connection type" value={kind} onChange={setKind} data={[{ value: 'all', label: 'All connections' }, { value: 'ethernet', label: 'Ethernet' }, { value: 'wifi', label: 'Wi-Fi' }, { value: 'unknown', label: 'Unknown' }]} w={160} />
        {!mobile && <Select aria-label="Device type" value={type} onChange={setType} data={[{ value: 'all', label: 'All devices' }, { value: 'mobile', label: 'Mobile' }, { value: 'infrastructure', label: 'Infrastructure' }]} w={160} />}
      </Group>
      <Table.ScrollContainer minWidth={1000}>
        <Table verticalSpacing="sm" className="network-clients-table">
          <colgroup><col className="network-clients-device-column" /><col className="network-clients-ip-column" /><col className="network-clients-status-column" /><col /><col className="network-clients-seen-column" /><col className="network-clients-actions-column" /></colgroup>
          <Table.Thead><Table.Tr><Table.Th>Device</Table.Th><Table.Th>IP address</Table.Th><Table.Th>Status</Table.Th><Table.Th>Connection</Table.Th><Table.Th>Last seen</Table.Th><Table.Th><VisuallyHidden>Actions</VisuallyHidden></Table.Th></Table.Tr></Table.Thead>
          <Table.Tbody>{visible.map(({ device, links: connections }) => <Table.Tr key={device.id}>
            <Table.Td><Group gap="xs" wrap="nowrap"><DeviceIconStack device={device} size={22} /><div className="network-client-name"><Text size="sm" fw={600} className="wrap-text">{device.name}</Text><Text size="xs" c="dimmed">{formatRoleLabel(device.role)}{device.room ? ` · ${device.room}` : ''}</Text></div></Group></Table.Td>
            <Table.Td><Text size="sm" dir="ltr">{device.ip}</Text></Table.Td>
            <Table.Td><Text size="sm"><i className={`network-presence-dot ${device.online ? 'online' : ''}`} />{device.online ? 'Online' : 'Not online'}</Text></Table.Td>
            <Table.Td>{connections.length ? <Stack gap={4}>{connections.map((link) => {
              const peerId = link.source_device === device.id ? link.target_device : link.source_device;
              const peer = devices.find((item) => item.id === peerId);
              return <Group key={link.id} gap={4} wrap="nowrap"><Tooltip label={`${link.origin === 'manual' ? 'Manual' : 'LLDP'}${link.stale ? ' · Stale observation' : ''}`}>
                <button type="button" className="network-client-link" onClick={() => onLink(link)}>
                  {link.kind === 'wifi' ? 'Wi-Fi' : link.kind === 'ethernet' ? 'Ethernet' : 'Unknown'}{mobile && peer ? ` · ${peer.name}` : ''}
                  {link.source_port || link.target_port ? ` · ${[link.source_port, link.target_port].filter(Boolean).join(' / ')}` : ''}
                </button></Tooltip>{editable && onEditLink && <Tooltip label="Edit connection"><ActionIcon size="xs" variant="subtle" aria-label={`Edit connection ${link.id}`} onClick={() => onEditLink(link)}><IconPencil size={14} /></ActionIcon></Tooltip>}</Group>;
            })}</Stack> : <NetworkRoamingIndicator />}</Table.Td>
            <Table.Td><Text size="xs">{device.last_seen ? formatDate(device.last_seen, timeZone) : '-'}</Text></Table.Td>
            <Table.Td><Tooltip label="Open device"><ActionIcon variant="subtle" aria-label={`Open ${device.name}`} onClick={() => onOpen(device)}><IconArrowUpRight size={18} /></ActionIcon></Tooltip></Table.Td>
          </Table.Tr>)}</Table.Tbody>
        </Table>
      </Table.ScrollContainer>
      {!visible.length && <Text ta="center" c="dimmed" size="sm" py="lg">{rows.length ? 'No matching devices.' : 'No saved connections.'}</Text>}
    </Stack>
  </Modal>;
}
