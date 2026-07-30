#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIGURATION="${CONFIGURATION:-debug}"
APP_NAME="${APP_NAME:-LanGuard}"
PRODUCT_NAME="LanGuardMac"
APP_DIR="$ROOT_DIR/.build/app/$APP_NAME.app"
CONTENTS_DIR="$APP_DIR/Contents"
MACOS_DIR="$CONTENTS_DIR/MacOS"
RESOURCES_DIR="$CONTENTS_DIR/Resources"
BUNDLE_IDENTIFIER="$(/usr/libexec/PlistBuddy -c "Print :CFBundleIdentifier" "$ROOT_DIR/Packaging/Info.plist")"

cd "$ROOT_DIR"

swift build --configuration "$CONFIGURATION"

rm -rf "$APP_DIR"
mkdir -p "$MACOS_DIR" "$RESOURCES_DIR"

cp "$ROOT_DIR/Packaging/Info.plist" "$CONTENTS_DIR/Info.plist"
cp "$ROOT_DIR/.build/$CONFIGURATION/$PRODUCT_NAME" "$MACOS_DIR/$PRODUCT_NAME"

if [ -d "$ROOT_DIR/Resources" ]; then
  rsync -a --exclude ".gitkeep" "$ROOT_DIR/Resources/" "$RESOURCES_DIR/"
fi

chmod +x "$MACOS_DIR/$PRODUCT_NAME"

/usr/bin/codesign --force --deep --sign - --identifier "$BUNDLE_IDENTIFIER" "$APP_DIR"

echo "Built $APP_DIR"
