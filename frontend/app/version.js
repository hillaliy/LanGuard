export const APP_VERSION = process.env.NEXT_PUBLIC_APP_VERSION || 'development';

function changelogEntries() {
  try {
    return JSON.parse(process.env.NEXT_PUBLIC_CHANGELOG_JSON || '[]');
  } catch {
    return [];
  }
}

export const CHANGELOG_ENTRIES = changelogEntries();
