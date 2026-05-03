---
layout: page
title: Paper bot IC review (week ending 2026-05-03)
permalink: /paper/ic/2026-05-03/
---

## Paper bot — weekly IC review (week ending 2026-05-03)

**Not financial advice.**

### Scoreboard
- 1w: portfolio 0.73% vs SPY 0.94%
- 4w: portfolio 2.87% vs SPY 10.81%
- End NAV: 103,275.50
- Pending: exec_date=2026-05-04 orders=1

### Process audit (answer honestly)
- **Did we follow the rules?** Mostly yes. The weekly process ran and the portfolio remained within the current sleeve structure and trade assumptions.
- **Any data/execution weirdness?** Yes: recent execution quality is still noisy. The latest daily review shows **6 stale-fallback fills out of 10 fills in the last 14 days**, and there is **1 pending order** queued for 2026-05-04.
- **Were changes made too quickly?** No. This week we should avoid rule churn and keep the learning loop clean.

### Mistakes (process, not outcome)
- We are still letting stale-fallback execution dominate too many recent fills, which weakens confidence in what performance is telling us.

### Improvements
- **Candidate hypothesis to test next week:** If we require fresher provider data on trading days and defer fills when lag exceeds threshold, the stale-fallback share of fills should drop below **10%** over the next two weeks without causing a meaningful rise in stuck orders.
- **One change (max 1) OR explicitly 'no change':** **No change.** Hypothesis is promising, but this week the evidence does not yet justify a rules change under the written-policy bar. Track the metric first, then evaluate with a dated experiment.

### Next week’s focus
- Measure stale-fallback share of fills and pending-order frequency together.
- Confirm whether the execution-quality issue is operational/data-layer noise rather than a strategy-selection problem.
- Reassess at next IC review with a concrete metric readout and explicit evaluation date before touching rules.
