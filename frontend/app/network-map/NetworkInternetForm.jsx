import { useState } from 'react';
import { Alert, Button, Group, Modal, Select, Stack } from '@mantine/core';
import { IconCheck, IconTrash, IconWorld } from '@tabler/icons-react';
import { networkLinkKinds } from '../utils/networkMap';

export default function NetworkInternetForm({ initial, connection, devices, editable, busy, error, onClose, onSave, onRemove }) {
  const initialInterface = initial?.target || connection?.target;
  const initialDevice = devices.find((device) => device.interfaces.some((item) => item.id === initialInterface));
  const [deviceId, setDeviceId] = useState(initialDevice ? String(initialDevice.id) : null);
  const [target, setTarget] = useState(initialDevice ? String(initialInterface) : null);
  const [kind, setKind] = useState(connection?.kind || 'unknown');
  const interfaces = devices.find((device) => String(device.id) === deviceId)?.interfaces || [];
  return <Modal opened title={<Group gap="xs"><IconWorld size={22} />Internet connection</Group>} onClose={busy ? () => {} : onClose} centered size="md">
    <form onSubmit={(event) => { event.preventDefault(); if (editable && target && !busy) onSave({ target: Number(target), kind, revision: connection?.revision || 0 }); }}>
      <Stack gap="md">
        {error && <Alert color="red">{error}</Alert>}
        {connection?.enabled && connection.target_device == null && <Alert color="orange">The assigned interface is no longer available.</Alert>}
        <Select label="Connect to" searchable required disabled={!editable || busy} value={deviceId}
          data={devices.map((device) => ({ value: String(device.id), label: `${device.name} · ${device.ip}` }))}
          onChange={(id) => { setDeviceId(id); setTarget(id ? String(devices.find((device) => String(device.id) === id).interfaces[0].id) : null); }} />
        <Select label="Network interface" required disabled={!editable || busy} value={target} onChange={setTarget}
          data={interfaces.map((item) => ({ value: String(item.id), label: `${item.mac} · ${item.ip}` }))} />
        <Select label="Connection type" required disabled={!editable || busy} value={kind} onChange={setKind} data={networkLinkKinds} />
        <Group justify="space-between" wrap="wrap">
          {editable && connection?.enabled ? <Button variant="subtle" color="red" leftSection={<IconTrash size={16} />} disabled={busy} onClick={onRemove}>Remove Internet</Button> : <span />}
          <Group gap="xs"><Button variant="default" disabled={busy} onClick={onClose}>{editable ? 'Cancel' : 'Close'}</Button>
            {editable && <Button type="submit" leftSection={<IconCheck size={16} />} loading={busy} disabled={!target}>Save</Button>}</Group>
        </Group>
      </Stack>
    </form>
  </Modal>;
}
