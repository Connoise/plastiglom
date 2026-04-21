---
id: main-values-drift
title: Values drift check
category: main
parent_id: null
version: 1
status: active
schedule:
  window: evening
  weight_factors:
    recent_relevance: 0.8
    depth_potential: 0.7
    weekday_weight: 0.5
    weekend_weight: 0.9
    novelty_value: 0.6
prompts:
  - "What did you want a year ago that you no longer want?"
  - "What does that shift reveal, if anything?"
tags: [values, identity, temporal-self]
created_at: 2026-01-01T00:00:00Z
created_by: seed
updated_at: 2026-01-01T00:00:00Z
updated_by: seed
---

Seed exercise. Probes change in what the user cares about over longer spans.
