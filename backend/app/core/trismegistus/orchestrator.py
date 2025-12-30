"""
TRISMEGISTUS - The Orchestrator

Named after Hermes Trismegistus ("Thrice-Great Hermes"),
this system coordinates all other subsystems.

Responsibilities:
1. Receive user queries
2. Coordinate SHEBA (observation), LOGOS (proposal), PAPERMOON (verification)
3. Attach LAPLACE explanations
4. Manage the query lifecycle
"""
from typing import Optional
from sqlalchemy.orm import Session

from app.schemas.chat import ChatContext, ChatResponse, ExplanationSource
from app.core.sheba.observer import ShebaObserver
from app.core.logos.actor import LogosActor
from app.core.laplace.explain import LaplaceExplainer
from app.core.papermoon.authority import PapermoonAuthority


class Orchestrator:
    """
    TRISMEGISTUS - Central orchestrator for the CHALDEA system.

    Query flow:
    1. SHEBA observes query → identifies relevant context
    2. LOGOS proposes response → generates answer
    3. PAPERMOON verifies → checks factual accuracy
    4. LAPLACE explains → attaches sources
    """

    def __init__(self, db: Session):
        self.db = db
        self.sheba = ShebaObserver(db)
        self.logos = LogosActor()
        self.papermoon = PapermoonAuthority(db)
        self.laplace = LaplaceExplainer(db)

    async def process_query(
        self,
        query: str,
        context: Optional[ChatContext] = None,
    ) -> ChatResponse:
        """
        Process a natural language query through the full pipeline.

        1. SHEBA: Observe and understand the query
        2. LOGOS: Generate a proposed response
        3. PAPERMOON: Verify the proposal
        4. LAPLACE: Attach explanations and sources
        """
        # Step 1: SHEBA observation
        observation = await self.sheba.observe(query, context)

        # Step 2: LOGOS proposal
        proposal = await self.logos.propose(query, observation)

        # Step 3: PAPERMOON verification
        verification = await self.papermoon.verify(proposal, observation)

        if not verification.approved:
            # If rejected, return with low confidence
            return ChatResponse(
                answer=proposal.answer,
                confidence=0.3,
                sources=[],
                related_events=observation.related_events,
                suggested_queries=[],
                reasoning_trace={"verification": "rejected", "reason": verification.reason}
            )

        # Step 4: LAPLACE explanation
        explanation = await self.laplace.explain(proposal, observation)

        return ChatResponse(
            answer=proposal.answer,
            sources=explanation.sources,
            confidence=verification.confidence,
            related_events=observation.related_events,
            suggested_queries=explanation.suggested_queries,
            proposal_id=proposal.id,
            reasoning_trace={
                "observation": observation.summary,
                "verification": "approved",
                "source_count": len(explanation.sources),
            }
        )

    async def observe_only(self, query: str) -> dict:
        """
        SHEBA observation without LLM processing.

        Useful for exploring what data is available.
        """
        observation = await self.sheba.observe(query, None)
        return {
            "query": query,
            "interpreted_as": observation.interpretation,
            "time_context": observation.time_context,
            "location_context": observation.location_context,
            "related_events": [e.id for e in observation.related_events],
            "related_persons": [p.id for p in observation.related_persons],
        }
