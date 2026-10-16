import { Box, Button, Group, Text } from '@mantine/core';
import { IconHistory } from '@tabler/icons-react';

import { formatDate } from '../utils/date';

export default function DeviceNetworkChange({ event, onShowHistory, timeZone }) {
  if (!event) return null;

  return (
    <Box mt="lg">
      <Group justify="space-between" gap="xs">
        <Text size="xs" c="dimmed">Last network change</Text>
        <Button
          variant="subtle"
          size="compact-xs"
          leftSection={<IconHistory size={14} />}
          onClick={onShowHistory}
        >
          View history
        </Button>
      </Group>
      <Text size="sm" fw={500} mt={4}>
        {event.event_type_display}
      </Text>
      {event.message && <Text size="sm" className="wrap-text">{event.message}</Text>}
      <Text size="xs" c="dimmed" mt={4}>{formatDate(event.created_at, timeZone)}</Text>
    </Box>
  );
}
