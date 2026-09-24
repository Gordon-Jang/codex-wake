#!/usr/bin/env bash
set -euo pipefail
SKILL_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
PIDFILE="$SKILL_ROOT/.state/watcher.pid"
if [[ -f "$PIDFILE" ]]; then
  PID="$(cat "$PIDFILE")"
  kill "$PID" 2>/dev/null || true
  rm -f "$PIDFILE"
  echo "Stopped WAKE watcher PID $PID."
else
  echo "WAKE watcher is not running."
fi
