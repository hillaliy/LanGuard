import { Box, Text } from '@mantine/core';

export default function SummaryMetric({ label, value, align = 'left', nowrap = false }) {
  return (
    <Box ta={align} style={{ minWidth: 0 }}>
      <Text size="sm" c="dimmed" fw={600}>{label}</Text>
      <Text
        className={`dashboard-summary-value${nowrap ? ' dashboard-summary-value-nowrap' : ''}`}
        fw={800}
      >
        {value}
      </Text>
    </Box>
  );
}
