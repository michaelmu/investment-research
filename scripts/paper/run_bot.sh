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

# Health-check market data before trading. In fills mode, keep going even if
# data is stale; in close mode, warn but do not hard-stop the bot.
if ! "$PY" ./scripts/paper/provider_health.py --asof "$ASOF"; then
  echo "ALERT: provider health check failed for $ASOF; continuing bot run for visibility." >&2
fi

"$PY" ./scripts/paper/bot_daily.py --asof "$ASOF" --mode "$MODE"
