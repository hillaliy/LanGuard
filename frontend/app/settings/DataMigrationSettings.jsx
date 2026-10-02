import { Box, Button, Divider, FileButton, Group, Image, Stack, Tabs, Text, Title } from '@mantine/core';
import { IconDevices, IconDownload, IconUpload } from '@tabler/icons-react';

export default function DataMigrationSettings({ controller }) {
  const {
    exportInventory,
    exporting,
    importInventoryFile,
    importNetAlertXFile,
    importWatchYourLanFile,
    importing,
    importingNetAlertX,
    importingWatchYourLan,
  } = controller;

  return (
<Tabs.Panel value="data" className="settings-category-panel">
        <Stack gap="xl">
          <Box>
            <Title order={3}>Data & migration</Title>
            <Text c="dimmed">Move device inventory into or out of LanGuard.</Text>
          </Box>
        <Group justify="space-between" align="flex-start" wrap="wrap">
          <Box>
            <Group gap="xs">
              <IconDevices size={24} aria-hidden="true" />
              <Text fw={700}>Device inventory</Text>
            </Group>
            <Text size="sm" c="dimmed">
              Export or import known devices, names, icons, vendors, IPs, and open ports.
            </Text>
          </Box>
          <Group gap="sm">
            <Button
              variant="default"
              leftSection={<IconDownload size={18} />}
              onClick={exportInventory}
              loading={exporting}
            >
              Export
            </Button>
            <FileButton onChange={importInventoryFile} accept="application/json,.json">
              {(props) => (
                <Button
                  {...props}
                  variant="light"
                  leftSection={<IconUpload size={18} />}
                  loading={importing}
                >
                  Import
                </Button>
              )}
            </FileButton>
          </Group>
        </Group>

        <Divider />

        <Group justify="space-between" align="flex-start" wrap="wrap">
          <Box>
            <Group gap="xs">
              <Image
                src="/integrations/netalertx.svg"
                alt=""
                aria-hidden="true"
                w={24}
                h={24}
                fit="contain"
              />
              <Text fw={700}>NetAlertX migration</Text>
            </Group>
            <Text size="sm" c="dimmed">
              Import devices from the <code>devices.csv</code> export created by NetAlertX.
            </Text>
          </Box>
          <FileButton onChange={importNetAlertXFile} accept="text/csv,.csv">
            {(props) => (
              <Button
                {...props}
                variant="light"
                leftSection={<IconUpload size={18} />}
                loading={importingNetAlertX}
              >
                Import from NetAlertX
              </Button>
            )}
          </FileButton>
        </Group>

        <Divider />

        <Group className="watchyourlan-migration-row" justify="space-between" align="flex-start" wrap="wrap">
          <Box className="watchyourlan-migration-description">
            <Group gap="xs">
              <Image
                src="/integrations/watchyourlan.png"
                alt=""
                aria-hidden="true"
                w={24}
                h={24}
                fit="contain"
              />
              <Text fw={700}>WatchYourLAN migration</Text>
            </Group>
            <Text size="sm" c="dimmed">
              Import devices from the JSON returned by the WatchYourLAN <code>/api/all</code> endpoint.
            </Text>
          </Box>
          <FileButton onChange={importWatchYourLanFile} accept="application/json,.json">
            {(props) => (
              <Button
                {...props}
                variant="light"
                leftSection={<IconUpload size={18} />}
                loading={importingWatchYourLan}
              >
                Import from WatchYourLAN
              </Button>
            )}
          </FileButton>
        </Group>
        </Stack>
          </Tabs.Panel>
  );
}
