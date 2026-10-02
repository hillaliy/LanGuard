'use client';

import {
  Badge,
  Box,
  Group,
  Select,
  Stack,
  Table,
  Text,
  Title,
} from '@mantine/core';
import { IconBell } from '@tabler/icons-react';

import { apiRequest } from '../api';
import ActivityTablePanel from '../components/ActivityTablePanel';
import PageIcon from '../components/PageIcon';
import {
  activityRecordLabel,
  eventDeviceId,
  hasNextActivityPage,
} from '../utils/activity';
import { formatDate } from '../utils/date';

const eventTypeOptions = [
  { value: 'new_device', label: 'New devices' },
  { value: 'device_online', label: 'Online events' },
  { value: 'device_offline', label: 'Offline events' },
  { value: 'ip_changed', label: 'IP changes' },
  { value: 'version_available', label: 'Version updates' },
  { value: 'speedtest_health_changed', label: 'Speedtest health changes' },
  { value: 'port_opened', label: 'Opened ports' },
  { value: 'port_closed', label: 'Closed ports' },
  { value: 'container_discovered', label: 'New containers' },
  { value: 'container_port_exposed', label: 'Container port changes' },
];

export default function EventsView({
  events,
  eventType,
  setEventType,
  timeZone,
  pagination,
  loadingMore,
  onLoadMore,
  onSelectDevice,
  onError,
}) {
  async function handleSelectEventDevice(event) {
    const id = eventDeviceId(event);
    if (id === null || id === undefined) {
      return;
    }

    try {
      const payload = await apiRequest(`device/?id=${id}`);
      if (payload.data) {
        onSelectDevice(payload.data);
      }
    } catch (err) {
      onError(err);
    }
  }

  return (
    <Stack gap="lg">
      <Group justify="space-between" align="flex-end" wrap="wrap">
        <Group gap="sm">
          <PageIcon>
            <IconBell size={26} />
          </PageIcon>
          <Box>
            <Title order={2}>Events</Title>
            <Text c="dimmed">Network changes and alert decisions</Text>
          </Box>
        </Group>
        <Group gap="sm">
          <Badge variant="light">{activityRecordLabel(pagination, events.length)}</Badge>
          <Select
            w={220}
            placeholder="Event type"
            clearable
            data={eventTypeOptions}
            value={eventType}
            onChange={(value) => setEventType(value || '')}
          />
        </Group>
      </Group>

      <ActivityTablePanel
        hasMore={hasNextActivityPage(pagination)}
        loadingMore={loadingMore}
        onLoadMore={onLoadMore}
      >
        <Table verticalSpacing="sm">
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Type</Table.Th>
              <Table.Th>Message</Table.Th>
              <Table.Th>Created</Table.Th>
              <Table.Th>Status</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {events.map((event) => {
              const deviceId = eventDeviceId(event);
              const hasDevice = deviceId !== null && deviceId !== undefined;
              return (
                <Table.Tr
                  key={event.id}
                  className={hasDevice ? 'activity-clickable-row' : undefined}
                  tabIndex={hasDevice ? 0 : undefined}
                  role={hasDevice ? 'button' : undefined}
                  aria-label={hasDevice ? `Open device for ${event.message || 'event'}` : undefined}
                  onClick={hasDevice ? () => handleSelectEventDevice(event) : undefined}
                  onKeyDown={hasDevice ? (keyboardEvent) => {
                    if (keyboardEvent.key === 'Enter' || keyboardEvent.key === ' ') {
                      keyboardEvent.preventDefault();
                      handleSelectEventDevice(event);
                    }
                  } : undefined}
                >
                  <Table.Td>
                    <Badge variant="light">
                      {event.event_type_display || event.event_type}
                    </Badge>
                  </Table.Td>
                  <Table.Td>{event.message}</Table.Td>
                  <Table.Td>{formatDate(event.created_at, timeZone)}</Table.Td>
                  <Table.Td>
                    <Badge color={event.notified ? 'teal' : 'gray'} variant="light">
                      {event.notified ? 'Handled' : 'Pending'}
                    </Badge>
                  </Table.Td>
                </Table.Tr>
              );
            })}
          </Table.Tbody>
        </Table>
      </ActivityTablePanel>
    </Stack>
  );
}
