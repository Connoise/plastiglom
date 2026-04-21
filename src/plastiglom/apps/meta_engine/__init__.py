"""Meta-engine: Opus-driven management of the evolving exercise pool.

See §7.7. Default stance: NEVER auto-apply changes. Always propose, user
refines in the web app, user approves, and the change is logged with rationale
to `exercise_history/`.
"""

from plastiglom.apps.meta_engine.proposals import (
    ExerciseProposal,
    ProposalAction,
    apply_proposal,
    record_history,
)

__all__ = ["ExerciseProposal", "ProposalAction", "apply_proposal", "record_history"]
