import { Badge, Box, Button, Group, Image, NumberInput, PasswordInput, SimpleGrid, Stack, Switch, Tabs, Text, TextInput, Title } from '@mantine/core';
import { IconRefresh, IconSend, IconServer, IconWorldSearch } from '@tabler/icons-react';
import DockerIntegrationSettings from './DockerIntegrationSettings';
import { formatDate } from '../utils/date';

export default function IntegrationSettings({ controller }) {
  const {
    adguardConfigured,
    adguardEnabled,
    adguardLastError,
    adguardLastSyncAt,
    adguardPassword,
    adguardRetentionDays,
    adguardSyncInterval,
    adguardUrl,
    adguardUsername,
    homeboxConfigured,
    homeboxEnabled,
    homeboxToken,
    homeboxUrl,
    integrationCategory,
    onSaved,
    piholeConfigured,
    piholeEnabled,
    piholeLastError,
    piholeLastSyncAt,
    piholePassword,
    piholeRetentionDays,
    piholeSyncInterval,
    piholeUrl,
    setAdguardEnabled,
    setAdguardPassword,
    setAdguardRetentionDays,
    setAdguardSyncInterval,
    setAdguardUrl,
    setAdguardUsername,
    setHomeboxEnabled,
    setHomeboxToken,
    setHomeboxUrl,
    setIntegrationCategory,
    setPiholeEnabled,
    setPiholePassword,
    setPiholeRetentionDays,
    setPiholeSyncInterval,
    setPiholeUrl,
    setSpeedtestTrackerApiToken,
    setSpeedtestTrackerEnabled,
    setSpeedtestTrackerUrl,
    speedtestTrackerApiToken,
    speedtestTrackerConfigured,
    speedtestTrackerEnabled,
    speedtestTrackerUrl,
    syncAdguardNow,
    syncPiholeNow,
    syncingAdguard,
    syncingPihole,
    testAdguardConnection,
    testHomeboxConnection,
    testPiholeConnection,
    testSpeedtestTrackerConnection,
    testingAdguard,
    testingHomebox,
    testingPihole,
    testingSpeedtestTracker,
    timeZone,
  } = controller;

  return (
<Tabs.Panel value="integrations" className="settings-category-panel">
        <Stack gap="xl">
          <Group justify="space-between" align="flex-start">
            <Box>
              <Title order={3}>Integrations</Title>
              <Text c="dimmed">Connect external services that extend LanGuard network visibility.</Text>
            </Box>
            <Badge variant="light">5 available</Badge>
          </Group>
        <Tabs
          value={integrationCategory}
          onChange={(value) => setIntegrationCategory(value || 'network-services')}
          variant="pills"
          keepMounted={false}
        >
          <Tabs.List>
            <Tabs.Tab value="network-services" leftSection={<IconWorldSearch size={17} />}>
              Network services
            </Tabs.Tab>
            <Tabs.Tab value="infrastructure" leftSection={<IconServer size={17} />}>
              Infrastructure
            </Tabs.Tab>
          </Tabs.List>
          <Tabs.Panel value="network-services" pt="lg">
            <Stack gap="xl">
              <Text size="sm" c="dimmed">
                Connect services that add DNS, performance, and inventory context to LanGuard.
              </Text>
        <Stack className="settings-subsection" gap="sm">
          <Group justify="space-between" align="flex-start">
            <Box>
              <Group gap="sm">
                <Image
                  src="/integrations/adguard-home.svg"
                  alt=""
                  aria-hidden="true"
                  w={24}
                  h={24}
                  fit="contain"
                />
                <Text fw={700}>AdGuard Home</Text>
                <Switch
                  label="Enabled"
                  checked={adguardEnabled}
                  onChange={(event) => {
                    const enabled = event.currentTarget.checked;
                    setAdguardEnabled(enabled);
                    if (enabled) setPiholeEnabled(false);
                  }}
                />
              </Group>
              <Text size="sm" c="dimmed" mt={4}>
                Sync aggregated DNS destinations to device pages. LanGuard stores domain counters, not raw DNS responses.
              </Text>
            </Box>
            <Badge color={adguardConfigured && adguardEnabled ? 'teal' : 'gray'} variant="light">
              {adguardConfigured ? 'Configured' : 'Not configured'}
            </Badge>
          </Group>

          <SimpleGrid className="adguard-connection-fields" cols={{ base: 1, md: 3 }}>
            <TextInput
              label="AdGuard Home URL"
              placeholder="http://192.168.1.2:3000"
              value={adguardUrl}
              onChange={(event) => setAdguardUrl(event.currentTarget.value)}
              disabled={!adguardEnabled}
            />
            <TextInput
              label="Username"
              placeholder="admin"
              value={adguardUsername}
              onChange={(event) => setAdguardUsername(event.currentTarget.value)}
              disabled={!adguardEnabled}
            />
            <PasswordInput
              label="Password"
              placeholder={adguardConfigured ? 'Saved password' : 'Password'}
              value={adguardPassword}
              onChange={(event) => setAdguardPassword(event.currentTarget.value)}
              disabled={!adguardEnabled}
            />
          </SimpleGrid>
          {adguardConfigured && (
            <Text size="xs" c="dimmed">Leave the password blank to keep the saved password.</Text>
          )}

          <Group className="adguard-sync-controls" justify="space-between" align="flex-end" wrap="wrap">
            <Group className="adguard-sync-fields" align="flex-end" wrap="wrap">
              <NumberInput
                w={170}
                label="Sync interval"
                value={adguardSyncInterval}
                onChange={(value) => setAdguardSyncInterval(Number(value) || 5)}
                min={1}
                max={1440}
                suffix=" min"
                disabled={!adguardEnabled}
              />
              <NumberInput
                w={170}
                label="Activity retention"
                value={adguardRetentionDays}
                onChange={(value) => setAdguardRetentionDays(Number(value) || 90)}
                min={1}
                max={3650}
                suffix=" days"
                disabled={!adguardEnabled}
              />
              <Box className="adguard-sync-status" pb={6}>
                <Text size="xs" c="dimmed">
                  {adguardLastSyncAt
                    ? `Last sync: ${formatDate(adguardLastSyncAt, timeZone)}`
                    : 'Not synced yet'}
                </Text>
                {adguardLastError && (
                  <Text size="xs" c="red" maw={420} className="wrap-text">
                    Last error: {adguardLastError}
                  </Text>
                )}
              </Box>
            </Group>
            <Group className="adguard-sync-actions" gap="sm">
              <Button
                variant="default"
                leftSection={<IconSend size={18} />}
                onClick={testAdguardConnection}
                loading={testingAdguard}
                disabled={!adguardEnabled || !adguardUrl.trim() || syncingAdguard}
              >
                Test connection
              </Button>
              <Button
                variant="light"
                leftSection={<IconRefresh size={18} />}
                onClick={syncAdguardNow}
                loading={syncingAdguard}
                disabled={!adguardEnabled || !adguardConfigured || testingAdguard}
              >
                Sync now
              </Button>
            </Group>
          </Group>
        </Stack>
        <Stack className="settings-subsection" gap="sm">
          <Group justify="space-between" align="flex-start">
            <Box>
              <Group gap="sm">
                <Image
                  src="/integrations/pi-hole.svg"
                  alt=""
                  aria-hidden="true"
                  w={24}
                  h={24}
                  fit="contain"
                />
                <Text fw={700}>Pi-hole</Text>
                <Switch
                  label="Enabled"
                  checked={piholeEnabled}
                  onChange={(event) => {
                    const enabled = event.currentTarget.checked;
                    setPiholeEnabled(enabled);
                    if (enabled) setAdguardEnabled(false);
                  }}
                />
              </Group>
              <Text size="sm" c="dimmed" mt={4}>
                Sync aggregated DNS activity and discover clients from Pi-hole v6 DHCP leases.
                Only one DNS provider can be active at a time.
              </Text>
            </Box>
            <Badge color={piholeConfigured && piholeEnabled ? 'teal' : 'gray'} variant="light">
              {piholeConfigured ? 'Configured' : 'Not configured'}
            </Badge>
          </Group>

          <SimpleGrid cols={{ base: 1, md: 2 }}>
            <TextInput
              label="Pi-hole URL"
              placeholder="http://192.168.1.2"
              value={piholeUrl}
              onChange={(event) => setPiholeUrl(event.currentTarget.value)}
              disabled={!piholeEnabled}
            />
            <PasswordInput
              label="Application password"
              placeholder={piholeConfigured ? 'Saved application password' : 'Application password'}
              value={piholePassword}
              onChange={(event) => setPiholePassword(event.currentTarget.value)}
              disabled={!piholeEnabled}
            />
          </SimpleGrid>
          {piholeConfigured && (
            <Text size="xs" c="dimmed">
              Leave the application password blank to keep the saved password.
            </Text>
          )}

          <Group justify="space-between" align="flex-end" wrap="wrap">
            <Group align="flex-end" wrap="wrap">
              <NumberInput
                w={170}
                label="Sync interval"
                value={piholeSyncInterval}
                onChange={(value) => setPiholeSyncInterval(Number(value) || 5)}
                min={1}
                max={1440}
                suffix=" min"
                disabled={!piholeEnabled}
              />
              <NumberInput
                w={170}
                label="Activity retention"
                value={piholeRetentionDays}
                onChange={(value) => setPiholeRetentionDays(Number(value) || 90)}
                min={1}
                max={3650}
                suffix=" days"
                disabled={!piholeEnabled}
              />
              <Box pb={6}>
                <Text size="xs" c="dimmed">
                  {piholeLastSyncAt
                    ? `Last sync: ${formatDate(piholeLastSyncAt, timeZone)}`
                    : 'Not synced yet'}
                </Text>
                {piholeLastError && (
                  <Text size="xs" c="red" maw={420} className="wrap-text">
                    Last error: {piholeLastError}
                  </Text>
                )}
              </Box>
            </Group>
            <Group gap="sm">
              <Button
                variant="default"
                leftSection={<IconSend size={18} />}
                onClick={testPiholeConnection}
                loading={testingPihole}
                disabled={!piholeEnabled || !piholeUrl.trim() || syncingPihole}
              >
                Test connection
              </Button>
              <Button
                variant="light"
                leftSection={<IconRefresh size={18} />}
                onClick={syncPiholeNow}
                loading={syncingPihole}
                disabled={!piholeEnabled || !piholeConfigured || testingPihole}
              >
                Sync now
              </Button>
            </Group>
          </Group>
        </Stack>
        <Stack className="settings-subsection" gap="sm">
          <Group justify="space-between" align="flex-start">
            <Box>
              <Group gap="sm">
                <Image
                  src="/integrations/speedtest-tracker.svg"
                  alt=""
                  aria-hidden="true"
                  w={24}
                  h={24}
                  fit="contain"
                />
                <Text fw={700}>Speedtest Tracker</Text>
                <Switch
                  label="Enabled"
                  checked={speedtestTrackerEnabled}
                  onChange={(event) => setSpeedtestTrackerEnabled(event.currentTarget.checked)}
                />
              </Group>
              <Text size="sm" c="dimmed" mt={4}>
                Show the latest internet performance result on the dashboard.
              </Text>
            </Box>
            <Badge color={speedtestTrackerConfigured && speedtestTrackerEnabled ? 'teal' : 'gray'} variant="light">
              {speedtestTrackerConfigured ? 'Configured' : 'Not configured'}
            </Badge>
          </Group>
          <Stack className="speedtest-connection-controls" gap="sm">
          <SimpleGrid className="speedtest-connection-fields" cols={{ base: 1, md: 2 }}>
            <TextInput
              label="Speedtest Tracker URL"
              placeholder="http://192.168.1.2:8080"
              value={speedtestTrackerUrl}
              onChange={(event) => setSpeedtestTrackerUrl(event.currentTarget.value)}
              disabled={!speedtestTrackerEnabled}
            />
            <PasswordInput
              label="API token"
              placeholder={speedtestTrackerConfigured ? 'Saved API token' : 'API token'}
              value={speedtestTrackerApiToken}
              onChange={(event) => setSpeedtestTrackerApiToken(event.currentTarget.value)}
              disabled={!speedtestTrackerEnabled}
            />
          </SimpleGrid>
          {speedtestTrackerConfigured && (
            <Text className="speedtest-connection-hint" size="xs" c="dimmed">Leave the API token blank to keep the saved token.</Text>
          )}
          <Group className="speedtest-connection-actions" justify="flex-end">
            <Button
              variant="default"
              leftSection={<IconSend size={18} />}
              onClick={testSpeedtestTrackerConnection}
              loading={testingSpeedtestTracker}
              disabled={!speedtestTrackerEnabled || !speedtestTrackerUrl.trim()}
            >
              Test connection
            </Button>
          </Group>
          </Stack>
        </Stack>
        <Stack className="settings-subsection" gap="sm">
          <Group justify="space-between">
            <Group>
              <Image
                src="/integrations/homebox.svg"
                alt=""
                aria-hidden="true"
                w={24}
                h={24}
                fit="contain"
              />
              <Text fw={700}>HomeBox</Text>
              <Switch
                label="Enabled"
                checked={homeboxEnabled}
                onChange={(event) => setHomeboxEnabled(event.currentTarget.checked)}
              />
            </Group>
            <Badge color={homeboxConfigured && homeboxEnabled ? 'teal' : 'gray'} variant="light">
              {homeboxConfigured ? 'Configured' : 'Not configured'}
            </Badge>
          </Group>
          <SimpleGrid cols={{ base: 1, md: 2 }}>
            <TextInput label="HomeBox URL" value={homeboxUrl} disabled={!homeboxEnabled}
              onChange={(event) => setHomeboxUrl(event.currentTarget.value)} />
            <PasswordInput label="API key" value={homeboxToken} disabled={!homeboxEnabled}
              placeholder={homeboxConfigured ? 'Saved API key' : 'API key'}
              onChange={(event) => setHomeboxToken(event.currentTarget.value)} />
          </SimpleGrid>
          <Group justify="flex-end">
            <Button variant="default" leftSection={<IconSend size={18} />}
              disabled={!homeboxEnabled || !homeboxUrl.trim()} loading={testingHomebox}
              onClick={testHomeboxConnection}>Test connection</Button>
          </Group>
        </Stack>
        </Stack>
          </Tabs.Panel>
          <Tabs.Panel value="infrastructure" pt="lg">
            <Stack gap="xl">
              <Text size="sm" c="dimmed">
                Add runtime context from the infrastructure that hosts LanGuard.
              </Text>
              <DockerIntegrationSettings
                timeZone={timeZone}
                onChanged={onSaved}
              />
            </Stack>
          </Tabs.Panel>
        </Tabs>
        </Stack>
          </Tabs.Panel>
  );
}
