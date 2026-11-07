import { memo, useEffect, useRef, useState } from 'react';
import { Handle, Position, BaseEdge, EdgeLabelRenderer } from '@xyflow/react';
import { IconGripVertical, IconChevronDown, IconChevronRight, IconDeviceMobile, IconWifi, IconPlugConnected, IconWorld, IconArrowDown, IconArrowUp } from '@tabler/icons-react';
import { ActionIcon, Tooltip } from '@mantine/core';
import { useDroppable } from '@dnd-kit/core';

import DeviceIconStack from '../components/DeviceIconStack';
import { formatRoleLabel } from '../utils/device';
import { networkLinkTitle } from '../utils/networkMap';
import NetworkRoamingIndicator from './NetworkRoamingIndicator';
import { internetSpeedtestStatus, formatInternetMetric } from '../utils/networkInternetStatus';
import { formatDate } from '../utils/date';

export const NetworkDeviceNode = memo(function NetworkDeviceNode({ data, isConnectable }) {
  const device = data.device;
  const { setNodeRef, isOver } = useDroppable({
    id: `network-node-${device.id}`, data: { deviceId: device.id }, disabled: !data.canDrop,
  });
  return (
    <article ref={setNodeRef} className={`topology-device-node ${data.summary ? 'infrastructure-node' : ''} ${device.online ? 'online' : 'offline'} ${data.connected ? '' : 'unconnected'} ${isOver ? 'drop-target' : ''}`}>
      <Handle type="target" position={Position.Top} isConnectable={isConnectable} />
      <div className="network-node-heading">
        {data.editing && <span className="network-node-grip" aria-label="Move device"><IconGripVertical size={16} /></span>}
        <DeviceIconStack device={device} size={22} />
        <button className="network-node-name nodrag" type="button" title={device.name}>{device.name}</button>
        {data.clientCount > 0 && <Tooltip label={data.summary ? 'View connected devices' : data.collapsed ? 'Expand connected devices' : 'Collapse connected devices'}>
          <ActionIcon size="xs" variant="subtle" className="nodrag nopan network-branch-toggle"
            aria-label={`${data.summary ? 'View' : data.collapsed ? 'Expand' : 'Collapse'} ${data.clientCount} devices under ${device.name}`}
            aria-expanded={data.summary ? undefined : !data.collapsed} onClick={(event) => { event.stopPropagation(); data.onToggleBranch(device.id); }}>
            {data.collapsed ? <IconChevronRight size={16} /> : <IconChevronDown size={16} />}
          </ActionIcon>
        </Tooltip>}
      </div>
      <div className="network-node-address">{device.ip}</div>
      {data.summary && <div className="network-node-summary">
        {data.clientCount ? <><span>{data.summary.online}/{data.clientCount} online</span>
          <span>{data.summary.ethernet} wired · {data.summary.wifi} Wi-Fi · {data.summary.unknown} unknown</span></>
          : <span>No saved connections</span>}
      </div>}
      <div className="network-node-footer">
        <span>{data.summary ? formatRoleLabel(device.role) : data.clientCount ? `${data.collapsed ? '+' : ''}${data.clientCount} devices` : data.connected ? formatRoleLabel(device.role) : 'Unconnected'}</span>
        <span><i className={`network-presence-dot ${device.online ? 'online' : ''}`} />{device.online ? 'Online' : 'Not online'}</span>
      </div>
      <Handle type="source" position={Position.Bottom} isConnectable={isConnectable} />
    </article>
  );
});

export const NetworkMobileNode = memo(function NetworkMobileNode({ data }) {
  const group = data.device.mobileGroup;
  const online = group.members.filter((device) => device.online).length;
  return <article className="topology-device-node infrastructure-node network-mobile-node">
    {group.parent != null && <Handle type="target" position={Position.Top} isConnectable={false} />}
    <div className="network-node-heading">
      {data.editing && <span className="network-node-grip" aria-label="Move mobile group"><IconGripVertical size={16} /></span>}
      <IconDeviceMobile size={24} />
      <button className="network-node-name nodrag" type="button" title={group.title} aria-label={group.title}>Mobile devices</button>
    </div>
    <div className="network-mobile-icons">{group.members.slice(0, 4).map((device) => <Tooltip key={device.id} label={`${device.name} · ${device.online ? 'Online' : 'Not online'}`}>
      <span className={device.online ? '' : 'offline'}><DeviceIconStack device={device} size={21} /></span></Tooltip>)}
      {group.members.length > 4 && <span>+{group.members.length - 4}</span>}</div>
    <div className="network-node-footer"><span>{online}/{group.members.length} online</span>
      <span>{group.parent == null ? <NetworkRoamingIndicator /> : group.kind === 'wifi' ? 'Wi-Fi' : group.kind === 'ethernet' ? 'Ethernet' : 'Connection unknown'}</span></div>
  </article>;
});

