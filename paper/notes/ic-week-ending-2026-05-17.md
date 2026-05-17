---
layout: page
title: Paper bot IC review (week ending 2026-05-17)
permalink: /paper/ic/2026-05-17/
---

## Paper bot — weekly IC review (week ending 2026-05-17)

**Not financial advice.**

### Scoreboard
- 1w: portfolio 0.53% vs SPY 0.21%
- 4w: portfolio 3.62% vs SPY 4.09%
- End NAV: 105,306.00
- Pending: exec_date=2026-05-18 orders=1

### Process audit (answer honestly)
- Rules followed this week: **yes**, based on the current weekly close execution framework.
- Data/execution weirdness: **minor** — there is still **1 pending order** queued for `2026-05-18`, so execution continuity should be checked after Monday's run.
- Were changes made too quickly? **No.** No live rule changes were made this week.

### Mistakes (process, not outcome)
- We still don't have a completed write-up on whether recent pending-order behavior is ordinary scheduling lag or a recurring execution issue. That's a process gap: operational anomalies should be classified quickly so they don't get hand-waved as noise.

### Improvements
- Candidate hypothesis to test next week: the existing **winner sizing** idea remains the best candidate, but it should stay in experiment mode until tested. **Hypothesis:** modestly increasing effective sizing in the highest-score names can improve 4-week relative return vs SPY without worsening max drawdown by more than 1 percentage point. **Evaluation date:** 2026-06-07.
- One change (max 1) OR explicitly 'no change': **No change.** Default policy applies this week; there is not yet enough evidence to justify modifying live rules.

### Next week’s focus
- Verify whether the pending 2026-05-18 order executes cleanly.
- Review whether the 4-week lag vs SPY is caused by sizing, selection, or simple short-sample noise.
- Keep the live rules stable while the sizing hypothesis is evaluated.
