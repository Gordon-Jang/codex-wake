#!/usr/bin/env bash
set -euo pipefail
SKILL_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
python3 "$SKILL_ROOT/watcher/wake_watcher.py" status
