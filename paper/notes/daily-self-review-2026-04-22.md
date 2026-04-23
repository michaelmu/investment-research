---
layout: page
title: Daily self review (2026-04-22)
permalink: /paper/daily-review/2026-04-22/
---

## Paper bot — daily self review (2026-04-22)

**Not financial advice.**

### Quick scoreboard
- Portfolio return since inception: 1.7201073129564204
- Relative return vs benchmark: -8.529625282495367
- Last ~5 trading days return: 0.47577491643953085
- Turnover (% avg NAV): 65.01178629981568
- Closed trades / hit rate: 2 / 100.0

### Execution quality
- Fills in last 14 days: 10
- exact: 4
- latest_available: 0
- stale_fallback: 6
- unknown: 0

### Proposed next improvement
- Title: Reduce stale-fill risk in execution path
- Hypothesis: If stale fills remain a meaningful share of trades, execution quality will distort the learning loop and hurt returns.
- Change: Tighten execution to require provider freshness on trading days or defer fills instead of using stale fallback when lag exceeds threshold.
- Metric: stale_fallback share of fills < 10% over rolling 2 weeks
- Risk: More deferred orders / lower responsiveness.
- Severity / confidence: 9 / 8
- Auto-executable: True

### Daily decision
- Executed: False
- Reason: already at desired setting
- Changes: none

### Daily discipline
- Daily self-review may auto-execute only high-severity, high-confidence operational fixes. Strategy preference changes still defer to the weekly IC loop.
