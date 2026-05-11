"""Compute submission streaks and per-exercise coverage from the entry tree.

Definitions:

- **Submission day**: a calendar day in `tz` with at least one entry whose
  status is `SUBMITTED`. Null / opened_unresponded days do not count — they
  indicate a prompt fired but the user did not respond, which is the gap we
  want streaks to surface.
- **Current streak**: number of consecutive submission days ending at the
  most recent day with any firing. We anchor on "any firing today" so a
  reference day with no prompt firings doesn't break the streak. If the
  most recent firing day was not a submission day, the current streak is 0.
- **Longest streak**: longest run of consecutive submission days across all
  history.
- **Per-exercise coverage**: counts of fired / submitted / null / open and
  the submission rate, used to spot exercises the user reliably skips.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, tzinfo
from pathlib import Path

from plastiglom.packages.core.entry import Entry, EntryStatus
from plastiglom.packages.vault.markdown import read_markdown_file
from plastiglom.packages.vault.serializers import parse_entry


def collect_entries(entries_root: Path) -> list[Entry]:
    """Return every parseable entry under `entries_root`. Bad files are skipped."""
    if not entries_root.exists():
        return []
    out: list[Entry] = []
    for md in sorted(entries_root.rglob("*.md")):
        try:
            out.append(parse_entry(read_markdown_file(md)))
        except Exception:
            continue
    return out


@dataclass
class StreakInfo:
    current: int
    longest: int
    last_submission_day: date | None
    last_fire_day: date | None
    submission_days: int
    fire_days: int


def compute_streaks(entries: list[Entry], tz: tzinfo) -> StreakInfo:
    """Streak math in the user's local timezone.

    Submission and fire days are reduced to local-date sets, then we walk
    backwards from the latest fire day to find the current run, and walk
    every gap once to find the longest run.
    """
    submission_days: set[date] = set()
    fire_days: set[date] = set()
    for e in entries:
        d = e.timestamp_fired.astimezone(tz).date()
        fire_days.add(d)
        if e.status is EntryStatus.SUBMITTED:
            submission_days.add(d)

    last_fire = max(fire_days) if fire_days else None
    last_submission = max(submission_days) if submission_days else None

    current = 0
    if last_fire is not None and last_fire in submission_days:
        day = last_fire
        while day in submission_days:
            current += 1
            day = day - timedelta(days=1)

    longest = 0
    run = 0
    if submission_days:
        ordered = sorted(submission_days)
        run = 1
        longest = 1
        for i in range(1, len(ordered)):
            if ordered[i] - ordered[i - 1] == timedelta(days=1):
                run += 1
                longest = max(longest, run)
            else:
                run = 1

    return StreakInfo(
        current=current,
        longest=longest,
        last_submission_day=last_submission,
        last_fire_day=last_fire,
        submission_days=len(submission_days),
        fire_days=len(fire_days),
    )


@dataclass
class ExerciseCoverage:
    exercise_id: str
    fired: int = 0
    submitted: int = 0
    null: int = 0
    opened_unresponded: int = 0

    @property
    def submission_rate(self) -> float:
        return self.submitted / self.fired if self.fired else 0.0

    @property
    def skip_rate(self) -> float:
        return (self.null + self.opened_unresponded) / self.fired if self.fired else 0.0


@dataclass
class StatsReport:
    window_start: date | None
    window_end: date | None
    entry_count: int
    submitted_count: int
    null_count: int
    open_count: int
    submitted_words: int
    streak: StreakInfo
    by_exercise: dict[str, ExerciseCoverage] = field(default_factory=dict)
    by_day: dict[date, dict[str, int]] = field(default_factory=dict)
    """Per-day submitted / null / open counts (local date). Used for heatmaps."""
    top_tags: list[tuple[str, int]] = field(default_factory=list)

    @property
    def submission_rate(self) -> float:
        return self.submitted_count / self.entry_count if self.entry_count else 0.0


def build_report(
    entries: list[Entry],
    *,
    tz: tzinfo,
    window_start: date | None = None,
    window_end: date | None = None,
    top_n_tags: int = 10,
) -> StatsReport:
    """Aggregate `entries` into a `StatsReport`. `window_*` are local-date inclusive bounds."""
    filtered: list[Entry] = []
    for e in entries:
        d = e.timestamp_fired.astimezone(tz).date()
        if window_start is not None and d < window_start:
            continue
        if window_end is not None and d > window_end:
            continue
        filtered.append(e)

    by_exercise: dict[str, ExerciseCoverage] = defaultdict(
        lambda: ExerciseCoverage(exercise_id="")
    )
    by_day: dict[date, dict[str, int]] = defaultdict(
        lambda: {"submitted": 0, "null": 0, "opened_unresponded": 0}
    )
    tag_counter: Counter[str] = Counter()
    submitted = 0
    null = 0
    open_count = 0
    submitted_words = 0

    for e in filtered:
        cov = by_exercise[e.exercise_id]
        cov.exercise_id = e.exercise_id
        cov.fired += 1
        if e.status is EntryStatus.SUBMITTED:
            cov.submitted += 1
            submitted += 1
            submitted_words += len(e.response.split())
        elif e.status is EntryStatus.NULL:
            cov.null += 1
            null += 1
        else:
            cov.opened_unresponded += 1
            open_count += 1
        for t in e.tags:
            tag_counter[t] += 1
        d = e.timestamp_fired.astimezone(tz).date()
        by_day[d][e.status.value] = by_day[d].get(e.status.value, 0) + 1

    streak = compute_streaks(filtered, tz)

    return StatsReport(
        window_start=window_start,
        window_end=window_end,
        entry_count=len(filtered),
        submitted_count=submitted,
        null_count=null,
        open_count=open_count,
        submitted_words=submitted_words,
        streak=streak,
        by_exercise=dict(by_exercise),
        by_day=dict(sorted(by_day.items())),
        top_tags=tag_counter.most_common(top_n_tags),
    )


def parse_window(
    *,
    since_days: int | None,
    since: str | None,
    until: str | None,
    today: date,
) -> tuple[date | None, date | None]:
    """Translate CLI flags into (start, end) inclusive local-date bounds."""
    start = date.fromisoformat(since) if since else None
    end = date.fromisoformat(until) if until else None
    if since_days is not None:
        if end is None:
            end = today
        start = end - timedelta(days=since_days - 1)
    return start, end


def parse_today(value: str | None, tz: tzinfo) -> date:
    if value is None:
        return datetime.now(tz=tz).date()
    return date.fromisoformat(value)
