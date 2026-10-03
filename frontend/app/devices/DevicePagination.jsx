import { Box, Button, Group, Select, Text } from '@mantine/core';
import { IconArrowLeft, IconArrowRight } from '@tabler/icons-react';

export default function DevicePagination({ pagination, limit, loading, refreshing, onLimitChange, onOffsetChange }) {
  const count = pagination.count || 0;
  const currentPage = Math.floor(pagination.offset / limit) + 1;
  const pageCount = Math.max(1, Math.ceil(count / limit));
  return (
    <Box className="device-pagination" p="md">
      <Group justify="space-between" align="flex-end" wrap="wrap" gap="sm">
        <Select
          className="device-page-size"
          w={120}
          label="Per page"
          allowDeselect={false}
          data={['25', '50', '75', '100']}
          value={String(limit)}
          onChange={(value) => onLimitChange(Number(value || 100))}
        />
        <Text size="sm" fw={600} className="device-page-number">
          Page {currentPage} of {pageCount}
        </Text>
        <Group gap="xs" wrap="nowrap">
          <Button
            size="xs"
            variant="default"
            leftSection={<IconArrowLeft size={16} />}
            disabled={pagination.previous_offset === null || loading || refreshing}
            onClick={() => onOffsetChange(pagination.previous_offset)}
          >Previous</Button>
          <Button
            size="xs"
            variant="default"
            rightSection={<IconArrowRight size={16} />}
            disabled={pagination.next_offset === null || loading || refreshing}
            onClick={() => onOffsetChange(pagination.next_offset)}
          >Next</Button>
        </Group>
      </Group>
    </Box>
  );
}
