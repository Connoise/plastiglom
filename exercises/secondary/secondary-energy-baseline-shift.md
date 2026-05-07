---
id: secondary-energy-baseline-shift
title: Energy baseline — shift
category: secondary
parent_id: main-energy-baseline
version: 1
status: active
schedule:
  window: contextual
  weight_factors:
    recent_relevance: 0.6
    depth_potential: 0.4
    weekday_weight: 0.6
    weekend_weight: 0.7
    novelty_value: 0.3
prompts:
  - "How has your energy changed since this morning, and what specifically moved it — food, people, work, screens, sleep debt, something else?"
tags: [energy, mood, attribution]
created_at: 2026-05-07T00:00:00Z
created_by: seed
updated_at: 2026-05-07T00:00:00Z
updated_by: seed
---

Seed secondary exercise. Builds attribution between baseline and current
state without forcing a clean cause.
