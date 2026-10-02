'use client';

import { Badge, Box, Group, Stack, Table, Text, Title } from '@mantine/core';
import { IconBell } from '@tabler/icons-react';

import ActivityTablePanel from '../components/ActivityTablePanel';
import PageIcon from '../components/PageIcon';
import { activityRecordLabel, hasNextActivityPage } from '../utils/activity';
import { formatDate } from '../utils/date';

export default function NotificationsView({
  notifications: deliveries,
  timeZone,
  pagination,
  loadingMore,
  onLoadMore,
}) {
  return (
    <Stack gap="lg">
      <Group justify="space-between" align="flex-end">
        <Group gap="sm">
          <PageIcon>
            <IconBell size={26} />
          </PageIcon>
          <Box>
            <Title order={2}>Notifications</Title>
            <Text c="dimmed">Delivery status for external notification channels</Text>
          </Box>
        </Group>
        <Badge variant="light">{activityRecordLabel(pagination, deliveries.length)}</Badge>
      </Group>

      <ActivityTablePanel
        hasMore={hasNextActivityPage(pagination)}
        loadingMore={loadingMore}
        onLoadMore={onLoadMore}
      >
        <Table verticalSpacing="sm">
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Channel</Table.Th>
              <Table.Th>Status</Table.Th>
              <Table.Th>Attempts</Table.Th>
              <Table.Th>Created</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {deliveries.map((delivery) => (
              <Table.Tr key={delivery.id}>
                <Table.Td>{delivery.channel_display || delivery.channel}</Table.Td>
                <Table.Td>
                  <Badge color={delivery.status === 'sent' ? 'teal' : delivery.status === 'failed' ? 'red' : 'gray'} variant="light">
                    {delivery.status_display || delivery.status}
                  </Badge>
                </Table.Td>
                <Table.Td>{delivery.attempts}</Table.Td>
                <Table.Td>{formatDate(delivery.created_at, timeZone)}</Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      </ActivityTablePanel>
    </Stack>
  );
}
