import { Checkbox, Group, NumberInput, SimpleGrid, Stack, Switch, Text, TextInput } from '@mantine/core';

export default function NotificationRules({ controller }) {
  const {
    notifyDeviceOffline, notifyDeviceOnline, notifyNewDevices, notifyPortChanges,
    notifySpeedtestChanges, notifyVersionUpdates, quietHoursDayOptions, quietHoursDays,
    quietHoursEnabled, quietHoursEnd, quietHoursStart, setNotifyDeviceOffline,
    setNotifyDeviceOnline, setNotifyNewDevices, setNotifyPortChanges, setNotifySpeedtestChanges,
    setNotifyVersionUpdates, setQuietHoursDays, setQuietHoursEnabled, setQuietHoursEnd,
    setQuietHoursStart, setVersionCheckIntervalHours, versionCheckIntervalHours,
  } = controller;

  return (
    <Stack gap="sm">
      <Text fw={700}>Rules</Text>
      <SimpleGrid cols={{ base: 1, sm: 2 }}>
        <Switch label="New devices" checked={notifyNewDevices}
          onChange={(event) => setNotifyNewDevices(event.currentTarget.checked)} />
        <Switch label="Device comes online" checked={notifyDeviceOnline}
          onChange={(event) => setNotifyDeviceOnline(event.currentTarget.checked)} />
        <Switch label="Device goes offline" checked={notifyDeviceOffline}
          onChange={(event) => setNotifyDeviceOffline(event.currentTarget.checked)} />
        <Switch label="Port changes" checked={notifyPortChanges}
          onChange={(event) => setNotifyPortChanges(event.currentTarget.checked)} />
        <Switch label="New LanGuard version" checked={notifyVersionUpdates}
          onChange={(event) => setNotifyVersionUpdates(event.currentTarget.checked)} />
        <Switch label="Speedtest health changes" checked={notifySpeedtestChanges}
          onChange={(event) => setNotifySpeedtestChanges(event.currentTarget.checked)} />
      </SimpleGrid>
      <NumberInput
        label="Update check interval"
        description="How often LanGuard checks for a new release."
        value={versionCheckIntervalHours}
        onChange={(value) => setVersionCheckIntervalHours(Number(value) || 6)}
        min={1}
        max={168}
        step={1}
        suffix=" hr"
        allowDecimal={false}
        required
        maw={320}
      />
      <SimpleGrid cols={{ base: 1, sm: 3 }}>
        <Switch label="Quiet hours" checked={quietHoursEnabled}
          onChange={(event) => setQuietHoursEnabled(event.currentTarget.checked)} />
        <TextInput type="time" label="Quiet from" value={quietHoursStart}
          onChange={(event) => setQuietHoursStart(event.currentTarget.value)} disabled={!quietHoursEnabled} />
        <TextInput type="time" label="Quiet until" value={quietHoursEnd}
          onChange={(event) => setQuietHoursEnd(event.currentTarget.value)} disabled={!quietHoursEnabled} />
      </SimpleGrid>
      <Checkbox.Group
        label="Quiet days"
        description="For overnight ranges, early morning hours belong to the previous day."
        value={quietHoursDays}
        onChange={setQuietHoursDays}
      >
        <Group mt="xs" gap="lg">
          {quietHoursDayOptions.map((day) => (
            <Checkbox key={day.value} value={day.value} label={day.label} disabled={!quietHoursEnabled} />
          ))}
        </Group>
      </Checkbox.Group>
    </Stack>
  );
}
