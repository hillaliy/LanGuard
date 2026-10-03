import { Badge, Box, Group, Paper, Text, UnstyledButton } from '@mantine/core';
import { IconNetwork } from '@tabler/icons-react';
import { RiskBadge } from '../components/DeviceBadges';
import DeviceIconStack, { normalizeDeviceIcon } from '../components/DeviceIconStack';
import PortSummary from '../components/PortGuidance';
import { deviceStatus, displayDeviceName, formatRoleLabel } from '../utils/device';
import { isPortGuidanceInteraction } from './deviceListUtils';

function deviceMapShape(device) {
  const icon = normalizeDeviceIcon(device.icon);
  if (device.is_gateway) return 'router';
  if (!device.known || icon === 'unknown') return 'unknown';
  if (icon === 'router') return 'router';
  if (['server', 'nas'].includes(icon)) return 'server';
  if (['smart-hub', 'phone', 'tablet', 'smart-watch', 'robot-vacuum', 'power-strip', 'smart-power-strip', 'smart-relay', 'power-meter', 'game-console', 'lock'].includes(icon)) {
    return 'compact';
  }
  if (['tv', 'streamer', 'security-camera'].includes(icon)) return 'media';
  return 'device';
}

function NetworkMapDeviceNode({ device, onSelectDevice }) {
  const status = deviceStatus(device);
  return (
    <UnstyledButton
      component="div"
      className={`network-device-node ${deviceMapShape(device)} ${device.online ? 'online' : 'offline'}`}
      role="button"
      tabIndex={0}
      onClick={(event) => {
        if (!isPortGuidanceInteraction(event)) onSelectDevice(device);
      }}
      onKeyDown={(event) => {
        if (!isPortGuidanceInteraction(event) && ['Enter', ' '].includes(event.key)) {
          event.preventDefault();
          onSelectDevice(device);
        }
      }}
    >
      <Group justify="space-between" align="flex-start" wrap="nowrap">
        <span className="network-device-icon">
          <DeviceIconStack device={device} size={22} />
        </span>
        <Group gap={4} justify="flex-end" wrap="wrap">
          <RiskBadge device={device} compact />
          <Badge color={status.color} variant="light">{status.label}</Badge>
        </Group>
      </Group>
      <Text fw={800} className="network-node-name">{displayDeviceName(device)}</Text>
      <Text size="xs" className="mobile-mono-value">{device.ip}</Text>
      <div className="network-device-ports">
        <PortSummary ports={device.open_ports || []} />
      </div>
    </UnstyledButton>
  );
}

function buildRoleSections(devices) {
  const sectionsByRole = new Map();
  devices.forEach((device) => {
    const roleLabel = formatRoleLabel(device.role || 'device');
    if (!sectionsByRole.has(roleLabel)) sectionsByRole.set(roleLabel, []);
    sectionsByRole.get(roleLabel).push(device);
  });
  return Array.from(sectionsByRole.entries())
    .map(([role, devicesForRole]) => ({
      role,
      devices: devicesForRole.sort((left, right) =>
        String(left.name || left.ip || '').localeCompare(String(right.name || right.ip || ''))
      ),
    }))
    .sort((left, right) => left.role.localeCompare(right.role));
}

export default function DeviceRolesView({ devices = [], totalCount = 0, onSelectDevice }) {
  const roleSections = buildRoleSections(devices);
  return (
    <Box p="md">
      <Paper className="rooms-map-panel" radius="md">
        <div className="rooms-map">
          {roleSections.length ? (
            <div className="rooms-map-list">
              {roleSections.map((section) => (
                <section className="rooms-map-room" key={section.role}>
                  <Group justify="space-between" align="center" mb="sm" wrap="nowrap">
                    <Group gap="xs" wrap="nowrap" className="rooms-map-title">
                      <span className="rooms-map-icon"><IconNetwork size={22} /></span>
                      <Text fw={800} className="rooms-map-room-name">{section.role}</Text>
                    </Group>
                    <Badge variant="light" color="indigo">{section.devices.length}</Badge>
                  </Group>
                  <div className="network-device-grid">
                    {section.devices.map((device) => (
                      <NetworkMapDeviceNode
                        key={device.id}
                        device={device}
                        onSelectDevice={onSelectDevice}
                      />
                    ))}
                  </div>
                </section>
              ))}
            </div>
          ) : (
            <Text c="dimmed" ta="center" py="xl">No devices to show.</Text>
          )}
        </div>
      </Paper>
      <Text size="xs" c="dimmed" mt="sm">
        {totalCount > devices.length
          ? `Showing ${devices.length} of ${totalCount} devices grouped by role.`
          : `Showing ${devices.length} ${devices.length === 1 ? 'device' : 'devices'} grouped by role.`}
      </Text>
    </Box>
  );
}
