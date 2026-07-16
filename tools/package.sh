#!/bin/bash
# Assemble the Alfred bundle into build/ and zip it into alfred-launchd-monitor.alfredworkflow.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BUILD="$ROOT/build"
OUT="$ROOT/alfred-launchd-monitor.alfredworkflow"

rm -rf "$BUILD" "$OUT"
mkdir -p "$BUILD/bin"

python3 "$ROOT/tools/build_info_plist.py" "$BUILD/info.plist"
plutil -lint "$BUILD/info.plist"

cp "$ROOT/launchd_monitor.py" "$BUILD/launchd_monitor.py"
cp "$ROOT/bin/dispatch.sh" "$BUILD/bin/dispatch.sh"
chmod +x "$BUILD/bin/dispatch.sh"
cp "$ROOT/icon.png" "$BUILD/icon.png"

( cd "$BUILD" && zip -r -X "$OUT" . -x '.*' )
echo "built $OUT"
