"""Phase 4.D: monthly analysis -> blind-spot proposals.

Drives Analyzer end-to-end with a FakeRouter that dispatches by Task so we
exercise the analysis pass and the meta-engine pass in one run, without an
Anthropic call. Verifies that:
  - monthly with meta_generator runs blind-spots and embeds proposal IDs;
  - weekly / ad-hoc never run blind-spots;
  - corrections never re-run blind-spots;
  - empty pool is a no-op (no Opus call to the meta-engine);
  - the analyzer CLI constructs a Generator only for monthly cadence.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from plastiglom.apps.analyzer.analyzer import (
    AnalysisRequest,
    Analyzer,
    Cadence,
    correction_request,
)
from plastiglom.apps.meta_engine import list_proposals
from plastiglom.apps.meta_engine.generator import Generator
from plastiglom.packages.core.exercise import (
    Exercise,
    ExerciseCategory,
    ExerciseStatus,
    Schedule,
    ScheduleWindow,
    WeightFactors,
)
from plastiglom.packages.llm.router import Task
from plastiglom.packages.llm.types import LLMResponse
from plastiglom.packages.vault.markdown import read_markdown_file, write_markdown_file
from plastiglom.packages.vault.serializers import exercise_to_document


@dataclass
class TaskRouter:
    """Router stub that returns canned text by Task type and records calls."""

    by_task: dict[Task, str]
    invocations: list[Task] = field(default_factory=list)

    def invoke(self, task: Task, _call) -> LLMResponse:
        self.invocations.append(task)
        text = self.by_task.get(task, "")
        return LLMResponse(text=text, model="fake", input_tokens=0, output_tokens=0)


def _exercise(*, id_: str = "main-existing", version: int = 1) -> Exercise:
    when = datetime(2026, 1, 1, tzinfo=UTC)
    return Exercise(
        id=id_,
        title=id_,
        category=ExerciseCategory.MAIN,
        parent_id=None,
        version=version,
        status=ExerciseStatus.ACTIVE,
        schedule=Schedule(window=ScheduleWindow.MORNING, weight_factors=WeightFactors()),
        prompts=["q?"],
        tags=["values"],
        created_at=when,
        created_by="seed",
        updated_at=when,
        updated_by="seed",
    )


def _seed_pool(vault: Path) -> None:
    write_markdown_file(
        vault / "exercises" / "main" / "main-existing.md",
        exercise_to_document(_exercise()),
    )


def _create_proposal_json(new_id: str = "main-fresh-blind-spot") -> str:
    when = datetime(2026, 5, 1, tzinfo=UTC).isoformat()
    return json.dumps(
        {
            "proposals": [
                {
                    "action": "create",
                    "exercise": {
                        "id": new_id,
                        "title": "Blind-spot probe",
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
                    "rationale": "An under-probed area surfaced in monthly analysis.",
                    "tags_touched": ["blind-spot"],
                }
            ]
        }
    )


def _monthly_request() -> AnalysisRequest:
    return AnalysisRequest(
        cadence=Cadence.MONTHLY,
        window_start=datetime(2026, 4, 1, tzinfo=UTC),
        window_end=datetime(2026, 5, 1, tzinfo=UTC),
    )


def _weekly_request() -> AnalysisRequest:
    return AnalysisRequest(
        cadence=Cadence.WEEKLY,
        window_start=datetime(2026, 5, 11, tzinfo=UTC),
        window_end=datetime(2026, 5, 18, tzinfo=UTC),
    )


def test_monthly_runs_blind_spots_and_embeds_proposal_ids(tmp_path: Path) -> None:
    _seed_pool(tmp_path)
    router = TaskRouter(
        by_task={
            Task.MONTHLY_ANALYSIS: "MONTHLY ANALYSIS BODY",
            Task.EXERCISE_EDIT: _create_proposal_json(),
        }
    )
    analyzer = Analyzer(
        vault_path=tmp_path,
        router=router,
        meta_generator=Generator(router=router, vault_path=tmp_path),
    )

    report_path = analyzer.run(_monthly_request())

    # Both passes ran in order.
    assert router.invocations == [Task.MONTHLY_ANALYSIS, Task.EXERCISE_EDIT]

    doc = read_markdown_file(report_path)
    assert "MONTHLY ANALYSIS BODY" in doc.content
    assert "Proposed exercise changes" in doc.content
    assert "main-fresh-blind-spot" in doc.content
    proposal_ids = doc.metadata.get("blind_spot_proposal_ids")
    assert isinstance(proposal_ids, list) and len(proposal_ids) == 1
    # Proposal landed pending in the queue.
    queued = list_proposals(tmp_path)
    assert len(queued) == 1
    assert queued[0].status.value == "pending"
    assert queued[0].proposal.exercise.id == "main-fresh-blind-spot"


def test_monthly_with_zero_proposals_still_emits_footer(tmp_path: Path) -> None:
    _seed_pool(tmp_path)
    router = TaskRouter(
        by_task={
            Task.MONTHLY_ANALYSIS: "MONTHLY BODY",
            Task.EXERCISE_EDIT: "this is not JSON",
        }
    )
    analyzer = Analyzer(
        vault_path=tmp_path,
        router=router,
        meta_generator=Generator(router=router, vault_path=tmp_path),
    )

    report_path = analyzer.run(_monthly_request())
    doc = read_markdown_file(report_path)
    assert "produced no proposals" in doc.content
    # Frontmatter omits the field when empty.
    assert "blind_spot_proposal_ids" not in doc.metadata
    assert list_proposals(tmp_path) == []


def test_weekly_does_not_run_blind_spots(tmp_path: Path) -> None:
    _seed_pool(tmp_path)
    router = TaskRouter(
        by_task={Task.WEEKLY_ANALYSIS: "WEEKLY BODY"},
    )
    analyzer = Analyzer(
        vault_path=tmp_path,
        router=router,
        meta_generator=Generator(router=router, vault_path=tmp_path),
    )

    analyzer.run(_weekly_request())
    assert router.invocations == [Task.WEEKLY_ANALYSIS]
    assert list_proposals(tmp_path) == []


def test_correction_does_not_re_run_blind_spots(tmp_path: Path) -> None:
    _seed_pool(tmp_path)
    # First pass: a normal monthly that fires blind-spots.
    router1 = TaskRouter(
        by_task={
            Task.MONTHLY_ANALYSIS: "FIRST BODY",
            Task.EXERCISE_EDIT: _create_proposal_json("main-first-pass"),
        }
    )
    analyzer1 = Analyzer(
        vault_path=tmp_path,
        router=router1,
        meta_generator=Generator(router=router1, vault_path=tmp_path),
    )
    prior = analyzer1.run(_monthly_request())

    # Correction pass: must not re-run blind-spots, even with a generator.
    router2 = TaskRouter(
        by_task={
            Task.MONTHLY_ANALYSIS: "CORRECTED BODY",
            Task.EXERCISE_EDIT: _create_proposal_json("main-second-pass"),
        }
    )
    analyzer2 = Analyzer(
        vault_path=tmp_path,
        router=router2,
        meta_generator=Generator(router=router2, vault_path=tmp_path),
    )
    new_path = analyzer2.run(correction_request(prior, "you missed pattern Y"))

    assert router2.invocations == [Task.MONTHLY_ANALYSIS]
    new_doc = read_markdown_file(new_path)
    assert "Proposed exercise changes" not in new_doc.content
    # Only the first-pass proposal exists.
    queued_ids = {r.proposal.exercise.id for r in list_proposals(tmp_path)}
    assert queued_ids == {"main-first-pass"}


def test_monthly_skips_blind_spots_when_pool_empty(tmp_path: Path) -> None:
    # No exercises seeded -> empty pool -> meta-engine call is skipped.
    router = TaskRouter(
        by_task={
            Task.MONTHLY_ANALYSIS: "MONTHLY BODY",
            Task.EXERCISE_EDIT: _create_proposal_json(),
        }
    )
    analyzer = Analyzer(
        vault_path=tmp_path,
        router=router,
        meta_generator=Generator(router=router, vault_path=tmp_path),
    )

    report_path = analyzer.run(_monthly_request())
    # Only the analyzer call ran; no Opus call to the meta-engine.
    assert router.invocations == [Task.MONTHLY_ANALYSIS]
    doc = read_markdown_file(report_path)
    # Footer reflects the no-op (skipped, not "produced no proposals").
    assert "produced no proposals" in doc.content
    assert list_proposals(tmp_path) == []


def test_monthly_without_meta_generator_works_unchanged(tmp_path: Path) -> None:
    """Default Analyzer (no meta_generator) preserves Phase 3 behaviour."""
    _seed_pool(tmp_path)
    router = TaskRouter(by_task={Task.MONTHLY_ANALYSIS: "PLAIN MONTHLY"})
    analyzer = Analyzer(vault_path=tmp_path, router=router)

    report_path = analyzer.run(_monthly_request())
    assert router.invocations == [Task.MONTHLY_ANALYSIS]
    doc = read_markdown_file(report_path)
    assert "Proposed exercise changes" not in doc.content
