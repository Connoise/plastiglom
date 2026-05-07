"""Meta-engine CLI: blind-spots and generate subcommands.

Drives the CLI's argument parsing and orchestration with a FakeRouter so we
exercise loader + persistence + reporting without an Anthropic call.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from plastiglom.apps.meta_engine.__main__ import (
    main as meta_main,
)
from plastiglom.apps.meta_engine.proposals import load_active_pool
from plastiglom.apps.meta_engine.queue import list_proposals
from plastiglom.packages.config import Settings
from plastiglom.packages.core.exercise import (
    Exercise,
    ExerciseCategory,
    ExerciseStatus,
    Schedule,
    ScheduleWindow,
    WeightFactors,
)
from plastiglom.packages.llm.types import LLMResponse
from plastiglom.packages.vault.markdown import write_markdown_file
from plastiglom.packages.vault.serializers import exercise_to_document


@dataclass
class FakeRouter:
    text: str

    def invoke(self, _task, _call) -> LLMResponse:
        return LLMResponse(text=self.text, model="fake", input_tokens=0, output_tokens=0)


def _make_exercise(
    *,
    id_: str,
    category: ExerciseCategory,
    parent_id: str | None = None,
    status: ExerciseStatus = ExerciseStatus.ACTIVE,
    version: int = 1,
) -> Exercise:
    when = datetime(2026, 5, 1, tzinfo=UTC)
    return Exercise(
        id=id_,
        title=id_,
        category=category,
        parent_id=parent_id,
        version=version,
        status=status,
        schedule=Schedule(
            window=ScheduleWindow.MORNING
            if category is ExerciseCategory.MAIN
            else ScheduleWindow.CONTEXTUAL,
            weight_factors=WeightFactors(),
        ),
        prompts=["q?"],
        tags=[],
        created_at=when,
        created_by="seed",
        updated_at=when,
        updated_by="seed",
    )


def _seed_exercise_files(exercises_dir: Path, exercises: list[Exercise]) -> None:
    for ex in exercises:
        sub = "main" if ex.category is ExerciseCategory.MAIN else "secondary"
        write_markdown_file(exercises_dir / sub / f"{ex.id}.md", exercise_to_document(ex))


def _settings(vault: Path) -> Settings:
    from datetime import time
    from zoneinfo import ZoneInfo

    return Settings(
        vault_path=vault,
        timezone=ZoneInfo("UTC"),
        morning_fire=time(7, 30),
        evening_fire=time(21, 0),
        telegram_bot_token=None,
        telegram_chat_id=None,
        web_base_url="http://test",
        anthropic_api_key="test-key",
        model_sonnet="claude-sonnet-4-6",
        model_opus="claude-opus-4-7",
        qmd_bin="",
    )


def _create_proposal_json(new_exercise_id: str, parent_pool_member: str) -> str:
    """Build a canned `create` proposal JSON response for FakeRouter."""
    when = datetime(2026, 5, 1, tzinfo=UTC).isoformat()
    return json.dumps(
        {
            "proposals": [
                {
                    "action": "create",
                    "exercise": {
                        "id": new_exercise_id,
                        "title": "Probe gap",
                        "category": "main",
                        "parent_id": None,
                        "version": 1,
                        "status": "active",
                        "schedule": {
                            "window": "morning",
                            "weight_factors": {
                                "recent_relevance": 0.5,
                                "depth_potential": 0.5,
                                "weekday_weight": 0.5,
                                "weekend_weight": 0.5,
                                "novelty_value": 0.5,
                            },
                        },
                        "prompts": ["What gap is this probing?"],
                        "tags": ["blind-spot"],
                        "created_at": when,
                        "created_by": "opus-4-7",
                        "updated_at": when,
                        "updated_by": "opus-4-7",
                    },
                    "prior_version": None,
                    "rationale": (
                        f"Pool gap relative to {parent_pool_member}: this targets "
                        "an under-probed area surfaced in recent analysis."
                    ),
                    "tags_touched": ["blind-spot"],
                }
            ]
        }
    )


def test_load_active_pool_includes_main_and_secondary_skips_retired(tmp_path: Path) -> None:
    main_active = _make_exercise(id_="main-a", category=ExerciseCategory.MAIN)
    main_retired = _make_exercise(
        id_="main-old",
        category=ExerciseCategory.MAIN,
        status=ExerciseStatus.RETIRED,
    )
    secondary = _make_exercise(
        id_="secondary-a",
        category=ExerciseCategory.SECONDARY,
        parent_id="main-a",
    )
    _seed_exercise_files(tmp_path / "exercises", [main_active, main_retired, secondary])
    pool = load_active_pool(tmp_path / "exercises")
    assert {ex.id for ex in pool} == {"main-a", "secondary-a"}


def test_blind_spots_dry_run_does_not_persist(tmp_path: Path, capsys) -> None:
    _seed_exercise_files(
        tmp_path / "exercises",
        [_make_exercise(id_="main-a", category=ExerciseCategory.MAIN)],
    )
    settings = _settings(tmp_path)
    fake_response = _create_proposal_json("main-fresh-probe", "main-a")

    with (
        patch(
            "plastiglom.apps.meta_engine.__main__.load_settings",
            return_value=settings,
        ),
        patch(
            "plastiglom.apps.meta_engine.__main__._build_router",
            return_value=FakeRouter(text=fake_response),
        ),
    ):
        rc = meta_main(["--dry-run", "blind-spots", "--days", "7"])

    assert rc == 0
    out = capsys.readouterr().out
    assert "would propose 1" in out
    payload = json.loads(out.split("\n", 1)[1])
    assert payload[0]["exercise_id"] == "main-fresh-probe"
    # Dry-run: no proposal files.
    assert list_proposals(tmp_path) == []


def test_blind_spots_persists_when_not_dry_run(tmp_path: Path, capsys) -> None:
    _seed_exercise_files(
        tmp_path / "exercises",
        [_make_exercise(id_="main-a", category=ExerciseCategory.MAIN)],
    )
    settings = _settings(tmp_path)
    fake_response = _create_proposal_json("main-new-coverage", "main-a")

    with (
        patch(
            "plastiglom.apps.meta_engine.__main__.load_settings",
            return_value=settings,
        ),
        patch(
            "plastiglom.apps.meta_engine.__main__._build_router",
            return_value=FakeRouter(text=fake_response),
        ),
    ):
        rc = meta_main(["blind-spots", "--days", "30"])

    assert rc == 0
    records = list_proposals(tmp_path)
    assert len(records) == 1
    assert records[0].proposal.exercise.id == "main-new-coverage"
    assert records[0].status.value == "pending"
    assert "filed 1 proposal" in capsys.readouterr().out


def test_generate_reads_files_and_persists(tmp_path: Path, capsys) -> None:
    _seed_exercise_files(
        tmp_path / "exercises",
        [_make_exercise(id_="main-a", category=ExerciseCategory.MAIN)],
    )
    settings = _settings(tmp_path)
    analysis_path = tmp_path / "analysis_excerpt.md"
    analysis_path.write_text("Recent analysis: pattern X is recurring.")
    memory_path = tmp_path / "memory_excerpt.md"
    memory_path.write_text("Memory: subject A is important.")
    fake_response = _create_proposal_json("main-explicit-probe", "main-a")

    with (
        patch(
            "plastiglom.apps.meta_engine.__main__.load_settings",
            return_value=settings,
        ),
        patch(
            "plastiglom.apps.meta_engine.__main__._build_router",
            return_value=FakeRouter(text=fake_response),
        ),
    ):
        rc = meta_main(
            [
                "generate",
                "--analysis",
                str(analysis_path),
                "--memory",
                str(memory_path),
            ]
        )

    assert rc == 0
    records = list_proposals(tmp_path)
    assert {r.proposal.exercise.id for r in records} == {"main-explicit-probe"}
    assert "filed 1 proposal" in capsys.readouterr().out


def test_generate_returns_2_when_pool_is_empty(tmp_path: Path, caplog) -> None:
    settings = _settings(tmp_path)
    analysis_path = tmp_path / "x.md"
    analysis_path.write_text("anything")
    with (
        patch(
            "plastiglom.apps.meta_engine.__main__.load_settings",
            return_value=settings,
        ),
        patch(
            "plastiglom.apps.meta_engine.__main__._build_router",
            return_value=FakeRouter(text="{}"),
        ),
    ):
        rc = meta_main(["generate", "--analysis", str(analysis_path)])
    assert rc == 2


def test_blind_spots_returns_2_when_pool_is_empty(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    with (
        patch(
            "plastiglom.apps.meta_engine.__main__.load_settings",
            return_value=settings,
        ),
        patch(
            "plastiglom.apps.meta_engine.__main__._build_router",
            return_value=FakeRouter(text="{}"),
        ),
    ):
        rc = meta_main(["blind-spots"])
    assert rc == 2


def test_garbage_response_yields_zero_proposals(tmp_path: Path, capsys) -> None:
    _seed_exercise_files(
        tmp_path / "exercises",
        [_make_exercise(id_="main-a", category=ExerciseCategory.MAIN)],
    )
    settings = _settings(tmp_path)
    with (
        patch(
            "plastiglom.apps.meta_engine.__main__.load_settings",
            return_value=settings,
        ),
        patch(
            "plastiglom.apps.meta_engine.__main__._build_router",
            return_value=FakeRouter(text="this is not JSON at all"),
        ),
    ):
        rc = meta_main(["blind-spots"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "filed 0 proposal" in out
    assert list_proposals(tmp_path) == []


def test_unknown_subcommand_exits(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        meta_main(["nonsense"])
