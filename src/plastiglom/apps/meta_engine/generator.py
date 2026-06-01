"""Opus-driven proposal generator. See §7.7 of DESIGN.md.

The generator emits structured `ExerciseProposal` objects from a JSON-mode
Opus call. The parser is defensive — malformed responses yield no proposals
rather than blowing up the caller, since this is an advisory pipeline.

Approval is *always* manual (§11). This module never persists changes; it
only writes pending records to the proposal queue.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from plastiglom.apps.meta_engine.proposals import ExerciseProposal, ProposalAction
from plastiglom.apps.meta_engine.queue import (
    ProposalRecord,
    compute_diff,
    make_record,
    save_proposal,
)
from plastiglom.packages.core.exercise import Exercise
from plastiglom.packages.llm.router import LLMCall, LLMRouter, Task

logger = logging.getLogger(__name__)


_SYSTEM = (
    "You are the meta-engine for a personal self-reflection system. The "
    "user's goal is to produce the data of a changing life — a journal kept "
    "with active intention to surface long-term weaknesses, strengths, and "
    "personal insights as they write.\n\n"
    "Given the active exercise pool and recent analysis, propose changes: "
    "create new exercises that open unexplored territory, edit existing ones "
    "whose framing is too narrow, retire exercises that no longer earn their "
    "slot.\n\n"
    "PRINCIPLES FOR EVERY EXERCISE YOU WRITE:\n"
    "- Invite daily contemplation, not a routine check. A good prompt cannot "
    "be honestly answered in one or two sentences; it opens a thread the user "
    "wants to follow. Avoid yes/no, rate-it-1-to-10, and did-you-do-X framings.\n"
    "- Pursue BREADTH across a whole life, not a shrinking set of productivity, "
    "awareness, or single-feeling checks. Deliberately rotate across domains: "
    "highlights of the day/week and how they felt in the moment versus in "
    "retrospect; the philosophy underneath the user's goals, lifestyle, social "
    "conditions, emotions, health, legacy, and creativity; the health of "
    "specific relationships they've built; what they learned and what genuinely "
    "interests them right now; perceived failures, weak points, and the real "
    "explanations behind them; and the alternate outcomes events could have "
    "taken.\n"
    "- Do not pigeon-hole. If the pool is already dense in one territory, "
    "propose somewhere it is thin. Reach for depth of personal exploration over "
    "another variation on a covered theme.\n"
    "- Write open, specific, unhurried prompts. A main exercise may carry "
    "several connected prompts that build on one another. Match tone to "
    "DESIGN.md: neutral, blunt, never softened on emotional grounds.\n\n"
    "Output JSON only with shape: "
    '{"proposals": [{"action": "create|edit|retire", "exercise": <full exercise '
    'object matching the existing schema>, "prior_version": <int|null>, '
    '"rationale": "...", "tags_touched": ["..."]}]}'
)


@dataclass
class GeneratorInput:
    pool: list[Exercise]
    analysis_excerpt: str
    memory_excerpt: str = ""


@dataclass
class Generator:
    router: LLMRouter
    vault_path: Path
    proposed_by: str = "opus-4-8"

    def generate(
        self,
        payload: GeneratorInput,
        *,
        dry_run: bool = False,
    ) -> list[ProposalRecord]:
        """Run a single Opus pass; persist any pending proposals.

        With `dry_run=True`, records are constructed and returned but not
        written to disk — useful for the CLI's preview path so callers can
        see what would be proposed without polluting the queue.
        """
        call = LLMCall(
            system=_SYSTEM,
            user=_render_user(payload),
            cacheable_system=[_render_pool(payload.pool)],
            max_tokens=4096,
        )
        response = self.router.invoke(Task.EXERCISE_EDIT, call)
        proposals = parse_response(response.text, payload.pool)
        when = datetime.now(tz=UTC)
        records: list[ProposalRecord] = []
        for proposal in proposals:
            record = make_record(proposal, proposed_by=self.proposed_by, when=when)
            if not dry_run:
                save_proposal(self.vault_path, record)
            records.append(record)
        return records


def parse_response(text: str, current_pool: list[Exercise]) -> list[ExerciseProposal]:
    """Pull a `proposals` array out of the LLM response and validate each."""
    try:
        data = json.loads(_extract_json(text))
    except (json.JSONDecodeError, ValueError):
        logger.warning("meta-engine response was not parseable JSON")
        return []

    proposals: list[ExerciseProposal] = []
    by_id = {ex.id: ex for ex in current_pool}
    for raw in data.get("proposals", []):
        try:
            proposal = _proposal_from_raw(raw, by_id)
        except Exception as exc:
            logger.warning("skipping malformed proposal: %s", exc)
            continue
        proposals.append(proposal)
    return proposals


def _proposal_from_raw(
    raw: dict[str, object],
    by_id: dict[str, Exercise],
) -> ExerciseProposal:
    action = ProposalAction(str(raw["action"]))
    exercise_dict = dict(raw["exercise"])  # type: ignore[arg-type]
    exercise = Exercise.model_validate(exercise_dict)
    prior_version = raw.get("prior_version")
    if action is ProposalAction.EDIT:
        prior = by_id.get(exercise.id)
        if prior is None:
            raise ValueError(f"edit proposal targets unknown exercise: {exercise.id}")
        if prior_version is None:
            prior_version = prior.version
        if exercise.version <= prior.version:
            raise ValueError(
                f"edit must bump version: {prior.version} -> {exercise.version}"
            )
    elif action is ProposalAction.CREATE:
        if exercise.id in by_id:
            raise ValueError(f"create proposal duplicates existing id: {exercise.id}")
    elif action is ProposalAction.RETIRE:
        if exercise.id not in by_id:
            raise ValueError(f"retire proposal targets unknown exercise: {exercise.id}")
        if exercise.status.value != "retired":
            raise ValueError("retire proposals must set status: retired")

    diff = compute_diff(by_id.get(exercise.id), exercise)
    rationale = str(raw.get("rationale") or "")
    tags_touched = [str(t) for t in (raw.get("tags_touched") or [])]
    return ExerciseProposal(
        action=action,
        exercise=exercise,
        rationale=rationale,
        prior_version=int(prior_version) if prior_version is not None else None,
        diff=diff,
        tags_touched=tags_touched,
    )


def _render_pool(pool: list[Exercise]) -> str:
    if not pool:
        return "ACTIVE POOL: (empty)"
    lines = ["ACTIVE POOL:"]
    for ex in pool:
        lines.append(
            f"- {ex.id}@v{ex.version} ({ex.category.value}/{ex.schedule.window.value}) "
            f"status={ex.status.value} prompts={len(ex.prompts)}"
        )
    return "\n".join(lines)


def _render_user(payload: GeneratorInput) -> str:
    blocks = [
        "Recent analysis excerpt:",
        payload.analysis_excerpt.strip() or "(none)",
    ]
    if payload.memory_excerpt:
        blocks += ["", "Memory excerpt:", payload.memory_excerpt.strip()]
    blocks += [
        "",
        "Propose 0-5 exercise changes. Favor breadth and depth over another "
        "narrow check; prefer prompts that invite real contemplation. Be "
        "precise. Respond with JSON only.",
    ]
    return "\n".join(blocks)


def _extract_json(text: str) -> str:
    start = text.find("{")
    if start == -1:
        raise ValueError("no JSON object found")
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    raise ValueError("unbalanced JSON object")
