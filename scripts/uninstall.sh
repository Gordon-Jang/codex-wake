#!/usr/bin/env bash
set -euo pipefail

TARGET="$HOME/.agents/skills/wake"

if [[ -d "$TARGET" ]]; then
  rm -rf "$TARGET"
  echo "WAKE removed from:"
  echo "  $TARGET"
else
  echo "WAKE is not installed at:"
  echo "  $TARGET"
fi

echo "Restart Codex if the skill still appears in the skill picker."
