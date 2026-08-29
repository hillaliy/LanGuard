# Contributing to LanGuard

Thank you for helping improve LanGuard. Keep changes focused, follow the existing
project patterns, and include tests appropriate to the behavior being changed.

## Development

Create and start the backend environment:

```bash
python3.14 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python backend/manage.py migrate
python backend/manage.py runserver 127.0.0.1:8000
```

Start the frontend in another terminal:

```bash
cd frontend
npm ci
npm run dev
```

Open `http://127.0.0.1:3000`.

For native macOS development and packaging, see
[`macos/LanGuardMac/README.md`](macos/LanGuardMac/README.md).

## Checks

Run the relevant checks before opening a pull request:

```bash
.venv/bin/python backend/manage.py test core
node --test scripts/changelog.test.mjs
node scripts/changelog.mjs --check
cd frontend && npm run lint && npm run build
```

Run the macOS tests when changing the native app:

```bash
cd macos/LanGuardMac
swift test
```

## Release Metadata

[`VERSION`](VERSION) is the single source for the Docker, frontend, and macOS
version number. [`CHANGELOG.md`](CHANGELOG.md) is the single source for the
frontend **What's new** catalog and GitHub release notes.

Validate both files and generate release notes for the current version with:

```bash
node scripts/changelog.mjs --check
node scripts/changelog.mjs --version "$(cat VERSION)" > /tmp/languard-release-notes.md
```

Move completed entries from `Unreleased` into a dated version section before
publishing a release. Do not edit `frontend/app/version.js` with release entries;
the frontend build generates them from `CHANGELOG.md`.
