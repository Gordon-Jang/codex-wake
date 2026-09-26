#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
TARGET_ROOT="$HOME/.codex/skills"
TARGET="$TARGET_ROOT/wake"

mkdir -p "$TARGET_ROOT"
if [[ "$REPO_ROOT" != "$TARGET" ]]; then
  rm -rf "$TARGET"
  mkdir -p "$TARGET"
  cp "$REPO_ROOT/SKILL.md" "$REPO_ROOT/VERSION" "$TARGET/"
  for f in README.md README.zh-CN.md CHANGELOG.md; do
    [[ -f "$REPO_ROOT/$f" ]] && cp "$REPO_ROOT/$f" "$TARGET/"
  done
  cp -R "$REPO_ROOT/agents" "$REPO_ROOT/watcher" "$REPO_ROOT/docs" "$REPO_ROOT/scripts" "$TARGET/"
fi
mkdir -p "$HOME/.codex/wake"
echo "WAKE v0.5.0 installed: $TARGET"
echo "Durable jobs: $HOME/.codex/wake"
echo "Run: python3 '$TARGET/watcher/wake_watcher.py' doctor"
