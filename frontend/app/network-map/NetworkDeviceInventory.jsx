import { useCallback, useState } from 'react';
import { ActionIcon, Button, Checkbox, Group, Text, TextInput, Title, Tooltip, UnstyledButton } from '@mantine/core';
import { IconGripVertical, IconLink, IconSearch } from '@tabler/icons-react';
import { useDraggable, useDroppable } from '@dnd-kit/core';
import DeviceIconStack from '../components/DeviceIconStack';

function InventoryDevice({ device, editable, busy, selected, onSelect, onOpen }) {
  const { attributes, listeners, setNodeRef, setActivatorNodeRef, isDragging } = useDraggable({
    id: `inventory-${device.id}`, data: { deviceId: device.id }, disabled: !editable || busy,
  });
  const { setNodeRef: setDropRef, isOver } = useDroppable({
    id: `inventory-target-${device.id}`, data: { deviceId: device.id }, disabled: !editable || busy,
  });
  const setRefs = useCallback((node) => { setNodeRef(node); setDropRef(node); }, [setNodeRef, setDropRef]);
  return (
    <li ref={setRefs}
      className={`network-inventory-device ${isOver ? 'drop-target' : ''} ${isDragging ? 'dragging' : ''}`}>
      {editable && <Checkbox aria-label={`Select ${device.name}`} checked={selected} disabled={busy} onChange={onSelect} />}
      <DeviceIconStack device={device} size={20} />
      <UnstyledButton className="network-inventory-name" onClick={onOpen}>
        <Text size="sm" fw={600}>{device.name}</Text><Text size="xs" c="dimmed">{device.ip}</Text>
      </UnstyledButton>
      {editable && <Tooltip label={`Connect ${device.name}`}><ActionIcon ref={setActivatorNodeRef} variant="subtle"
        aria-label={`Drag ${device.name} to connect`} disabled={busy} className="network-inventory-grip"
        {...attributes} {...listeners}><IconGripVertical size={18} /></ActionIcon></Tooltip>}
    </li>
  );
}

export default function NetworkDeviceInventory({ devices, editable, busy, selected, onSelect, onSelectAll, onConnect, onOpen }) {
  const [search, setSearch] = useState('');
  const query = search.trim().toLowerCase();
  const visible = devices.filter((device) => `${device.name} ${device.ip} ${device.room}`.toLowerCase().includes(query));
  return (
    <aside className="network-inventory" aria-label="Unconnected devices">
      <Group justify="space-between" gap="xs"><Title order={5}>Unconnected devices</Title><Text size="sm" c="dimmed">{devices.length}</Text></Group>
      <TextInput aria-label="Search unconnected devices" placeholder="Search" leftSection={<IconSearch size={16} />}
        value={search} onChange={(event) => setSearch(event.currentTarget.value)} />
      {editable && <>
        <Group justify="space-between" gap="xs"><Checkbox label="Select visible" disabled={busy || !visible.length}
          checked={visible.length > 0 && visible.every((device) => selected.includes(device.id))}
          indeterminate={visible.some((device) => selected.includes(device.id)) && !visible.every((device) => selected.includes(device.id))}
          onChange={(event) => onSelectAll(visible.map((device) => device.id), event.currentTarget.checked)} />
          <Text size="xs" c="dimmed">{selected.length} selected</Text></Group>
        <Button variant="light" size="xs" leftSection={<IconLink size={16} />} disabled={busy || !selected.length} onClick={onConnect}>Connect selected</Button>
      </>}
      <ul className="network-inventory-list">{visible.map((device) => <InventoryDevice key={device.id} device={device}
        editable={editable} busy={busy} selected={selected.includes(device.id)} onSelect={() => onSelect(device.id)} onOpen={() => onOpen(device)} />)}</ul>
      {!visible.length && <Text size="sm" c="dimmed">{devices.length ? 'No matching devices.' : 'All devices are connected.'}</Text>}
    </aside>
  );
}
