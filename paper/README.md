# Paper trading

This folder contains the public, auditable paper-trading system.

## Files
- `rules.json` — current strategy + risk rules
- `ledger.csv` — append-only event ledger (trades, dividends, splits, fees)
- `positions.csv` — latest position snapshot (generated)
- `nav.csv` — raw daily NAV vs benchmark log (generated)
- `nav_clean.csv` — de-duplicated NAV series used for reporting
- `cash.csv` — daily cash balance (generated)
- `position_pnl.csv` — realized/unrealized P&L by position
- `performance_summary.json` — summarized performance metrics
- `analytics_summary.json` — turnover / trade stats / sleeve summary
- `sleeve_pnl.csv` — sleeve-level traded notional and realized P&L
- `exposure_history.csv` — rough sleeve exposure snapshots over time
- `notes/` — weekly review memos
- `tiingo_api_key.txt` — optional local API key file for Tiingo (gitignored)

## Market data providers
Configured in `rules.json` under `marketData`.

Current supported providers:
- `yahoo`
- `stooq`
- `tiingo`

Tiingo auth lookup order:
1. `TIINGO_API_KEY` environment variable
2. `paper/tiingo_api_key.txt`

## Workflow
1) Record events (append-only):
   - `./scripts/paper/ledger.py add-trade ...`
2) Mark portfolio (recompute positions + NAV):
   - `./scripts/paper/mark.py --date YYYY-MM-DD`
3) Weekly review:
   - `./scripts/paper/weekly.py --week-ending YYYY-MM-DD`
4) Provider health check:
   - `./scripts/paper/provider_health.py --asof YYYY-MM-DD`
5) Performance cleanup / P&L:
   - `./scripts/paper/performance.py`
6) Portfolio analytics:
   - `./scripts/paper/analytics.py`

All output is **not financial advice**.
