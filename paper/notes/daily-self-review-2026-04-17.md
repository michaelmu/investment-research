---
layout: page
title: Daily self review (2026-04-17)
permalink: /paper/daily-review/2026-04-17/
---

## Paper bot — daily self review (2026-04-17)

**Not financial advice.**

### Quick scoreboard
- Portfolio return since inception: 1.1450215147894127
- Relative return vs benchmark: -7.624297494961163
- Last ~5 trading days return: 0.832710263760772
- Turnover (% avg NAV): 47.86901695127659
- Closed trades / hit rate: 2 / 100.0

### Execution quality
- Fills in last 14 days: 10
- exact: 0
- latest_available: 0
- stale_fallback: 6
- unknown: 4

### Proposed next improvement
- Title: Reduce stale-fill risk in execution path
- Hypothesis: If stale fills remain a meaningful share of trades, execution quality will distort the learning loop and hurt returns.
- Change: Tighten execution to require provider freshness on trading days or defer fills instead of using stale fallback when lag exceeds threshold.
- Metric: stale_fallback share of fills < 10% over rolling 2 weeks
- Risk: More deferred orders / lower responsiveness.

### Daily discipline
- Do not auto-change rules here. Queue evidence and escalate through weekly IC unless urgent bug/data issue.
