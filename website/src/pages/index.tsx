import type {ReactNode} from 'react';
import Link from '@docusaurus/Link';
import useBaseUrl from '@docusaurus/useBaseUrl';
import Layout from '@theme/Layout';
import Heading from '@theme/Heading';

import styles from './index.module.css';

const paths = [
  {
    number: '01',
    title: 'Install LanGuard',
    description: 'Deploy the Docker stack, understand host networking, and complete the first sign-in.',
    link: '/docs/installation',
    label: 'Open installation guide',
  },
  {
    number: '02',
    title: 'Discover your network',
    description: 'Choose scan methods, define network ranges, and learn how LanGuard identifies devices.',
    link: '/docs/device-discovery',
    label: 'Explore device discovery',
  },
  {
    number: '03',
    title: 'Act on changes',
    description: 'Configure attention rules, notifications, quiet hours, and delivery channels.',
    link: '/docs/devices-and-alerts',
    label: 'Review devices and alerts',
  },
];

const capabilities = [
  ['Inventory', 'Identify devices, vendors, addresses, ports, rooms, roles, and status.'],
  ['History', 'Review availability timelines, scan comparisons, events, and IP changes.'],
  ['Integrations', 'Connect AdGuard Home, HomeBox, Speedtest Tracker, and automation tools.'],
  ['Control', 'Archive devices, trigger Wake-on-LAN, run detailed port scans, and manage access.'],
];

function HomeHeader() {
  const dashboardImage = useBaseUrl('/img/demo-preview.png');

  return (
    <header className={styles.hero}>
      <div className={styles.heroInner}>
        <div className={styles.heroCopy}>
          <span className={styles.eyebrow}>Official documentation</span>
          <Heading as="h1">LanGuard Documentation</Heading>
          <p>
            Everything you need to deploy LanGuard, understand what it finds,
            and keep a clear inventory of the devices on your network.
          </p>
          <div className={styles.heroActions}>
            <Link className="button button--primary button--lg" to="/docs/getting-started">
              Get started
            </Link>
            <Link className="button button--outline button--lg" to="/docs/installation">
              Install LanGuard
            </Link>
          </div>
          <div className={styles.platforms} aria-label="Supported deployments">
            <span>Docker web app</span>
            <span>Native macOS scanner</span>
          </div>
        </div>
        <div className={styles.heroVisual}>
          <img
            src={dashboardImage}
            alt="LanGuard dashboard showing network status, scan results, and devices"
          />
        </div>
      </div>
    </header>
  );
}

export default function Home(): ReactNode {
  return (
    <Layout
      title="Network discovery and device inventory"
      description="Official documentation for deploying and operating LanGuard network discovery and device inventory.">
      <HomeHeader />
      <main>
        <section className={styles.quickStart}>
          <div className={styles.sectionHeading}>
            <span>Choose a path</span>
            <Heading as="h2">Start with the task in front of you</Heading>
          </div>
          <div className={styles.pathGrid}>
            {paths.map((path) => (
              <article className={styles.pathCard} key={path.number}>
                <span className={styles.pathNumber}>{path.number}</span>
                <Heading as="h3">{path.title}</Heading>
                <p>{path.description}</p>
                <Link to={path.link}>{path.label} <span aria-hidden="true">→</span></Link>
              </article>
            ))}
          </div>
        </section>

        <section className={styles.capabilityBand}>
          <div className={styles.capabilityInner}>
            <div className={styles.sectionHeading}>
              <span>From first scan to daily operation</span>
              <Heading as="h2">Know what is connected and what changed</Heading>
              <p>
                LanGuard keeps discovery, inventory, attention findings, and
                integrations in one focused interface for home and small-business networks.
              </p>
            </div>
            <div className={styles.capabilityGrid}>
              {capabilities.map(([title, description]) => (
                <div className={styles.capability} key={title}>
                  <Heading as="h3">{title}</Heading>
                  <p>{description}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className={styles.helpBand}>
          <div>
            <span>Need a precise answer?</span>
            <Heading as="h2">Search the docs or diagnose a problem</Heading>
            <p>The documentation search runs locally and covers every guide on this site.</p>
          </div>
          <div className={styles.helpActions}>
            <Link className="button button--primary button--lg" to="/docs/troubleshooting">
              Troubleshooting
            </Link>
            <Link className="button button--outline button--lg" to="/docs/release-notes">
              Release notes
            </Link>
          </div>
        </section>
      </main>
    </Layout>
  );
}
