import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const repositoryRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const defaultChangelogPath = resolve(repositoryRoot, 'CHANGELOG.md');
const defaultVersionPath = resolve(repositoryRoot, 'VERSION');

export function parseChangelog(markdown) {
  const entries = [];
  let currentEntry = null;
  let currentItemIndex = -1;

  for (const line of markdown.split(/\r?\n/)) {
    const heading = line.match(/^##\s+(.+?)\s*$/);
    if (heading) {
      if (currentEntry) {
        entries.push(currentEntry);
      }

      const label = heading[1];
      if (label === 'Unreleased') {
        currentEntry = { version: 'Unreleased', date: '', items: [] };
      } else {
        const release = label.match(/^(\S+)\s+-\s+(\d{4}-\d{2}-\d{2})$/);
        if (!release) {
          throw new Error(`Invalid changelog heading: ${label}`);
        }
        currentEntry = { version: release[1], date: release[2], items: [] };
      }
      currentItemIndex = -1;
      continue;
    }

    if (!currentEntry) {
      continue;
    }

    const item = line.match(/^-\s+(.+)$/);
    if (item) {
      currentEntry.items.push(item[1].trim());
      currentItemIndex = currentEntry.items.length - 1;
      continue;
    }

    const continuation = line.trim();
    if (continuation && currentItemIndex >= 0) {
      currentEntry.items[currentItemIndex] += ` ${continuation}`;
    }
  }

  if (currentEntry) {
    entries.push(currentEntry);
  }

  return entries;
}

export function stripInlineMarkdown(value) {
  return value
    .replace(/!\[([^\]]*)\]\([^)]*\)/g, '$1')
    .replace(/\[([^\]]+)\]\([^)]*\)/g, '$1')
    .replace(/\*\*([^*]+)\*\*/g, '$1')
    .replace(/__([^_]+)__/g, '$1')
    .replace(/`([^`]+)`/g, '$1');
}

export function frontendChangelogEntries(markdown) {
  return parseChangelog(markdown)
    .filter((entry) => entry.version !== 'Unreleased')
    .map((entry) => ({
      ...entry,
      items: entry.items.map(stripInlineMarkdown),
    }));
}

export function releaseNotesForVersion(markdown, version) {
  const normalizedVersion = version.trim().replace(/^v/i, '');
  const entry = parseChangelog(markdown).find(
    (candidate) => candidate.version === normalizedVersion
  );
  if (!entry) {
    throw new Error(`CHANGELOG.md does not contain version ${normalizedVersion}.`);
  }
  return entry.items.map((item) => `- ${item}`).join('\n');
}

export function validateChangelog(markdown, currentVersion) {
  const entries = parseChangelog(markdown);
  if (entries[0]?.version !== 'Unreleased') {
    throw new Error('CHANGELOG.md must begin with an Unreleased section.');
  }

  const versions = entries
    .filter((entry) => entry.version !== 'Unreleased')
    .map((entry) => entry.version);
  const duplicates = versions.filter((version, index) => versions.indexOf(version) !== index);
  if (duplicates.length) {
    throw new Error(`CHANGELOG.md contains duplicate versions: ${[...new Set(duplicates)].join(', ')}`);
  }

  const normalizedVersion = currentVersion.trim().replace(/^v/i, '');
  if (!versions.includes(normalizedVersion)) {
    throw new Error(`CHANGELOG.md does not contain current VERSION ${normalizedVersion}.`);
  }

  return entries;
}

function printUsage() {
  process.stderr.write(
    'Usage: node scripts/changelog.mjs --check | --json | --version <version>\n'
  );
}

function main() {
  const markdown = readFileSync(defaultChangelogPath, 'utf8');
  const args = process.argv.slice(2);

  if (args[0] === '--check' && args.length === 1) {
    const currentVersion = readFileSync(defaultVersionPath, 'utf8');
    const entries = validateChangelog(markdown, currentVersion);
    process.stdout.write(
      `Changelog valid: ${entries.length - 1} releases, current version ${currentVersion.trim()}.\n`
    );
    return;
  }

  if (args[0] === '--json' && args.length === 1) {
    process.stdout.write(`${JSON.stringify(frontendChangelogEntries(markdown), null, 2)}\n`);
    return;
  }

  if (args[0] === '--version' && args[1] && args.length === 2) {
    process.stdout.write(`${releaseNotesForVersion(markdown, args[1])}\n`);
    return;
  }

  printUsage();
  process.exitCode = 1;
}

const invokedPath = process.argv[1] ? resolve(process.argv[1]) : '';
if (invokedPath === fileURLToPath(import.meta.url)) {
  try {
    main();
  } catch (error) {
    process.stderr.write(`${error.message}\n`);
    process.exitCode = 1;
  }
}
