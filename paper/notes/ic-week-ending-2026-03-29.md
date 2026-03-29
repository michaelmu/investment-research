---
layout: page
title: Paper bot IC review (week ending 2026-03-29)
permalink: /paper/ic/2026-03-29/
---

## Paper bot — weekly IC review (week ending 2026-03-29)

**Not financial advice.**

Insufficient NAV history to compute weekly return endpoints for this week ending.

### Process audit
- Rules followed: **mostly** (nothing obvious violated), but **can’t fully audit** without clean daily NAV history and explicit execution logs.
- Data/execution weirdness:
  - `paper/nav.csv` has **duplicate rows** for 2026-03-26 and 2026-03-27 (suggests NAV append is not de-duping by date).
  - Weekly perf vs SPY can’t be computed yet: **insufficient endpoints** for a full 1w window.
  - Pending rebalance orders exist with exec_date=2026-03-30 (see `paper/orders_pending.json`).
- Improvements to queue for next week:
  1) **Bugfix**: de-dupe NAV writes by `date` (enforce one row per trading day).
  2) Add a small check that fails CI/run if NAV contains duplicate dates (or auto-compacts to last row per day).
  3) Compute “1w” using *last 5 trading days available* when calendar endpoints are missing (explicitly label it).
