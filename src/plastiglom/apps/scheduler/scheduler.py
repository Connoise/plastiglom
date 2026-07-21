"""Scheduler core. See §7.1 of DESIGN.md.

Responsibilities covered here:
  - Compute the next main-exercise firing time from a given `now`, using
    configured morning and evening clock times in the local timezone.
  - Compute `lock_at` for a just-fired entry = the *next* main firing after
    `fired_at`.
  - Pick which active main exercise fires, weighting by `weight_factors`
    combined with day-of-week context.

Secondary-exercise insertion (up to three per day, context-triggered) is a
Phase 4 concern; we expose a hook but do not wire policy yet.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from plastiglom.packages.core.exercise import (
    Exercise,
    ExerciseCategory,
    ExerciseStatus,
    ScheduleWindow,
)

# How long after a main exercise fires before its secondary may prompt the
# user. Secondaries never go out together with the parent; the delay is the
# within-day time-variance probe (§7.1).
SECONDARY_DELAY = timedelta(hours=4)


@dataclass(frozen=True)
class FiringClock:
    morning: time
    evening: time


def next_main_firing(now: datetime, clock: FiringClock, tz: ZoneInfo) -> datetime:
    """Return the next main firing strictly after `now`.

    Both `clock` times are wall-clock in `tz`; the result is `tz`-aware.
    """
    local_now = now.astimezone(tz)
    today = local_now.date()

    candidates = [
        datetime.combine(today, clock.morning, tzinfo=tz),
        datetime.combine(today, clock.evening, tzinfo=tz),
        datetime.combine(today + timedelta(days=1), clock.morning, tzinfo=tz),
    ]
    for candidate in candidates:
        if candidate > local_now:
            return candidate
    # Fallback (only if wrapping misbehaves): push a full day.
    return datetime.combine(today + timedelta(days=1), clock.morning, tzinfo=tz)


def compute_lock_at(fired_at: datetime, clock: FiringClock, tz: ZoneInfo) -> datetime:
    """`lock_at` equals the firing time of the next main exercise after `fired_at`."""
    return next_main_firing(fired_at, clock, tz)


def weight_for(exercise: Exercise, when: datetime) -> float:
    """Combine `weight_factors` with a day-of-week context multiplier."""
    wf = exercise.schedule.weight_factors
    is_weekend = when.weekday() >= 5
    context = wf.weekend_weight if is_weekend else wf.weekday_weight
    base = (wf.recent_relevance + wf.depth_potential + wf.novelty_value) / 3.0
    return max(0.0, base * context)


@dataclass
class Scheduler:
    clock: FiringClock
    tz: ZoneInfo
    rng: random.Random

    def select_next_main(
        self,
        pool: list[Exercise],
        when: datetime,
        *,
        recent_ids: set[str] | None = None,
    ) -> Exercise:
        """Weighted-random pick over active main exercises.

        `recent_ids` zeroes out exercises that fired recently to avoid
        unintentional repeats. The meta-engine may explicitly request repeats
        (for time-variance probing); that override lives outside this call.
        """
        recent = recent_ids or set()
        window = _window_for(when, self.clock)

        def _window_match(ex: Exercise) -> bool:
            return ex.schedule.window is ScheduleWindow.CONTEXTUAL or ex.schedule.window is window

        active_in_window = [
            ex
            for ex in pool
            if ex.status is ExerciseStatus.ACTIVE
            and ex.category is ExerciseCategory.MAIN
            and _window_match(ex)
        ]
        candidates = [ex for ex in active_in_window if ex.id not in recent]
        if not candidates:
            # Recent-firings filter exhausted the window — relax it but keep
            # the window match so morning exercises don't surface in the
            # evening (and vice-versa). Only collapse the window filter when
            # there are literally no active mains for this window.
            candidates = active_in_window or [
                ex
                for ex in pool
                if ex.status is ExerciseStatus.ACTIVE and ex.category is ExerciseCategory.MAIN
            ]
        if not candidates:
            raise RuntimeError("no active main exercises available")

        weights = [weight_for(ex, when) for ex in candidates]
        if all(w <= 0 for w in weights):
            weights = [1.0] * len(candidates)
        return self.rng.choices(candidates, weights=weights, k=1)[0]

    def select_secondaries(
        self,
        pool: list[Exercise],
        *,
        when: datetime,
        eligible_parent_ids: set[str],
        already_fired_secondary_ids: set[str],
        max_count: int = 3,
    ) -> list[Exercise]:
        """Pick context-triggered secondary exercises for the current moment.

        Per §7.1: at most three secondaries per day, each tied to a parent
        main exercise that fired earlier. The caller computes
        `eligible_parent_ids` — parents that fired at least `SECONDARY_DELAY`
        ago and whose lock hasn't passed — so a secondary never prompts the
        user at the same time as its parent.
        """
        if max_count <= 0:
            return []
        candidates = [
            ex
            for ex in pool
            if ex.status is ExerciseStatus.ACTIVE
            and ex.category is ExerciseCategory.SECONDARY
            and ex.parent_id in eligible_parent_ids
            and ex.id not in already_fired_secondary_ids
        ]
        if not candidates:
            return []
        weights = [weight_for(ex, when) for ex in candidates]
        if all(w <= 0 for w in weights):
            weights = [1.0] * len(candidates)
        # Sample without replacement up to min(max_count, len(candidates)).
        chosen: list[Exercise] = []
        remaining = list(candidates)
        remaining_weights = list(weights)
        while remaining and len(chosen) < max_count:
            pick = self.rng.choices(remaining, weights=remaining_weights, k=1)[0]
            chosen.append(pick)
            idx = remaining.index(pick)
            remaining.pop(idx)
            remaining_weights.pop(idx)
        return chosen


def _window_for(when: datetime, clock: FiringClock) -> ScheduleWindow:
    """Classify a firing time as morning or evening by proximity to the clock."""
    noon = time(12, 0)
    return ScheduleWindow.MORNING if when.time() < noon else ScheduleWindow.EVENING


def fire_dates_for_day(day: date, clock: FiringClock, tz: ZoneInfo) -> tuple[datetime, datetime]:
    """Convenience: the two main firings scheduled on `day`."""
    return (
        datetime.combine(day, clock.morning, tzinfo=tz),
        datetime.combine(day, clock.evening, tzinfo=tz),
    )
