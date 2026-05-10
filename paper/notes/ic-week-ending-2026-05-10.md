---
layout: page
title: Paper bot IC review (week ending 2026-05-10)
permalink: /paper/ic/2026-05-10/
---

## Paper bot — weekly IC review (week ending 2026-05-10)

**Not financial advice.**

### Scoreboard
- 1w: portfolio 1.43% vs SPY 2.35%
- 4w: portfolio 4.02% vs SPY 8.56%
- End NAV: 104,749.87
- Pending: exec_date=2026-05-11 orders=3

### Process audit (answer honestly)
- Did we follow the rules? **Yes** — no discretionary overrides or off-cycle rule edits were made.
- Any data/execution weirdness? **No material execution issue this week**; current pending orders are the normal Monday rebalance queue for 2026-05-11.
- Were changes made too quickly? **No** — weekly discipline held, and no strategy rule was changed without a pre-registered test.

### Mistakes (process, not outcome)
- We still do **not** have a pre-registered sizing experiment with a locked evaluation date, which makes it too easy to rationalize a rule tweak after weak relative performance. That is a process miss.

### Improvements
- Candidate hypothesis to test next week: increasing effective winner sizing modestly (for example via larger starter size or faster scaling into top-score names) could improve relative performance without materially worsening drawdown.
- One change (max 1) OR explicitly 'no change': **No change**. The hypothesis is reasonable, but this week it does not yet clear the bar for a rules edit because the metric and evaluation date were not already attached to a concrete rule change proposal.

### Next week’s focus
- Pre-register one sizing experiment with a specific metric and evaluation date.
- Watch whether Monday's three queued rebalance orders execute cleanly.
- Keep turnover in view; underperformance versus SPY is still large enough that impatience would be dangerous.
