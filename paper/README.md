# Paper trading

This folder contains the public, auditable paper-trading system.

## Files
- `rules.json` — current strategy + risk rules
- `ledger.csv` — append-only event ledger (trades, dividends, splits, fees)
- `positions.csv` — latest position snapshot (generated)
- `nav.csv` — daily NAV vs benchmark (generated)
- `cash.csv` — daily cash balance (generated)
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

All output is **not financial advice**.
