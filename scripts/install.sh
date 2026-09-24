#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
TARGET_ROOT="$HOME/.codex/skills"
TARGET="$TARGET_ROOT/wake"

mkdir -p "$TARGET_ROOT"

REPO_FULL="$(cd -- "$REPO_ROOT" && pwd)"
TARGET_FULL="$(cd -- "$(dirname -- "$TARGET")" && pwd)/$(basename -- "$TARGET")"

if [[ "$REPO_FULL" == "$TARGET_FULL" ]]; then
  echo "WAKE is already located at the target path: $TARGET"
  echo "No copy is needed."
else
  SAVED_STATE=""
  if [[ -d "$TARGET/.state" ]]; then
    TMPROOT="$(mktemp -d)"
    SAVED_STATE="$TMPROOT/state"
    cp -R "$TARGET/.state" "$SAVED_STATE"
  fi

  rm -rf "$TARGET"
  mkdir -p "$TARGET"
  cp "$REPO_ROOT/SKILL.md" "$REPO_ROOT/VERSION" "$TARGET/"
  cp -R "$REPO_ROOT/agents" "$REPO_ROOT/watcher" "$REPO_ROOT/docs" "$REPO_ROOT/scripts" "$TARGET/"

  if [[ -n "$SAVED_STATE" && -d "$SAVED_STATE" ]]; then
    cp -R "$SAVED_STATE" "$TARGET/.state"
  fi

  echo "WAKE v0.3.2 installed: $TARGET"
fi

echo "Run: python3 '$TARGET/watcher/wake_watcher.py' doctor"
echo "Watcher is not auto-started."
