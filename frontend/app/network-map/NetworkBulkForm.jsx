import { useState } from 'react';
import { Alert, Button, Group, Modal, MultiSelect, Select, Stack } from '@mantine/core';
import { networkLinkKinds } from '../utils/networkMap';

export default function NetworkBulkForm({ devices, initialTargets, initialSource, busy, error, onClose, onSave }) {
  const [sourceDevice, setSourceDevice] = useState(initialSource ? String(initialSource) : null);
  const [source, setSource] = useState(initialSource ? String(devices.find((device) => device.id === initialSource)?.interfaces[0]?.id) : null);
  const [targets, setTargets] = useState(initialTargets.map(String));
  const [interfaces, setInterfaces] = useState({});
  const [kind, setKind] = useState('unknown');
  const options = devices.map((device) => ({ value: String(device.id), label: `${device.name} · ${device.ip}` }));
  const sourceInterfaces = devices.find((device) => String(device.id) === sourceDevice)?.interfaces || [];
  const selectedDevices = devices.filter((device) => targets.includes(String(device.id)) && String(device.id) !== sourceDevice);
  const nicOptions = (items) => items.map((item) => ({ value: String(item.id), label: `${item.mac} · ${item.ip}` }));
  return (
    <Modal opened onClose={busy ? () => {} : onClose} title="Connect devices" centered size="lg">
      <form onSubmit={(event) => {
        event.preventDefault();
        if (!source || !selectedDevices.length || busy) return;
        onSave({ connections: selectedDevices.map((device) => ({ source: Number(source),
          target: Number(interfaces[device.id] || device.interfaces[0].id), kind })) });
      }}>
        <Stack gap="sm">
          {error && <Alert color="red">{error}</Alert>}
          <Select label="Connect to" data={options} searchable required value={sourceDevice} disabled={busy}
            onChange={(id) => { setSourceDevice(id); setSource(id ? String(devices.find((device) => String(device.id) === id).interfaces[0].id) : null); }} />
          <Select label="Network interface" data={nicOptions(sourceInterfaces)} required value={source} onChange={setSource} disabled={busy} />
          <MultiSelect label="Devices" data={options.filter((item) => item.value !== sourceDevice)} searchable required
            value={targets.filter((id) => id !== sourceDevice)} maxValues={200} onChange={setTargets} disabled={busy} />
          {selectedDevices.filter((device) => device.interfaces.length > 1).map((device) => (
            <Select key={device.id} label={`${device.name} interface`} data={nicOptions(device.interfaces)}
              value={interfaces[device.id] || String(device.interfaces[0].id)} disabled={busy}
              onChange={(value) => setInterfaces((current) => ({ ...current, [device.id]: value }))} required />
          ))}
          <Select label="Connection type" data={networkLinkKinds} value={kind} onChange={(value) => setKind(value || 'unknown')} disabled={busy} />
          <Group justify="flex-end" mt="sm">
            <Button variant="default" disabled={busy} onClick={onClose}>Cancel</Button>
            <Button type="submit" loading={busy} disabled={!source || !selectedDevices.length}>Connect {selectedDevices.length} devices</Button>
          </Group>
        </Stack>
      </form>
    </Modal>
  );
}
