#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
TARGET_ROOT="$HOME/.agents/skills"
TARGET="$TARGET_ROOT/wake"

if [[ ! -f "$REPO_ROOT/SKILL.md" ]]; then
  echo "SKILL.md not found at $REPO_ROOT" >&2
  exit 1
fi

mkdir -p "$TARGET_ROOT"
rm -rf "$TARGET"
mkdir -p "$TARGET"
cp "$REPO_ROOT/SKILL.md" "$TARGET/SKILL.md"
if [[ -d "$REPO_ROOT/agents" ]]; then
  cp -R "$REPO_ROOT/agents" "$TARGET/agents"
fi

echo
echo "WAKE installed successfully:"
echo "  $TARGET"
echo
echo "Try it in Codex:"
echo '  $wake'
echo
echo "Codex should detect skill changes automatically; restart it if WAKE does not appear."
