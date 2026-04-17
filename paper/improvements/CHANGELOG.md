# Paper bot change log

Rule changes are intentional, slow, and attributable.

## Principles
- **At most one rule change per week** (unless fixing a bug)
- Every change must include: hypothesis, expected upside, key risk, and evaluation date
- Changes are committed in git with a clear message

---

## Entries

- **2026-04-17 (data layer refactor)** — Add provider abstraction and set default market data provider to **Yahoo** with **Stooq** fallback.
  - Hypothesis: separating the data layer from execution logic will reduce breakage, make source quality explicit, and let us plug in a paid provider cleanly.
  - Change: introduce `marketData.provider` / `marketData.fallbackProvider` in rules, plus shared `scripts/paper/market_data.py`.
  - Metric: fewer data-related execution failures and cleaner provider swaps (e.g. Tiingo/Polygon) without changing trading logic.
  - Risk: Yahoo remains unofficial; this improves architecture more than data quality itself.
  - Evaluation date: **2026-05-01**.

- **2026-03-31 (rules v2)** — Switch execution from **next_open** → **close**.
  - Hypothesis: Stooq's daily bar timing makes same-day open unreliable; using close will eliminate stuck pending orders and make execution deterministic.
  - Change: `execution.tradePrice` = `close`.
  - Metric: % of pending orders executed on scheduled day; target **>=95%** within 1 trading day. Also: reduce WARNs about missing prices to near-zero.
  - Risk: different fill assumption vs next-open; may slightly bias results vs real-world if trading at open would differ.
  - Evaluation date: **2026-04-14** (two weeks).
