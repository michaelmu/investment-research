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

# Lightweight daily self-review after the main run. This should surface one
# concrete improvement candidate without changing rules automatically.
if [[ "$MODE" == "close" ]]; then
  "$PY" ./scripts/paper/performance.py >/dev/null 2>&1 || true
  "$PY" ./scripts/paper/analytics.py >/dev/null 2>&1 || true
  "$PY" ./scripts/paper/daily_self_review.py --asof "$ASOF" >/dev/null 2>&1 || true
fi
