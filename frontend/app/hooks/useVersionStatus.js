import { useEffect, useState } from 'react';
import { apiRequest } from '../api';
import { APP_VERSION } from '../version';
import { isNewerVersion } from '../utils/version';

const changelogSeenStorageKey = 'languard_changelog_seen_version';
const versionCheckFallbackInterval = 6 * 60 * 60 * 1000;

export function useVersionStatus() {
  const [changelogOpened, setChangelogOpened] = useState(false);
  const [seenChangelogVersion, setSeenChangelogVersion] = useState(APP_VERSION);
  const [latestVersion, setLatestVersion] = useState(APP_VERSION);
  const [versionCheckInterval, setVersionCheckInterval] = useState(
    versionCheckFallbackInterval
  );

  useEffect(() => {
    const storedVersion = window.localStorage.getItem(changelogSeenStorageKey) || '';
    setSeenChangelogVersion(storedVersion);
    if (storedVersion !== APP_VERSION) {
      setChangelogOpened(true);
    }
  }, []);

  useEffect(() => {
    async function checkVersion() {
      try {
        const payload = await apiRequest('version/');
        const versionData = payload.data || {};
        if (versionData.latest_version) {
          setLatestVersion(versionData.latest_version);
        }
        if (versionData.check_interval_seconds) {
          setVersionCheckInterval(versionData.check_interval_seconds * 1000);
        }
      } catch {
        setLatestVersion(APP_VERSION);
      }
    }

    checkVersion();
    const timer = window.setInterval(checkVersion, versionCheckInterval);
    return () => window.clearInterval(timer);
  }, [versionCheckInterval]);

  const hasUnreadChangelog = seenChangelogVersion !== APP_VERSION;
  const hasVersionUpdate = isNewerVersion(latestVersion, APP_VERSION);
  const hasVersionIndicator = hasUnreadChangelog || hasVersionUpdate;
  const versionTooltip = hasVersionUpdate
    ? `New version v${latestVersion} is available`
    : 'Version history';

  function closeChangelog() {
    window.localStorage.setItem(changelogSeenStorageKey, APP_VERSION);
    setSeenChangelogVersion(APP_VERSION);
    setChangelogOpened(false);
  }

  return {
    changelogOpened,
    setChangelogOpened,
    closeChangelog,
    latestVersion,
    hasVersionUpdate,
    hasVersionIndicator,
    versionTooltip,
  };
}
