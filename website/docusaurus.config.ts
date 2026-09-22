import {themes as prismThemes} from 'prism-react-renderer';
import type {Config} from '@docusaurus/types';
import type * as Preset from '@docusaurus/preset-classic';

const docusaurusNavbarItem = {
  type: 'html',
  value: [
    '<a class="navbar-docusaurus-link" href="https://docusaurus.io"',
    ' target="_blank" rel="noopener noreferrer"',
    ' aria-label="Docusaurus website" title="Docusaurus">',
    '<img src="/LanGuard/img/docusaurus.svg" alt="" width="24" height="24" />',
    '</a>',
  ].join(''),
  position: 'right',
  className: 'navbar-docusaurus-item',
} as const;

const config: Config = {
  title: 'LanGuard Documentation',
  tagline: 'Discover, understand, and protect the devices on your network.',
  favicon: 'img/logo.png',
  future: {v4: true},
  url: 'https://hillaliy.github.io',
  baseUrl: '/LanGuard/',
  organizationName: 'hillaliy',
  projectName: 'LanGuard',
  trailingSlash: false,
  onBrokenLinks: 'throw',
  markdown: {
    hooks: {
      onBrokenMarkdownLinks: 'throw',
      onBrokenMarkdownImages: 'throw',
    },
  },
  i18n: {defaultLocale: 'en', locales: ['en']},
  presets: [
    [
      'classic',
      {
        docs: {
          sidebarPath: './sidebars.ts',
          routeBasePath: 'docs',
          editUrl: 'https://github.com/hillaliy/LanGuard/edit/main/website/',
          showLastUpdateAuthor: true,
          showLastUpdateTime: true,
        },
        blog: false,
        theme: {customCss: './src/css/custom.css'},
      } satisfies Preset.Options,
    ],
  ],
  themes: process.env.DOCUSAURUS_LOCAL_SEARCH === 'false' ? [] : [
    [
      require.resolve('@easyops-cn/docusaurus-search-local'),
      {
        hashed: true,
        indexDocs: true,
        indexPages: true,
        indexBlog: false,
        docsRouteBasePath: '/docs',
        language: ['en'],
        highlightSearchTermsOnTargetPage: true,
        searchBarShortcutHint: true,
      },
    ],
  ],
  themeConfig: {
    image: 'img/demo-preview.png',
    metadata: [
      {
        name: 'keywords',
        content: 'LanGuard, network discovery, device inventory, network monitoring, Docker, macOS',
      },
    ],
    colorMode: {defaultMode: 'light', respectPrefersColorScheme: true},
    navbar: {
      title: 'LanGuard',
      hideOnScroll: true,
      logo: {alt: 'LanGuard shield logo', src: 'img/logo.svg'},
      items: [
        {type: 'docSidebar', sidebarId: 'docsSidebar', position: 'left', label: 'Documentation'},
        {to: '/docs/installation', label: 'Installation', position: 'left'},
        {to: '/docs/integrations', label: 'Integrations', position: 'left'},
        {to: '/docs/release-notes', label: 'Release notes', position: 'left'},
        {href: 'https://github.com/hillaliy/LanGuard', label: 'GitHub', position: 'right'},
        ...(process.env.NODE_ENV === 'production' ? [docusaurusNavbarItem] : []),
      ],
    },
    footer: {
      style: 'dark',
      links: [
        {
          title: 'Start here',
          items: [
            {label: 'Getting started', to: '/docs/getting-started'},
            {label: 'Installation', to: '/docs/installation'},
            {label: 'Configuration', to: '/docs/configuration'},
          ],
        },
        {
          title: 'Operate',
          items: [
            {label: 'Device discovery', to: '/docs/device-discovery'},
            {label: 'Integrations', to: '/docs/integrations'},
            {label: 'Troubleshooting', to: '/docs/troubleshooting'},
          ],
        },
        {
          title: 'Project',
          items: [
            {label: 'GitHub repository', href: 'https://github.com/hillaliy/LanGuard'},
            {label: 'Report an issue', href: 'https://github.com/hillaliy/LanGuard/issues/new/choose'},
            {label: 'Release notes', to: '/docs/release-notes'},
          ],
        },
      ],
      copyright: `Copyright © ${new Date().getFullYear()} LanGuard contributors. Licensed under Apache-2.0.`,
    },
    prism: {
      theme: prismThemes.github,
      darkTheme: prismThemes.dracula,
      additionalLanguages: ['bash', 'json'],
    },
  } satisfies Preset.ThemeConfig,
};

export default config;
