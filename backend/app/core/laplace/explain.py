"""
LAPLACE - Historical Record Electronic Sea (사상기록전자해)

Named after Pierre-Simon Laplace (mathematician who envisioned
complete knowledge of all particles), this system provides
explanations and source attribution.

Responsibilities:
1. Attach sources to answers
2. Trace causality and relationships
3. Answer "Why?" for any value

World-Centric Principle:
"Every value must be able to answer 'Why?'"
"""
from dataclasses import dataclass
from sqlalchemy.orm import Session

from app.core.logos.actor import Proposal
from app.core.sheba.observer import Observation
from app.schemas.chat import ExplanationSource
from app.schemas.source import Source as SourceSchema
from app.models.source import Source


@dataclass
class Explanation:
    """Complete explanation from LAPLACE."""
    sources: list[ExplanationSource]
    causality_chain: list[str]  # How events are connected
    suggested_queries: list[str]  # Follow-up questions


class LaplaceExplainer:
    """
    LAPLACE - Explanation and attribution system.

    For every answer, provides:
    1. Source attribution (where did this info come from?)
    2. Causality tracking (how are things connected?)
    3. Exploration suggestions (what else might interest you?)
    """

    def __init__(self, db: Session):
        self.db = db

    async def explain(
        self,
        proposal: Proposal,
        observation: Observation,
    ) -> Explanation:
        """
        Generate explanation for a proposal.

        Attaches:
        1. Sources from related events/persons
        2. Causality chain showing connections
        3. Suggested follow-up queries
        """
        sources = await self._find_sources(observation)
        causality = await self._trace_causality(observation)
        suggestions = await self._generate_suggestions(observation)

        return Explanation(
            sources=sources,
            causality_chain=causality,
            suggested_queries=suggestions,
        )

    async def _find_sources(self, observation: Observation) -> list[ExplanationSource]:
        """Find relevant sources for the observation."""
        sources = []

        # Get sources from related events
        for event in observation.related_events[:5]:
            if hasattr(event, 'sources') and event.sources:
                for source in event.sources:
                    sources.append(ExplanationSource(
                        source=SourceSchema(
                            id=source.id,
                            name=source.name,
                            type=source.type,
                            url=source.archive_url,
                            author=source.author,
                            archive_type=source.archive_type,
                            reliability=source.reliability,
                        ),
                        relevance=0.8,
                        excerpt=None,
                    ))

        # Get sources from related persons
        for person in observation.related_persons[:3]:
            if hasattr(person, 'sources') and person.sources:
                for source in person.sources:
                    sources.append(ExplanationSource(
                        source=SourceSchema(
                            id=source.id,
                            name=source.name,
                            type=source.type,
                            url=source.archive_url,
                            author=source.author,
                            archive_type=source.archive_type,
                            reliability=source.reliability,
                        ),
                        relevance=0.7,
                        excerpt=None,
                    ))

        # If no sources found, return reference to digital archives
        if not sources:
            # Add default reference sources
            default_sources = [
                ("Perseus Digital Library", "digital_archive", "perseus", "https://www.perseus.tufts.edu/"),
                ("Chinese Text Project", "digital_archive", "ctext", "https://ctext.org/"),
            ]
            for name, type_, archive, url in default_sources:
                sources.append(ExplanationSource(
                    source=SourceSchema(
                        id=0,
                        name=name,
                        type=type_,
                        url=url,
                        archive_type=archive,
                        reliability=4,
                    ),
                    relevance=0.3,
                    excerpt="General reference",
                ))

        return sources[:10]  # Limit to 10 sources

    async def _trace_causality(self, observation: Observation) -> list[str]:
        """Trace causal connections between events/persons."""
        chain = []

        if observation.related_events:
            events_sorted = sorted(
                observation.related_events,
                key=lambda e: e.date_start
            )
            for i, event in enumerate(events_sorted[:5]):
                chain.append(f"{event.date_display}: {event.title}")

        return chain

    async def _generate_suggestions(self, observation: Observation) -> list[str]:
        """Generate suggested follow-up queries."""
        suggestions = []

        # Suggest exploring related persons
        if observation.related_persons:
            person = observation.related_persons[0]
            suggestions.append(f"Tell me more about {person.name}")

        # Suggest exploring time period
        if observation.time_context:
            year = abs(observation.time_context["year"])
            era = "BCE" if observation.time_context["year"] < 0 else "CE"
            suggestions.append(f"What else happened around {year} {era}?")

        # Suggest exploring location
        if observation.location_context:
            loc = observation.location_context["name"]
            suggestions.append(f"What is the history of {loc}?")

        # Default suggestions
        if not suggestions:
            suggestions = [
                "What major events happened in ancient Greece?",
                "Tell me about famous philosophers",
                "What scientific discoveries were made in antiquity?",
            ]

        return suggestions[:4]

    async def explain_value(
        self,
        entity_type: str,
        entity_id: int,
        field: str,
    ) -> dict:
        """
        Explain a specific value in the database.

        This is the core "Why?" function - every value should
        be traceable to its sources.
        """
        # TODO: Implement detailed value explanation
        return {
            "entity": f"{entity_type}:{entity_id}",
            "field": field,
            "sources": [],
            "derivation": "Direct database value",
        }
