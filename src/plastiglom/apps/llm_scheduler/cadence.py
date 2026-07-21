"""Cadence rules for the LLM scheduler.

Each rule is a pure function `next_due(now) -> datetime` that returns the
earliest scheduled fire time strictly after `now` had no prior runs occurred
(i.e. the canonical clock-tick for that rule). The runner combines this with
each job's persisted `last_run_at` to decide whether a fire is owed: a job is
due if the most recent canonical tick at-or-before `now` is after
`last_run_at` (or `last_run_at` is unset).

Times are emitted in the supplied tzinfo so that day-of-week / day-of-month
arithmetic happens in the user's local zone, matching how DESIGN.md §7.6
describes the cadences ("last day of the month").
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import datetime, time, timedelta, tzinfo
from typing import Protocol


class Cadence(Protocol):
    """A schedule rule.

    `previous_tick(now)` returns the most recent scheduled fire time <= now.
    `next_tick(now)` returns the next scheduled fire time > now.
    `describe()` returns a human-readable summary used by `status` output.
    """

    def previous_tick(self, now: datetime) -> datetime: ...
    def next_tick(self, now: datetime) -> datetime: ...
    def describe(self) -> str: ...


def _localize(dt: datetime, tz: tzinfo) -> datetime:
    return dt.astimezone(tz) if dt.tzinfo is not None else dt.replace(tzinfo=tz)


@dataclass(frozen=True)
class Weekly:
    """Fires once a week at `at` local time on `weekday` (0=Mon, 6=Sun)."""

    weekday: int
    at: time
    tz: tzinfo

    def __post_init__(self) -> None:
        if not 0 <= self.weekday <= 6:
            raise ValueError(f"weekday must be 0..6, got {self.weekday}")

    def previous_tick(self, now: datetime) -> datetime:
        local = _localize(now, self.tz)
        days_back = (local.weekday() - self.weekday) % 7
        candidate = datetime.combine(local.date(), self.at, tzinfo=self.tz) - timedelta(
            days=days_back
        )
        if candidate > local:
            candidate -= timedelta(days=7)
        return candidate

    def next_tick(self, now: datetime) -> datetime:
        prev = self.previous_tick(now)
        return prev + timedelta(days=7)

    def describe(self) -> str:
        name = calendar.day_name[self.weekday]
        return f"weekly on {name} at {self.at.strftime('%H:%M')}"


@dataclass(frozen=True)
class MonthlyDay:
    """Fires once a month at `at` local time on calendar `day`.

    `day` may exceed a given month's length; in that case the rule clamps to
    the month's last day (so day=31 == last-day-of-month for short months).
    Pass `day=-1` for an unambiguous "last day of the month".
    """

    day: int
    at: time
    tz: tzinfo

    def __post_init__(self) -> None:
        if self.day == 0 or self.day < -1 or self.day > 31:
            raise ValueError(f"day must be -1 or 1..31, got {self.day}")

    def _resolve(self, year: int, month: int) -> datetime:
        last = calendar.monthrange(year, month)[1]
        d = last if self.day == -1 else min(self.day, last)
        return datetime(year, month, d, self.at.hour, self.at.minute, tzinfo=self.tz)

    def previous_tick(self, now: datetime) -> datetime:
        local = _localize(now, self.tz)
        candidate = self._resolve(local.year, local.month)
        if candidate > local:
            year, month = local.year, local.month - 1
            if month == 0:
                year, month = year - 1, 12
            candidate = self._resolve(year, month)
        return candidate

    def next_tick(self, now: datetime) -> datetime:
        local = _localize(now, self.tz)
        candidate = self._resolve(local.year, local.month)
        if candidate <= local:
            year, month = local.year, local.month + 1
            if month == 13:
                year, month = year + 1, 1
            candidate = self._resolve(year, month)
        return candidate

    def describe(self) -> str:
        when = "last day of month" if self.day == -1 else f"day {self.day}"
        return f"monthly on {when} at {self.at.strftime('%H:%M')}"
