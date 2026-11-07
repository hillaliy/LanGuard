import { memo } from 'react';
import { Handle, Position, BaseEdge, EdgeLabelRenderer } from '@xyflow/react';
import { IconGripVertical } from '@tabler/icons-react';
import { useDroppable } from '@dnd-kit/core';

import DeviceIconStack from '../components/DeviceIconStack';
import { formatRoleLabel } from '../utils/device';
import { networkLinkTitle } from '../utils/networkMap';

export const NetworkDeviceNode = memo(function NetworkDeviceNode({ data, isConnectable }) {
  const device = data.device;
  const { setNodeRef, isOver } = useDroppable({
    id: `network-node-${device.id}`, data: { deviceId: device.id }, disabled: !data.canDrop,
  });
  return (
    <article ref={setNodeRef} className={`topology-device-node ${device.online ? 'online' : 'offline'} ${data.connected ? '' : 'unconnected'} ${isOver ? 'drop-target' : ''}`}>
      <Handle type="target" position={Position.Top} isConnectable={isConnectable} />
      <div className="network-node-heading">
        {data.editing && <span className="network-node-grip" aria-label="Move device"><IconGripVertical size={16} /></span>}
        <DeviceIconStack device={device} size={22} />
        <button className="network-node-name nodrag" type="button" title={device.name}>{device.name}</button>
      </div>
      <div className="network-node-address">{device.ip}</div>
      <div className="network-node-footer">
        <span>{data.connected ? formatRoleLabel(device.role) : 'Unconnected'}</span>
        <span><i className={`network-presence-dot ${device.online ? 'online' : ''}`} />{device.online ? 'Online' : 'Not online'}</span>
      </div>
      <Handle type="source" position={Position.Bottom} isConnectable={isConnectable} />
    </article>
  );
});

export function NetworkConnectionEdge({ id, sourceX, sourceY, targetX, targetY, data, selected }) {
  const lane = data.lane || 0;
  const direction = data.link.source_device < data.link.target_device ? 1 : -1;
  const bend = lane * 70 * direction;
  const dy = targetY - sourceY;
  const c1 = { x: sourceX + bend, y: sourceY + dy / 3 };
  const c2 = { x: targetX + bend, y: targetY - dy / 3 };
  const path = `M ${sourceX},${sourceY} C ${c1.x},${c1.y} ${c2.x},${c2.y} ${targetX},${targetY}`;
  const labelX = (sourceX + 3 * c1.x + 3 * c2.x + targetX) / 8;
  const labelY = (sourceY + 3 * c1.y + 3 * c2.y + targetY) / 8;
  const state = data.link.suggested ? 'suggested' : data.link.stale ? 'stale' : data.link.origin;
  const title = networkLinkTitle(data.link);
  return (
    <>
      <BaseEdge id={id} path={path} interactionWidth={24} className={`network-connection ${state} ${selected ? 'selected' : ''}`} />
      <EdgeLabelRenderer>
        <button type="button" className={`network-connection-label nodrag nopan ${state}`}
          style={{ transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)` }}
          title={title} aria-label={`Connection: ${title}`}
          onClick={() => data.onSelect(data.link)}>
          {data.link.suggested ? 'LLDP suggestion' : title}
        </button>
      </EdgeLabelRenderer>
    </>
  );
}
