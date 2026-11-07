import { useState } from 'react';
import { Alert, Button, Group, Modal, Select, Stack, TextInput } from '@mantine/core';
import { networkLinkKinds } from '../utils/networkMap';

export default function NetworkLinkForm({ initial, devices, busy, error, onClose, onSave }) {
  const deviceFor = (endpoint) => devices.find((device) => device.interfaces.some((item) => item.id === endpoint));
  const [sourceDevice, setSourceDevice] = useState(String(deviceFor(initial.source)?.id || ''));
  const [targetDevice, setTargetDevice] = useState(String(deviceFor(initial.target)?.id || ''));
  const [source, setSource] = useState(initial.source ? String(initial.source) : null);
  const [target, setTarget] = useState(initial.target ? String(initial.target) : null);
  const [kind, setKind] = useState(initial.kind || 'unknown');
  const [label, setLabel] = useState(initial.label || '');
  const [sourcePort, setSourcePort] = useState(initial.source_port || '');
  const [targetPort, setTargetPort] = useState(initial.target_port || '');
  const options = devices.map((device) => ({ value: String(device.id), label: `${device.name} · ${device.ip}` }));
  const interfacesFor = (id) => devices.find((device) => String(device.id) === id)?.interfaces || [];
  const interfaceOptions = (id) => interfacesFor(id).map((item) => ({ value: String(item.id), label: `${item.mac} · ${item.ip}` }));

  return (
    <Modal opened onClose={busy ? () => {} : onClose} title={initial.id ? 'Edit connection' : 'Add connection'} centered size="lg">
      <form onSubmit={(event) => {
        event.preventDefault();
        onSave({ source: Number(source), target: Number(target), kind, label: label.trim(),
          source_port: sourcePort.trim(), target_port: targetPort.trim(), ...(initial.id ? { revision: initial.revision } : {}) });
      }}>
        <Stack gap="sm">
          {error && <Alert color="red">{error}</Alert>}
          <Select label="From device" data={options} searchable required value={sourceDevice || null}
            onChange={(value) => { setSourceDevice(value || ''); setSource(interfacesFor(value)[0] ? String(interfacesFor(value)[0].id) : null); }} />
          <Select label="From interface" data={interfaceOptions(sourceDevice)} value={source} required onChange={setSource} />
          <TextInput label="From port" value={sourcePort} maxLength={128} onChange={(event) => setSourcePort(event.currentTarget.value)} />
          <Select label="To device" data={options.filter((option) => option.value !== sourceDevice)} searchable required value={targetDevice || null}
            onChange={(value) => { setTargetDevice(value || ''); setTarget(interfacesFor(value)[0] ? String(interfacesFor(value)[0].id) : null); }} />
          <Select label="To interface" data={interfaceOptions(targetDevice)} value={target} required onChange={setTarget} />
          <TextInput label="To port" value={targetPort} maxLength={128} onChange={(event) => setTargetPort(event.currentTarget.value)} />
          <Select label="Connection type" data={networkLinkKinds} value={kind} onChange={(value) => setKind(value || 'unknown')} />
          <TextInput label="Label" value={label} maxLength={100} onChange={(event) => setLabel(event.currentTarget.value)} />
          <Group justify="flex-end" mt="sm">
            <Button variant="default" disabled={busy} onClick={onClose}>Cancel</Button>
            <Button type="submit" loading={busy} disabled={!source || !target || sourceDevice === targetDevice}>Save connection</Button>
          </Group>
        </Stack>
      </form>
    </Modal>
  );
}
