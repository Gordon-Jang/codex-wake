#!/usr/bin/env bash
set -euo pipefail
PIDFILE="$HOME/.codex/wake/watcher.pid"
if [[ -f "$PIDFILE" ]]; then
  PID="$(cat "$PIDFILE")"
  kill "$PID" 2>/dev/null || true
  rm -f "$PIDFILE"
  echo "Stopped WAKE watcher PID $PID."
else
  echo "WAKE watcher is not running."
fi
