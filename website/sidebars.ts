import type {SidebarsConfig} from '@docusaurus/plugin-content-docs';

const sidebars: SidebarsConfig = {
  docsSidebar: [
    {
      type: 'category',
      label: 'Start here',
      collapsible: false,
      items: ['getting-started', 'installation', 'configuration'],
    },
    {
      type: 'category',
      label: 'Understand LanGuard',
      collapsible: false,
      items: ['device-discovery', 'devices-and-alerts', 'scheduler-tasks'],
    },
    {
      type: 'category',
      label: 'Connect',
      collapsible: false,
      items: ['integrations', 'notifications'],
    },
    {
      type: 'category',
      label: 'Operate',
      collapsible: false,
      items: ['backup-and-migration', 'troubleshooting'],
    },
    {
      type: 'category',
      label: 'Other editions and updates',
      collapsible: false,
      items: ['macos-scanner', 'release-notes'],
    },
  ],
};

export default sidebars;
