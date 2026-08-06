#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MANUF_URL="${MANUF_URL:-https://gitlab.com/wireshark/wireshark/-/raw/release-4.0/manuf}"
TARGET="$ROOT_DIR/Resources/manuf"
TMP_FILE="$(mktemp)"

cleanup() {
  rm -f "$TMP_FILE"
}
trap cleanup EXIT

curl -L --fail "$MANUF_URL" -o "$TMP_FILE"

if [ "$(wc -l < "$TMP_FILE")" -lt 10000 ]; then
  echo "Downloaded manuf file looks too small" >&2
  exit 1
fi

mv "$TMP_FILE" "$TARGET"
echo "Updated $TARGET"
