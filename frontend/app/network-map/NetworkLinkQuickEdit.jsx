import { useState } from 'react';
import { Button, Group, Select, Stack, TextInput } from '@mantine/core';
import { IconCheck } from '@tabler/icons-react';
import { networkLinkKinds } from '../utils/networkMap';

export default function NetworkLinkQuickEdit({ link, busy, onSave }) {
  const [kind, setKind] = useState(link.kind);
  const [sourcePort, setSourcePort] = useState(link.source_port);
  const [targetPort, setTargetPort] = useState(link.target_port);
  const [label, setLabel] = useState(link.label);
  const changed = kind !== link.kind || sourcePort !== link.source_port || targetPort !== link.target_port || label !== link.label;
  return (
    <form onSubmit={(event) => {
      event.preventDefault();
      if (!changed || busy) return;
      onSave({ source: link.source, target: link.target, revision: link.revision,
        kind, source_port: sourcePort.trim(), target_port: targetPort.trim(), label: label.trim() });
    }}>
      <Stack gap="sm">
        <Select label="Connection type" data={networkLinkKinds} value={kind} onChange={(value) => setKind(value || 'unknown')} disabled={busy} />
        <TextInput label="From port" value={sourcePort} maxLength={128} onChange={(event) => setSourcePort(event.currentTarget.value)} disabled={busy} />
        <TextInput label="To port" value={targetPort} maxLength={128} onChange={(event) => setTargetPort(event.currentTarget.value)} disabled={busy} />
        <TextInput label="Label" value={label} maxLength={100} onChange={(event) => setLabel(event.currentTarget.value)} disabled={busy} />
        <Group justify="flex-end"><Button type="submit" loading={busy} disabled={!changed} leftSection={<IconCheck size={16} />}>Save changes</Button></Group>
      </Stack>
    </form>
  );
}
