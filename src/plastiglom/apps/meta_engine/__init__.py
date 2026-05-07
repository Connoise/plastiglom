"""Meta-engine: Opus-driven management of the evolving exercise pool.

See §7.7. Default stance: NEVER auto-apply changes. Always propose, user
refines in the web app, user approves, and the change is logged with rationale
to `exercise_history/`.
"""

from plastiglom.apps.meta_engine.blind_spots import detect_blind_spots
from plastiglom.apps.meta_engine.generator import (
    Generator,
    GeneratorInput,
    parse_response,
)
from plastiglom.apps.meta_engine.proposals import (
    ExerciseProposal,
    ProposalAction,
    apply_proposal,
    load_active_pool,
    record_history,
    validate_exercise_for_action,
)
from plastiglom.apps.meta_engine.queue import (
    ProposalRecord,
    ProposalStatus,
    compute_diff,
    decide,
    list_proposals,
    load_proposal,
    make_proposal_id,
    make_record,
    proposal_path,
    save_proposal,
)

__all__ = [
    "ExerciseProposal",
    "Generator",
    "GeneratorInput",
    "ProposalAction",
    "ProposalRecord",
    "ProposalStatus",
    "apply_proposal",
    "compute_diff",
    "decide",
    "detect_blind_spots",
    "list_proposals",
    "load_active_pool",
    "load_proposal",
    "make_proposal_id",
    "make_record",
    "parse_response",
    "proposal_path",
    "record_history",
    "save_proposal",
    "validate_exercise_for_action",
]
