import { Group, Text, ThemeIcon, Title } from '@mantine/core';

export function ThemeIconLike({ children, color, size = 42 }) {
  return (
    <ThemeIcon
      color={color}
      size={size}
      radius="md"
      variant="light"
      style={{
        background: `var(--mantine-color-${color}-1)`,
        color: `var(--mantine-color-${color}-7)`,
      }}
    >
      {children}
    </ThemeIcon>
  );
}

export function DashboardCardHeader({ icon, title, badge }) {
  return (
    <Group className="dashboard-card-header" justify="space-between" align="center" wrap="nowrap">
      <Group className="dashboard-card-header-title" gap="sm" wrap="nowrap">
        {icon}
        <Title order={3}>{title}</Title>
      </Group>
      {badge}
    </Group>
  );
}

export function SummaryRow({ label, value }) {
  return (
    <Group justify="space-between" wrap="nowrap">
      <Text c="dimmed" fw={600}>{label}</Text>
      <Text fw={800}>{value}</Text>
    </Group>
  );
}
