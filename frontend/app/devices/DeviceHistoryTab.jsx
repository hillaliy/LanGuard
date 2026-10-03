import {
  Badge, Box, Button, Divider, Group, LoadingOverlay, ScrollArea, SegmentedControl,
  SimpleGrid, Stack, Table, Tabs, Text, Title, Tooltip,
} from '@mantine/core';

import { activityRecordLabel, hasNextActivityPage } from '../utils/activity';
import SummaryMetric from '../components/SummaryMetric';
import { formatDate } from '../utils/date';
import { formatRoleLabel } from '../utils/device';
import { formatAvailabilityDuration } from './DeviceDetailFields';

export default function DeviceHistoryTab({
  availability,
  availabilityPeriod,
  eventPagination,
  events,
  loadMoreEvents,
  loadingAvailability,
  loadingMoreEvents,
  setAvailabilityPeriod,
  timeZone,
}) {
  return (
    <Tabs.Panel value="history" pt="lg">
      <Stack gap="md">
        <section className="device-availability-section">
          <Group justify="space-between" align="flex-start" wrap="wrap" gap="md">
            <Box>
              <Title order={4}>Availability</Title>
              <Text size="sm" c="dimmed">
                Online and offline time from retained device status history.
              </Text>
            </Box>
            <SegmentedControl
              value={availabilityPeriod}
              onChange={setAvailabilityPeriod}
              data={[
                { value: 'day', label: 'Day' },
                { value: 'week', label: 'Week' },
                { value: 'month', label: 'Month' },
                { value: 'year', label: 'Year' },
              ]}
            />
          </Group>

          <Box pos="relative" mt="lg" mih={116}>
            <LoadingOverlay visible={loadingAvailability} />
            {availability && (
              <Stack gap="md">
                <SimpleGrid cols={{ base: 1, xs: 3 }}>
                  <SummaryMetric
                    label="Availability"
                    value={availability.availability_percent == null
                      ? 'No data'
                      : `${availability.availability_percent}%`}
                  />
                  <SummaryMetric
                    label="Online time"
                    value={formatAvailabilityDuration(availability.online_seconds)}
                  />
                  <SummaryMetric
                    label="Status changes"
                    value={Number(availability.status_changes || 0).toLocaleString()}
                  />
                </SimpleGrid>

                <div className="availability-timeline" aria-label="Device availability timeline">
                  {(availability.segments || []).map((segment, index) => (
                    <Tooltip
                      key={`${segment.started_at}-${index}`}
                      label={`${formatRoleLabel(segment.status)}: ${formatDate(segment.started_at, timeZone)} to ${formatDate(segment.ended_at, timeZone)}`}
                    >
                      <span
                        className={`availability-segment ${segment.status}`}
                        style={{ flexGrow: Math.max(Number(segment.duration_seconds || 0), 1) }}
                      />
                    </Tooltip>
                  ))}
                </div>
                <Group justify="space-between" wrap="nowrap">
                  <Text size="xs" c="dimmed">
                    {availability.period === 'day'
                      ? '24 hours ago'
                      : availability.period === 'week'
                        ? '7 days ago'
                        : availability.period === 'month'
                          ? '30 days ago'
                          : '1 year ago'}
                  </Text>
                  <Text size="xs" c="dimmed">Now</Text>
                </Group>
                <Group gap="md" wrap="wrap" className="availability-legend">
                  <Text size="xs"><span className="availability-key online" />Online</Text>
                  <Text size="xs"><span className="availability-key offline" />Offline</Text>
                  <Text size="xs"><span className="availability-key unknown" />No data</Text>
                </Group>
                {Number(availability.coverage_percent || 0) < 100 && (
                  <Text size="xs" c="dimmed">
                    History coverage: {availability.coverage_percent}%. Missing time is not included
                    in the availability calculation.
                  </Text>
                )}
              </Stack>
            )}
          </Box>
        </section>

        <Divider />
        <Group justify="space-between">
          <Box>
            <Title order={4}>Device history</Title>
            <Text size="sm" c="dimmed">
              {activityRecordLabel(eventPagination, events.length)}
            </Text>
          </Box>
        </Group>
        <ScrollArea.Autosize mah={520} type="auto" className="activity-table-scroll">
          <Table striped highlightOnHover verticalSpacing="sm">
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Time</Table.Th>
                <Table.Th>Event</Table.Th>
                <Table.Th>Details</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {events.map((event) => (
                <Table.Tr key={event.id}>
                  <Table.Td className="device-history-time">
                    {formatDate(event.created_at, timeZone)}
                  </Table.Td>
                  <Table.Td>
                    <Badge variant="light">
                      {event.event_type_display || formatRoleLabel(event.event_type)}
                    </Badge>
                  </Table.Td>
                  <Table.Td>{event.message || '-'}</Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </ScrollArea.Autosize>
        {!events.length && <Text c="dimmed">No history recorded for this device.</Text>}
        {hasNextActivityPage(eventPagination) && (
          <Group justify="center">
            <Button variant="default" onClick={loadMoreEvents} loading={loadingMoreEvents}>
              Load older events
            </Button>
          </Group>
        )}
      </Stack>
    </Tabs.Panel>
  );
}
