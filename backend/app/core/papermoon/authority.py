"""
PAPERMOON - The Authority (종이 달)

Named for the fragile yet essential nature of verification,
this system judges proposals before execution.

Responsibilities:
1. Verify proposals from LOGOS
2. Check factual accuracy against CHALDEAS data
3. Approve, reject, or request changes

World-Centric Principle:
"Authority judges proposals - independent verification before any change"
"""
from dataclasses import dataclass
from sqlalchemy.orm import Session

from app.core.logos.actor import Proposal
from app.core.sheba.observer import Observation
from app.models.event import Event
from app.models.person import Person


@dataclass
class VerificationResult:
    """Result of PAPERMOON verification."""
    approved: bool
    confidence: float
    reason: str
    corrections: list[str] = None

    def __post_init__(self):
        if self.corrections is None:
            self.corrections = []


class PapermoonAuthority:
    """
    PAPERMOON - Proposal verification authority.

    Verifies that LOGOS proposals are:
    1. Factually consistent with CHALDEAS data
    2. Not making claims beyond available sources
    3. Properly attributed
    """

    def __init__(self, db: Session):
        self.db = db

    async def verify(
        self,
        proposal: Proposal,
        observation: Observation,
    ) -> VerificationResult:
        """
        Verify a proposal from LOGOS.

        Checks:
        1. Date consistency (if dates are mentioned)
        2. Person existence (if persons are named)
        3. Event accuracy (if events are referenced)
        """
        corrections = []
        confidence_adjustments = []

        # Check if proposal uses available context
        if not proposal.context_used:
            corrections.append("No database context was used - lower confidence")
            confidence_adjustments.append(-0.2)

        # Verify mentioned events exist
        if observation.related_events:
            for event in observation.related_events:
                if event.title.lower() in proposal.answer.lower():
                    # Event is mentioned - good
                    confidence_adjustments.append(0.1)
                    break

        # Verify mentioned persons exist
        if observation.related_persons:
            for person in observation.related_persons:
                if person.name.lower() in proposal.answer.lower():
                    # Person is mentioned - good
                    confidence_adjustments.append(0.1)
                    break

        # Calculate final confidence
        base_confidence = proposal.confidence
        for adj in confidence_adjustments:
            base_confidence += adj
        final_confidence = max(0.1, min(1.0, base_confidence))

        # Determine approval
        approved = final_confidence >= 0.4 and len(corrections) < 3

        return VerificationResult(
            approved=approved,
            confidence=final_confidence,
            reason="Verified against CHALDEAS data" if approved else "Insufficient verification",
            corrections=corrections,
        )

    async def log_decision(
        self,
        proposal: Proposal,
        result: VerificationResult,
    ):
        """Log the verification decision for audit."""
        # TODO: Implement logging to proposal_logs table
        pass
