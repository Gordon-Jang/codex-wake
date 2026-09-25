#!/usr/bin/env bash
set -euo pipefail
TARGET="$HOME/.codex/skills/wake"
if [[ -x "$TARGET/scripts/stop-watcher.sh" ]]; then
  "$TARGET/scripts/stop-watcher.sh" || true
fi
rm -rf "$TARGET"
echo "WAKE removed: $TARGET"
echo "Durable jobs preserved: $HOME/.codex/wake"