export const NetworkInternetNode = memo(function NetworkInternetNode({ data, isConnectable }) {
  const connection = data.device.internetConnection;
  const status = internetSpeedtestStatus(connection.speedtestTrackerPayload);
  const tested = status.testedAt ? formatDate(status.testedAt, connection.timeZone) : '';
  return <article className="topology-device-node infrastructure-node network-internet-node">
    <div className="network-node-heading">
      {data.editing && <span className="network-node-grip" aria-label="Move Internet"><IconGripVertical size={16} /></span>}
      <IconWorld size={30} />
      <button className="network-node-name nodrag" type="button">Internet</button>
    </div>
    <div className="network-internet-target">{connection.targetName || 'Uplink unavailable'}</div>
    {status.enabled && (status.hasSpeeds ? <div className="network-internet-speeds">
      <span title="Download" aria-label={`Download ${formatInternetMetric(status.download, 'Mbps')}`}><IconArrowDown size={14} /><strong>{formatInternetMetric(status.download, 'Mbps')}</strong></span>
      <span title="Upload" aria-label={`Upload ${formatInternetMetric(status.upload, 'Mbps')}`}><IconArrowUp size={14} /><strong>{formatInternetMetric(status.upload, 'Mbps')}</strong></span>
      <span>Ping {formatInternetMetric(status.ping, 'ms')}</span><span>Loss {formatInternetMetric(status.loss, '%')}</span>
    </div> : <div className="network-internet-no-result">{connection.speedtestTrackerPayload?.integration?.available ? 'No speed measurements' : 'Speedtest unavailable'}</div>)}
    {tested && <Tooltip label={`Speedtest Tracker · ${tested}`}><div className="network-internet-tested">Tested {tested}</div></Tooltip>}
    <div className="network-node-footer"><Tooltip multiline w={280} events={{ hover: true, focus: true, touch: true }} label={status.explanation}>
      <span className={`internet-verification ${status.color}`} tabIndex={0}>{status.verified && <i className={`network-presence-dot ${status.degraded ? 'degraded' : 'online'}`} />}{status.label}</span>
    </Tooltip><span>{connection.kind === 'wifi' ? 'Wi-Fi' : connection.kind === 'ethernet' ? 'Ethernet' : 'Unknown'}</span></div>
    <Handle type="source" position={Position.Bottom} isConnectable={isConnectable} />
  </article>;
});

export function NetworkConnectionEdge({ id, sourceX, sourceY, targetX, targetY, data, selected }) {
  const [hovered, setHovered] = useState(false);
  const hoverTimer = useRef(null);
  useEffect(() => () => clearTimeout(hoverTimer.current), []);
  const show = () => { clearTimeout(hoverTimer.current); setHovered(true); };
  const hide = () => { hoverTimer.current = setTimeout(() => setHovered(false), 100); };
  const lane = data.lane || 0;
  const direction = data.link.source_device < data.link.target_device ? 1 : -1;
  const bend = lane * 70 * direction;
  const dy = targetY - sourceY;
  const c1 = { x: sourceX + bend, y: sourceY + dy / 3 };
  const c2 = { x: targetX + bend, y: targetY - dy / 3 };
  const bus = data.busX != null && targetY > sourceY + 40;
  const busX = data.busX - lane * 8;
  const rowY = targetY - 18;
  const path = bus ? `M ${sourceX},${sourceY} V ${sourceY + 24} H ${busX} V ${rowY} H ${targetX} V ${targetY}`
    : `M ${sourceX},${sourceY} C ${c1.x},${c1.y} ${c2.x},${c2.y} ${targetX},${targetY}`;
  const labelX = bus ? (busX + targetX) / 2 : (sourceX + 3 * c1.x + 3 * c2.x + targetX) / 8;
  const labelY = bus ? rowY : (sourceY + 3 * c1.y + 3 * c2.y + targetY) / 8;
  const state = data.link.suggested ? 'suggested' : data.link.stale ? 'stale' : data.link.origin;
  const title = networkLinkTitle(data.link);
  return (
    <>
      <g onMouseEnter={show} onMouseLeave={hide}><title>{title}</title>
        <BaseEdge id={id} path={path} interactionWidth={24}
          style={{ strokeDasharray: data.link.kind === 'wifi' ? data.link.mobileGroup ? '10 4 2 4' : '8 5' : data.link.kind === 'unknown' ? '2 5' : 'none' }}
          className={`network-connection ${state} kind-${data.link.kind} ${data.link.mobileGroup ? 'mobile-group-link' : ''} ${selected ? 'selected' : ''}`} />
      </g>
      <EdgeLabelRenderer>
        <button type="button" className={`network-connection-label nodrag nopan ${state} ${selected || hovered || data.link.mobileGroup ? 'visible' : 'quiet'}`}
          style={{ transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)` }}
          title={title} aria-label={`Connection: ${title}`}
          onMouseEnter={show} onMouseLeave={hide}
          onClick={() => data.onSelect(data.link)}>
          {data.link.mobileGroup ? <IconDeviceMobile size={12} /> : data.link.kind === 'wifi' ? <IconWifi size={12} /> : data.link.kind === 'ethernet' ? <IconPlugConnected size={12} /> : null}
          {data.link.suggested ? 'LLDP suggestion' : title}
        </button>
      </EdgeLabelRenderer>
    </>
  );
}
