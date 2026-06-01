"""Settings loader. Reads `.env` if present, falls back to process env."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    def load_dotenv(*_args: object, **_kwargs: object) -> bool:
        return False


def _parse_hhmm(value: str) -> time:
    hh, mm = value.split(":", 1)
    return time(int(hh), int(mm))


@dataclass(frozen=True)
class Settings:
    vault_path: Path
    timezone: ZoneInfo
    morning_fire: time
    evening_fire: time
    # How long before an entry's lock (the next main firing) a follow-up
    # reminder may be sent if the entry is still unanswered.
    reminder_window: timedelta
    telegram_bot_token: str | None
    telegram_chat_id: str | None
    web_base_url: str
    anthropic_api_key: str | None
    model_sonnet: str
    model_opus: str
    thinking_budget_tokens: int
    qmd_bin: str
    # LLM scheduler clock-of-day overrides (local time, see apps/llm_scheduler).
    digest_weekly_at: time
    analyzer_weekly_at: time
    analyzer_monthly_at: time
    meta_blind_spots_at: time

    @property
    def entries_dir(self) -> Path:
        return self.vault_path / "entries"

    @property
    def exercises_dir(self) -> Path:
        return self.vault_path / "exercises"

    @property
    def daily_index_dir(self) -> Path:
        return self.vault_path / "daily_index"

    @property
    def memory_dir(self) -> Path:
        return self.vault_path / "memory"

    @property
    def analysis_dir(self) -> Path:
        return self.vault_path / "analysis"

    @property
    def tags_dir(self) -> Path:
        return self.vault_path / "tags"

    @property
    def hubs_dir(self) -> Path:
        return self.vault_path / "hubs"

    @property
    def logs_dir(self) -> Path:
        return self.vault_path / "logs"


def load_settings(dotenv_path: str | os.PathLike[str] | None = None) -> Settings:
    load_dotenv(dotenv_path=dotenv_path, override=False)

    vault = os.environ.get("PLASTIGLOM_VAULT_PATH")
    if not vault:
        raise RuntimeError("PLASTIGLOM_VAULT_PATH is required")

    return Settings(
        vault_path=Path(vault).expanduser(),
        timezone=ZoneInfo(os.environ.get("PLASTIGLOM_TIMEZONE", "UTC")),
        morning_fire=_parse_hhmm(os.environ.get("PLASTIGLOM_MORNING_FIRE", "07:30")),
        evening_fire=_parse_hhmm(os.environ.get("PLASTIGLOM_EVENING_FIRE", "21:00")),
        reminder_window=timedelta(
            minutes=int(os.environ.get("PLASTIGLOM_REMINDER_WINDOW_MINUTES", "60"))
        ),
        telegram_bot_token=os.environ.get("TELEGRAM_BOT_TOKEN") or None,
        telegram_chat_id=os.environ.get("TELEGRAM_CHAT_ID") or None,
        web_base_url=os.environ.get("PLASTIGLOM_WEB_BASE_URL", "http://plastiglom.local"),
        anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY") or None,
        model_sonnet=os.environ.get("PLASTIGLOM_MODEL_SONNET", "claude-sonnet-4-6"),
        model_opus=os.environ.get("PLASTIGLOM_MODEL_OPUS", "claude-opus-4-8"),
        thinking_budget_tokens=int(os.environ.get("PLASTIGLOM_THINKING_BUDGET_TOKENS", "10000")),
        qmd_bin=os.environ.get("PLASTIGLOM_QMD_BIN", "qmd"),
        digest_weekly_at=_parse_hhmm(os.environ.get("PLASTIGLOM_DIGEST_WEEKLY_AT", "22:00")),
        analyzer_weekly_at=_parse_hhmm(
            os.environ.get("PLASTIGLOM_ANALYZER_WEEKLY_AT", "22:30")
        ),
        analyzer_monthly_at=_parse_hhmm(
            os.environ.get("PLASTIGLOM_ANALYZER_MONTHLY_AT", "23:00")
        ),
        meta_blind_spots_at=_parse_hhmm(
            os.environ.get("PLASTIGLOM_META_BLIND_SPOTS_AT", "04:00")
        ),
    )
