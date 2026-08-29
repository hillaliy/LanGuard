import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

import {
  frontendChangelogEntries,
  parseChangelog,
  releaseNotesForVersion,
  stripInlineMarkdown,
  validateChangelog,
} from './changelog.mjs';

const sample = `# Changelog

## Unreleased

- Added a pending feature.

## 2.0.0 - 2026-08-29

- Added **important** support for \`devices\`.
  Continued on another line.
- See [documentation](https://example.test/docs).
`;

test('parseChangelog reads releases and multiline items', () => {
  assert.deepEqual(parseChangelog(sample), [
    {
      version: 'Unreleased',
      date: '',
      items: ['Added a pending feature.'],
    },
    {
      version: '2.0.0',
      date: '2026-08-29',
      items: [
        'Added **important** support for `devices`. Continued on another line.',
        'See [documentation](https://example.test/docs).',
      ],
    },
  ]);
});

test('frontend entries exclude Unreleased and strip inline markdown', () => {
  assert.deepEqual(frontendChangelogEntries(sample), [
    {
      version: '2.0.0',
      date: '2026-08-29',
      items: [
        'Added important support for devices. Continued on another line.',
        'See documentation.',
      ],
    },
  ]);
  assert.equal(stripInlineMarkdown('Use **bold** and `code`.'), 'Use bold and code.');
});

test('release notes come from the requested changelog section', () => {
  assert.equal(
    releaseNotesForVersion(sample, 'v2.0.0'),
    '- Added **important** support for `devices`. Continued on another line.\n' +
      '- See [documentation](https://example.test/docs).'
  );
});

test('repository changelog contains the current VERSION', () => {
  const changelog = readFileSync(new URL('../CHANGELOG.md', import.meta.url), 'utf8');
  const version = readFileSync(new URL('../VERSION', import.meta.url), 'utf8');
  assert.doesNotThrow(() => validateChangelog(changelog, version));
});
