#!/usr/bin/env bash
set -euo pipefail
SKILL_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
mkdir -p "$SKILL_ROOT/.state"
if [[ -f "$SKILL_ROOT/.state/watcher.pid" ]] && kill -0 "$(cat "$SKILL_ROOT/.state/watcher.pid")" 2>/dev/null; then
  echo "WAKE watcher already running."
  exit 0
fi
nohup python3 "$SKILL_ROOT/watcher/wake_watcher.py" run >> "$SKILL_ROOT/.state/nohup.log" 2>&1 &
echo "WAKE watcher start requested (PID $!)."
