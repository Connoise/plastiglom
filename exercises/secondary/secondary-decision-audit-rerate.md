---
id: secondary-decision-audit-rerate
title: Decision audit — rerate
category: secondary
parent_id: main-decision-audit
version: 1
status: active
schedule:
  window: contextual
  weight_factors:
    recent_relevance: 0.7
    depth_potential: 0.7
    weekday_weight: 0.6
    weekend_weight: 0.6
    novelty_value: 0.4
prompts:
  - "Re-reading the decision you flagged: is your read of it still the same now, or has confidence shifted in either direction?"
tags: [decisions, calibration, temporal-self]
created_at: 2026-05-07T00:00:00Z
created_by: seed
updated_at: 2026-05-07T00:00:00Z
updated_by: seed
---

Seed secondary exercise. Probes time-variance on a single named decision —
the kind of within-day re-read §7.1 calls out as valuable signal.
