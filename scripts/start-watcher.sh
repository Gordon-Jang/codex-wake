#!/usr/bin/env bash
set -euo pipefail
SKILL_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
WAKE_HOME="$HOME/.codex/wake"
PIDFILE="$WAKE_HOME/watcher.pid"
mkdir -p "$WAKE_HOME"
if [[ -f "$PIDFILE" ]] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
  echo "WAKE watcher already running (PID $(cat "$PIDFILE"))."
  exit 0
fi
nohup python3 "$SKILL_ROOT/watcher/wake_watcher.py" run >> "$WAKE_HOME/nohup.log" 2>&1 &
echo "WAKE watcher start requested (PID $!)."
