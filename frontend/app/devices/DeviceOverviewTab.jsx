import {
  Alert, Box, Button, Divider, Group, Loader, NumberInput, Select, SimpleGrid, Stack,
  Switch, Tabs, Text, TextInput, Textarea, Title,
} from '@mantine/core';
import { IconArrowUpRight, IconExternalLink, IconTrash, IconX } from '@tabler/icons-react';

import { PortGuidanceBadge } from '../components/PortGuidance';
import { formatDate } from '../utils/date';
import {
  buildRoomOptions,
  externalUrlUsesIPv4,
  formatRoleLabel,
  validExternalUrl,
} from '../utils/device';
import {
  DeviceField,
  DeviceIconPicker,
  HomeBoxItemPicker,
  IdentityConfidenceField,
  RoomField,
  deviceNotificationPreferenceOptions,
  devicePresenceExpectationOptions,
  deviceRoleOptions,
  formatDeviceNotificationPreference,
  formatDevicePresenceExpectation,
  formatOfflineAttention,
} from './DeviceDetailFields';
import DeviceSnmpInventory from './DeviceSnmpInventory';
import DeviceInterfacesSection from './DeviceInterfacesSection';

export default function DeviceOverviewTab({
  activeUrl,
  attentionAcknowledged,
  canEditDevices,
  comments,
  currentStatus,
  deleteConfirm,
  detectedWebUrl,
  detectingWebUrl,
  device,
  editing,
  externalUrl,
  externalUrlFollowDeviceIp,
  homeboxItemId,
  icon,
  isVisitor,
  known,
  name,
  offlineAttentionAfterDays,
  offlineNotificationPreference,
  onSeparateInterface,
  onlineNotificationPreference,
  presenceExpectation,
  role,
  room,
  roomOptions,
  secondaryIcon,
  setAttentionAcknowledged,
  setComments,
  setExternalUrl,
  setExternalUrlFollowDeviceIp,
  setHomeboxItemId,
  setIcon,
  setIsVisitor,
  setKnown,
  setName,
  setOfflineAttentionAfterDays,
  setOfflineNotificationPreference,
  setOnlineNotificationPreference,
  setPresenceExpectation,
  setRole,
  setRoom,
  setSecondaryIcon,
  timeZone,
}) {
  return (
    <Tabs.Panel value="overview" pt="lg">
      {!editing && device.homebox_link && (
        <Button
          component="a"
          href={device.homebox_link}
          target="_blank"
          rel="noopener noreferrer"
          variant="default"
          leftSection={<IconExternalLink size={18} />}
          mb="md"
        >
          Open in HomeBox
        </Button>
      )}
      {editing ? (
        <Stack gap="lg">
          <SimpleGrid cols={{ base: 1, md: 2 }}>
            <DeviceField label="Name" value={name} editable required onChange={setName} />
            <RoomField
              value={room}
              onChange={setRoom}
              roomOptions={buildRoomOptions([], room).concat(
                roomOptions.filter((option) => option.value !== room)
              )}
            />
            <Box className="device-field editable">
              <Text size="xs" c="dimmed">Role</Text>
              <Select
                classNames={{ input: 'device-field-input' }}
                data={deviceRoleOptions.map((value) => ({
                  value,
                  label: formatRoleLabel(value),
                }))}
                value={role}
                onChange={(value) => setRole(value || 'device')}
              />
            </Box>
            <Stack gap="xs">
              <TextInput
                label="External link"
                placeholder="https://192.168.0.20"
                value={externalUrl}
                error={!validExternalUrl(externalUrl)
                  ? 'Enter a valid HTTP or HTTPS URL without embedded credentials.'
                  : null}
                onChange={(event) => {
                  const nextExternalUrl = event.currentTarget.value;
                  setExternalUrl(nextExternalUrl);
                  if (!nextExternalUrl.trim()) {
                    setExternalUrlFollowDeviceIp(false);
                  }
                }}
              />
              {detectedWebUrl && !externalUrl.trim() && (
                <Button
                  variant="subtle"
                  size="compact-sm"
                  w="fit-content"
                  onClick={() => {
                    setExternalUrl(detectedWebUrl);
                    setExternalUrlFollowDeviceIp(true);
                  }}
                >
                  Use detected web interface
                </Button>
              )}
              <Switch
                label="Follow device IP"
                description="Replace only the link hostname when this device's IPv4 address changes."
                checked={externalUrlFollowDeviceIp}
                disabled={!externalUrlUsesIPv4(externalUrl)}
                onChange={(event) => setExternalUrlFollowDeviceIp(event.currentTarget.checked)}
              />
              {externalUrlFollowDeviceIp && activeUrl && activeUrl !== externalUrl.trim() && (
                <Text size="xs" c="dimmed" className="wrap-text">
                  Opens: {activeUrl}
                </Text>
              )}
            </Stack>
            {device.homebox_available ? (
              <HomeBoxItemPicker value={homeboxItemId} onChange={setHomeboxItemId} />
            ) : homeboxItemId && (
              <Button
                variant="default"
                leftSection={<IconX size={16} />}
                onClick={() => setHomeboxItemId(null)}
              >
                Unlink HomeBox item
              </Button>
            )}
          </SimpleGrid>
          <SimpleGrid cols={{ base: 1, md: 2 }}>
            <DeviceIconPicker value={icon} onChange={setIcon} />
            <DeviceIconPicker
              label="Secondary icon"
              value={secondaryIcon}
              onChange={setSecondaryIcon}
            />
          </SimpleGrid>
          <Textarea
            label="Comments"
            placeholder="Add notes about this device"
            value={comments}
            onChange={(event) => setComments(event.currentTarget.value)}
            autosize
            minRows={3}
            maxRows={8}
          />
          <Divider label="Presence notifications" labelPosition="left" />
          <Box>
            <Text size="sm" c="dimmed" mb="sm">
              Override the global Online and Offline rules for this device. Quiet hours and
              configured notification channels still apply.
            </Text>
            <SimpleGrid cols={{ base: 1, md: 2 }}>
              <Select
                label="When device comes online"
                description="Controls Online notifications for this device."
                data={deviceNotificationPreferenceOptions}
                value={onlineNotificationPreference}
                onChange={(value) => setOnlineNotificationPreference(value || 'inherit')}
              />
              <Select
                label="When device goes offline"
                description="Controls Offline notifications for this device."
                data={deviceNotificationPreferenceOptions}
                value={offlineNotificationPreference}
                onChange={(value) => setOfflineNotificationPreference(value || 'inherit')}
              />
            </SimpleGrid>
          </Box>
          <Divider label="Presence expectations" labelPosition="left" />
          <Box>
            <Text size="sm" c="dimmed" mb="sm">
              Decide when a prolonged absence should appear under Needs Attention.
              Visitor devices are always excluded.
            </Text>
            <SimpleGrid cols={{ base: 1, md: 2 }}>
              <Select
                label="Presence expectation"
                description="Automatic allows more time for portable devices."
                data={devicePresenceExpectationOptions}
                value={presenceExpectation}
                onChange={(value) => {
                  const nextValue = value || 'automatic';
                  setPresenceExpectation(nextValue);
                  if (!['always', 'occasional'].includes(nextValue)) {
                    setOfflineAttentionAfterDays('');
                  }
                }}
              />
              {['always', 'occasional'].includes(presenceExpectation) && (
                <NumberInput
                  label="Alert after days offline"
                  description={`Leave empty to use ${presenceExpectation === 'occasional' ? 21 : 7} days.`}
                  placeholder={presenceExpectation === 'occasional' ? '21' : '7'}
                  min={1}
                  max={3650}
                  allowDecimal={false}
                  value={offlineAttentionAfterDays}
                  onChange={setOfflineAttentionAfterDays}
                />
              )}
            </SimpleGrid>
            {presenceExpectation === 'automatic' && (
              <Text size="xs" c="dimmed" mt="sm">
                Uses 21 days for phones, tablets, watches, and laptops; 7 days for other devices.
              </Text>
            )}
            {presenceExpectation === 'never' && (
              <Text size="xs" c="dimmed" mt="sm">
                This device will not need attention because it has been offline for a long time.
              </Text>
            )}
          </Box>
          <Group align="flex-start">
            <Switch
              label="Known device"
              checked={known}
              onChange={(event) => {
                const nextKnown = event.currentTarget.checked;
                setKnown(nextKnown);
                if (!nextKnown) {
                  setIsVisitor(false);
                  setAttentionAcknowledged(false);
                }
              }}
            />
            <Switch
              label="Visitor device"
              description="Keeps this device recognized while treating its presence as temporary."
              checked={isVisitor}
              onChange={(event) => {
                const nextVisitor = event.currentTarget.checked;
                setIsVisitor(nextVisitor);
                if (nextVisitor) {
                  setKnown(true);
                }
              }}
            />
            <Switch
              label="This device does not need attention"
              description="Acknowledges the current risk. Risk changes will require attention again."
              checked={attentionAcknowledged}
              disabled={!known || (!device.needs_attention && !device.attention_acknowledged)}
              onChange={(event) => setAttentionAcknowledged(event.currentTarget.checked)}
            />
          </Group>
          {canEditDevices && (
            <Group>
              <Button
                color="red"
                variant="light"
                leftSection={<IconTrash size={18} />}
                onClick={deleteConfirm.open}
              >
                Delete device
              </Button>
            </Group>
          )}
        </Stack>
      ) : (
        <Stack gap="xl">
          <SimpleGrid cols={{ base: 1, md: 2 }} spacing="xl">
            <section className="device-detail-section">
              <Title order={4}>Identity</Title>
              <SimpleGrid cols={{ base: 1, sm: 2 }} mt="md">
                <DeviceField label="Vendor" value={device.vendor || '-'} />
                <DeviceField label="Hostname" value={device.hostname || '-'} />
                <DeviceField label="MAC address" value={device.mac || '-'} />
              </SimpleGrid>
              <IdentityConfidenceField device={device} />
            </section>
            <section className="device-detail-section">
              <Title order={4}>Network</Title>
              <SimpleGrid cols={{ base: 1, sm: 2 }} mt="md">
                <DeviceField label="IP address" value={device.ip || '-'} />
                <DeviceField
                  label="Last port scan"
                  value={formatDate(device.last_port_scan, timeZone)}
                />
                <DeviceField label="Missed scans" value={String(device.missed_scans ?? 0)} />
                <DeviceField label="Status source" value={device.status_source_display || '-'} />
              </SimpleGrid>
              <Text size="xs" c="dimmed" mt="md">Open ports</Text>
              <Group gap={6} mt={6}>
                {(device.open_ports || []).length ? (
                  device.open_ports.map((port) => (
                    <PortGuidanceBadge key={`${port.protocol}-${port.port}`} port={port} />
                  ))
                ) : <Text size="sm">-</Text>}
              </Group>
            </section>
          </SimpleGrid>

          <DeviceInterfacesSection
            canEditDevices={canEditDevices}
            device={device}
            onSeparate={onSeparateInterface}
            timeZone={timeZone}
          />

          <DeviceSnmpInventory device={device} timeZone={timeZone} />

          <Divider />
          <SimpleGrid cols={{ base: 1, md: 2 }} spacing="xl">
            <section className="device-detail-section">
              <Title order={4}>Profile</Title>
              <SimpleGrid cols={{ base: 1, sm: 2 }} mt="md">
                <DeviceField label="Room" value={device.room || 'Unassigned'} />
                <DeviceField label="Role" value={formatRoleLabel(device.role)} />
                <DeviceField
                  label="Online notifications"
                  value={formatDeviceNotificationPreference(
                    device.online_notification_preference
                  )}
                />
                <DeviceField
                  label="Offline notifications"
                  value={formatDeviceNotificationPreference(
                    device.offline_notification_preference
                  )}
                />
                <DeviceField
                  label="Presence expectation"
                  value={formatDevicePresenceExpectation(device.presence_expectation)}
                />
                <DeviceField
                  label="Absence attention"
                  value={formatOfflineAttention(device)}
                />
                <DeviceField label="First seen" value={formatDate(device.firstseen, timeZone)} />
                <DeviceField label="Last seen" value={formatDate(device.lastseen, timeZone)} />
              </SimpleGrid>
            </section>
            <section className="device-detail-section">
              <Title order={4}>Notes and access</Title>
              <Text size="sm" mt="md" className="wrap-text">
                {device.comments || 'No notes added.'}
              </Text>
              {detectingWebUrl && (
                <Group gap="xs" mt="md">
                  <Loader size="xs" />
                  <Text size="sm" c="dimmed">Checking web interface...</Text>
                </Group>
              )}
              {activeUrl && validExternalUrl(activeUrl) && (
                <Button
                  component="a"
                  href={activeUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  variant="light"
                  mt="md"
                  leftSection={<IconArrowUpRight size={17} />}
                >
                  Open device interface
                </Button>
              )}
            </section>
          </SimpleGrid>
          {currentStatus?.reason && <Alert color="gray">{currentStatus.reason}</Alert>}
        </Stack>
      )}
    </Tabs.Panel>
  );
}
