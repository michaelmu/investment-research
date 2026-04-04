#!/usr/bin/env bash
set -euo pipefail

ASOF=${1:-"$(date -I)"}
MODE=${2:-"close"}

cd "$(dirname "$0")/../.."  # repo root

PY="./.venv/bin/python"
if [[ ! -x "$PY" ]]; then
  PY="python3"
fi

export PYTHONPATH="$(pwd)/scripts/paper"

"$PY" ./scripts/paper/bot_daily.py --asof "$ASOF" --mode "$MODE"
