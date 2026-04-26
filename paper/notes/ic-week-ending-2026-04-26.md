---
layout: page
title: Paper bot IC review (week ending 2026-04-26)
permalink: /paper/ic/2026-04-26/
---

## Paper bot — weekly IC review (week ending 2026-04-26)

**Not financial advice.**

### Scoreboard
- 1w: portfolio 0.88% vs SPY 0.54%
- 4w: portfolio 2.29% vs SPY 12.59%
- End NAV: 102,527.33
- Pending: exec_date=2026-04-27 orders=0

### Process audit (answer honestly)
- Followed the current rules this week; no discretionary override detected.
- Execution/data quality still looks noisy: last 14 days show 10 fills, with 6 using `stale_fallback`, which is too high for a clean learning loop.
- No rules were changed too quickly this week.

### Mistakes (process, not outcome)
- We are still tolerating too many stale fallback fills in the execution path, which muddies whether performance is coming from the strategy or from data-quality artifacts.

### Improvements
- Candidate hypothesis to test next week: If we require fresher provider data on trading days (or defer fills when lag exceeds threshold), then stale-fallback fills should drop below 10% of fills over a rolling 2-week window, improving execution fidelity.
- One change (max 1) OR explicitly 'no change': **No change.** Default is no change, and while there is a plausible hypothesis + metric, there is not yet a written evaluation date for the proposed rule change. Keep observing and formalize the experiment before changing rules.

### Next week’s focus
- Add a dated experiment entry for execution freshness if the issue persists.
- Watch whether stale-fallback share improves materially from 6/10 fills.
- Keep strategy rules stable while we separate process quality from market outcome.
