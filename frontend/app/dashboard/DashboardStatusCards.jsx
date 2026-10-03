import { Box, Paper, Text, ThemeIcon } from '@mantine/core';
import { IconDeviceDesktop, IconNetwork, IconQuestionMark, IconWifi } from '@tabler/icons-react';

function DashboardStatusCard({ icon, label, value, secondaryItems = [], color }) {
  const visibleSecondaryItems = secondaryItems
    .map((item) => ({ ...item, value: Number(item.value) || 0 }))
    .filter((item) => item.value > 0);

  return (
    <Paper className="dashboard-status-card">
      <ThemeIcon
        className={`dashboard-status-icon ${color}`}
        color={color}
        size={56}
        radius={14}
        variant="light"
      >
        {icon}
      </ThemeIcon>
      <Box>
        <Text className="dashboard-status-label" fw={800}>{label}</Text>
        <Text className="dashboard-status-value" fw={900}>{value}</Text>
        {visibleSecondaryItems.length > 0 && (
          <Text component="div" className="dashboard-status-secondary" c="dimmed" fw={700}>
            {visibleSecondaryItems.map((item) => (
              <span className="dashboard-status-secondary-item" key={item.singular}>
                {item.value.toLocaleString()} {item.value === 1 ? item.singular : item.plural}
              </span>
            ))}
          </Text>
        )}
      </Box>
    </Paper>
  );
}

export default function DashboardStatusCards({ counters = {} }) {
  return (
    <div className="dashboard-status-grid">
      <DashboardStatusCard
        icon={<IconDeviceDesktop size={30} />}
        label="Devices"
        value={counters.all_devices ?? 0}
        secondaryItems={[
          { value: counters.visitor_devices, singular: 'visitor', plural: 'visitors' },
          { value: counters.archived_devices, singular: 'archived', plural: 'archived' },
        ]}
        color="blue"
      />
      <DashboardStatusCard
        icon={<IconWifi size={30} />}
        label="Online"
        value={counters.online_devices ?? 0}
        secondaryItems={[
          { value: counters.online_visitors, singular: 'visitor', plural: 'visitors' },
        ]}
        color="green"
      />
      <DashboardStatusCard
        icon={<IconQuestionMark size={30} />}
        label="Unknown"
        value={counters.new_devices ?? 0}
        color="orange"
      />
      <DashboardStatusCard
        icon={<IconNetwork size={30} />}
        label="Open Ports"
        value={counters.open_ports ?? 0}
        color="purple"
      />
    </div>
  );
}
