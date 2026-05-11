"""Submission streak + per-exercise coverage report.

Reads `entries/` and rolls up: daily submission rate, current/longest
streak, per-exercise fired / submitted / null / open counts, fire-vs-submit
ratio. Pure analysis — no LLM, no writes. Shared by the CLI and the web
app's `/stats` page.
"""

from plastiglom.apps.stats_report.stats import (
    ExerciseCoverage,
    StatsReport,
    StreakInfo,
    build_report,
    collect_entries,
    compute_streaks,
)

__all__ = [
    "ExerciseCoverage",
    "StatsReport",
    "StreakInfo",
    "build_report",
    "collect_entries",
    "compute_streaks",
]
