import { Badge, Tooltip } from '@mantine/core';
import { IconRouter } from '@tabler/icons-react';

export function deviceRisk(device) {
  const level = device?.risk_level || 'low';
  const labels = {
    high: 'High',
    medium: 'Medium',
    low: 'Low',
  };
  const colors = {
    high: 'red',
    medium: 'orange',
    low: 'teal',
  };
  const reasons = device?.risk_reasons || [];
  return {
    level,
    label: labels[level] || 'Low',
    color: colors[level] || 'gray',
    reasons,
    tooltip: reasons.length ? reasons.join('\n') : 'No obvious risk',
  };
}

export function RiskBadge({ device, compact = false }) {
  const risk = deviceRisk(device);

  return (
    <Tooltip label={risk.tooltip} multiline withArrow>
      <Badge
        className="device-risk-badge"
        color={risk.color}
        variant={risk.level === 'low' ? 'light' : 'filled'}
        size={compact ? 'sm' : 'md'}
      >
        {compact ? risk.label : `${risk.label} risk`}
      </Badge>
    </Tooltip>
  );
}

export function GatewayBadge({ device, compact = false }) {
  if (!device?.is_gateway) return null;

  return (
    <Badge
      className="device-gateway-badge"
      color="blue"
      variant="light"
      size={compact ? 'sm' : 'md'}
      leftSection={<IconRouter size={compact ? 12 : 14} stroke={2} />}
    >
      Gateway
    </Badge>
  );
}

export function DeviceClassificationBadge({ device, compact = false }) {
  const archived = Boolean(device?.archived);
  const visitor = Boolean(device?.is_visitor);
  const known = Boolean(device?.known);
  const color = archived ? 'gray' : visitor ? 'blue' : known ? 'teal' : 'yellow';
  const label = archived ? 'Archived' : visitor ? 'Visitor' : known ? 'Known' : 'New';

  return (
    <Badge
      className="device-known-badge"
      color={color}
      variant="light"
      size={compact ? 'sm' : 'md'}
    >
      {label}
    </Badge>
  );
}
