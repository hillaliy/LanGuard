import {
  Alert, Box, Button, Group, LoadingOverlay, Paper, Stack, Tabs, Text, Title,
} from '@mantine/core';
import {
  IconAlertCircle, IconBell, IconDownload, IconNetwork, IconSettings, IconTrash,
  IconWorldSearch,
} from '@tabler/icons-react';
import PageIcon from '../components/PageIcon';
import useSettingsController from './useSettingsController';
import ScanningSettings from './ScanningSettings';
import NotificationSettings from './NotificationSettings';
import IntegrationSettings from './IntegrationSettings';
import MaintenanceSettings from './MaintenanceSettings';
import DataMigrationSettings from './DataMigrationSettings';

export default function SettingsView({
  onSaved,
}) {
  const {
    loading,
    error,
    settingsCategory,
    setSettingsCategory,
    scanningSettings,
    notificationSettings,
    integrationSettings,
    maintenanceSettings,
    dataMigrationSettings,
    showSettingsSave,
    saveSettings,
    saving,
    settingsSaveLabel,
  } = useSettingsController({ onSaved });
  return (
    <Paper className="content-panel settings-page" radius="md" p="lg">
      <LoadingOverlay visible={loading} />
      <Stack>
        <Group justify="space-between" align="flex-start">
          <Group gap="sm">
            <PageIcon>
              <IconSettings size={26} />
            </PageIcon>
            <Box>
              <Title order={2}>Settings</Title>
              <Text c="dimmed">Scanner, notifications, and inventory tools</Text>
            </Box>
          </Group>
        </Group>

        {error && (
          <Alert color="red" icon={<IconAlertCircle size={18} />}>
            {error}
          </Alert>
        )}

        <Tabs
          value={settingsCategory}
          onChange={(value) => setSettingsCategory(value || 'scanning')}
          orientation="vertical"
          className="settings-layout"
        >
          <Tabs.List className="settings-category-nav">
            <Tabs.Tab value="scanning" leftSection={<IconNetwork size={18} />}>Scanning</Tabs.Tab>
            <Tabs.Tab value="notifications" leftSection={<IconBell size={18} />}>Notifications</Tabs.Tab>
            <Tabs.Tab value="integrations" leftSection={<IconWorldSearch size={18} />}>Integrations</Tabs.Tab>
            <Tabs.Tab value="data" leftSection={<IconDownload size={18} />}>Data & migration</Tabs.Tab>
            <Tabs.Tab value="maintenance" leftSection={<IconTrash size={18} />}>Maintenance</Tabs.Tab>
          </Tabs.List>

          <ScanningSettings controller={scanningSettings} />

          <NotificationSettings controller={notificationSettings} />

          <IntegrationSettings controller={integrationSettings} />

          <MaintenanceSettings controller={maintenanceSettings} />

          <DataMigrationSettings controller={dataMigrationSettings} />

          </Tabs>

        {showSettingsSave && (
          <Group justify="flex-end" className="settings-page-actions">
            <Button onClick={saveSettings} loading={saving}>
              {settingsSaveLabel}
            </Button>
          </Group>
        )}
      </Stack>
    </Paper>
  );
}
