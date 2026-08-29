#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPOSITORY_DIR="$(cd "$ROOT_DIR/../.." && pwd)"
APP_NAME="${APP_NAME:-LanGuard}"
APP_DIR="$ROOT_DIR/.build/app/$APP_NAME.app"
RELEASE_DIR="$ROOT_DIR/.build/release"
STAGING_DIR="$ROOT_DIR/.build/dmg-staging"
VERSION="$(tr -d '[:space:]' < "$REPOSITORY_DIR/VERSION")"
DMG_PATH="$RELEASE_DIR/$APP_NAME-$VERSION.dmg"
VOLUME_NAME="$APP_NAME $VERSION"

"$SCRIPT_DIR/build_app.sh"

rm -rf "$STAGING_DIR"
mkdir -p "$STAGING_DIR" "$RELEASE_DIR"

cp -R "$APP_DIR" "$STAGING_DIR/"
ln -s /Applications "$STAGING_DIR/Applications"

rm -f "$DMG_PATH"
hdiutil create \
  -volname "$VOLUME_NAME" \
  -srcfolder "$STAGING_DIR" \
  -ov \
  -format UDZO \
  "$DMG_PATH"

echo "Built $DMG_PATH"
