import {readFile, writeFile} from 'node:fs/promises';
import {dirname, resolve} from 'node:path';
import {fileURLToPath} from 'node:url';

const scriptDirectory = dirname(fileURLToPath(import.meta.url));
const websiteDirectory = resolve(scriptDirectory, '..');
const changelogPath = resolve(websiteDirectory, '..', 'CHANGELOG.md');
const outputPath = resolve(websiteDirectory, 'docs', 'release-notes.md');

const changelog = await readFile(changelogPath, 'utf8');
const body = changelog.replace(/^# Changelog\s*/, '');
const frontmatter = `---
title: Release Notes
description: Changes delivered in each LanGuard release.
slug: /release-notes
---

# Release Notes

This page is generated from the repository's canonical \`CHANGELOG.md\` during documentation builds.

`;

await writeFile(outputPath, `${frontmatter}${body}`, 'utf8');
