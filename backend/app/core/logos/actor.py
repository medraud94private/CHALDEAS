"""
LOGOS - The Word (로고스)

Named after the Greek concept of reason/word,
this system proposes responses using LLM.

Responsibilities:
1. Receive observation from SHEBA
2. Generate response proposals
3. NEVER execute - only propose

World-Centric Principle:
"Intelligence proposes, never executes"
"""
import uuid
from dataclasses import dataclass
from typing import Optional

from app.core.sheba.observer import Observation
from app.config import get_settings


@dataclass
class Proposal:
    """A proposed response from LOGOS."""
    id: str
    query: str
    answer: str
    rationale: str  # Why this answer
    confidence: float
    context_used: list[str]  # What context was used

    @classmethod
    def create(cls, query: str, answer: str, rationale: str, confidence: float, context: list[str]):
        return cls(
            id=str(uuid.uuid4()),
            query=query,
            answer=answer,
            rationale=rationale,
            confidence=confidence,
            context_used=context,
        )


class LogosActor:
    """
    LOGOS - LLM-based action proposer.

    Uses LLM to generate response proposals based on SHEBA observations.
    Does NOT execute anything - only proposes.
    """

    def __init__(self):
        self.settings = get_settings()
        self._llm = None  # Lazy load

    def _get_llm(self):
        """Lazy load LLM client."""
        if self._llm is None:
            if self.settings.anthropic_api_key:
                from anthropic import Anthropic
                self._llm = Anthropic(api_key=self.settings.anthropic_api_key)
                self._llm_type = "anthropic"
            elif self.settings.openai_api_key:
                from openai import OpenAI
                self._llm = OpenAI(api_key=self.settings.openai_api_key)
                self._llm_type = "openai"
            else:
                self._llm_type = "fallback"
        return self._llm

    async def propose(
        self,
        query: str,
        observation: Observation,
    ) -> Proposal:
        """
        Generate a response proposal based on observation.

        The proposal includes:
        - The answer text
        - Rationale for why this answer
        - Confidence level
        - What context was used
        """
        # Build context from observation
        context_items = []

        if observation.related_events:
            for event in observation.related_events[:5]:
                context_items.append(
                    f"Event: {event.title} ({event.date_display}) - {event.description[:200] if event.description else 'No description'}"
                )

        if observation.related_persons:
            for person in observation.related_persons[:3]:
                context_items.append(
                    f"Person: {person.name} ({person.lifespan_display}) - {person.biography[:200] if person.biography else 'No biography'}"
                )

        # Generate response
        llm = self._get_llm()

        if self._llm_type == "fallback" or llm is None:
            # Fallback: Generate answer from context directly
            answer = self._generate_fallback_answer(query, observation, context_items)
            rationale = "Generated from database context without LLM"
            confidence = 0.6
        else:
            # Use LLM to generate answer
            answer, rationale, confidence = await self._generate_llm_answer(
                query, observation, context_items
            )

        return Proposal.create(
            query=query,
            answer=answer,
            rationale=rationale,
            confidence=confidence,
            context=context_items,
        )

    def _generate_fallback_answer(
        self,
        query: str,
        observation: Observation,
        context_items: list[str],
    ) -> str:
        """Generate answer without LLM (fallback mode)."""
        if not observation.related_events and not observation.related_persons:
            return f"I don't have specific information about '{query}' in my database. Please try a different query."

        parts = []

        if observation.time_context:
            year = abs(observation.time_context["year"])
            era = "BCE" if observation.time_context["year"] < 0 else "CE"
            parts.append(f"Regarding events around {year} {era}:")

        if observation.related_events:
            event = observation.related_events[0]
            parts.append(f"\n\n**{event.title}** ({event.date_display})")
            if event.description:
                parts.append(f"\n{event.description[:500]}")

        if observation.related_persons:
            person = observation.related_persons[0]
            parts.append(f"\n\n**{person.name}** ({person.lifespan_display})")
            if person.biography:
                parts.append(f"\n{person.biography[:500]}")

        return "".join(parts) if parts else "No relevant information found."

    async def _generate_llm_answer(
        self,
        query: str,
        observation: Observation,
        context_items: list[str],
    ) -> tuple[str, str, float]:
        """Generate answer using LLM."""
        context_text = "\n".join(context_items) if context_items else "No specific context available."

        prompt = f"""You are a historian assistant. Answer the following question based on the provided context.

Context from historical database:
{context_text}

Question: {query}

Provide a concise, factual answer. If the context doesn't contain enough information, say so.
"""

        try:
            if self._llm_type == "anthropic":
                response = self._llm.messages.create(
                    model="claude-3-haiku-20240307",
                    max_tokens=500,
                    messages=[{"role": "user", "content": prompt}]
                )
                answer = response.content[0].text
            else:  # openai
                response = self._llm.chat.completions.create(
                    model="gpt-3.5-turbo",
                    max_tokens=500,
                    messages=[{"role": "user", "content": prompt}]
                )
                answer = response.choices[0].message.content

            return answer, "Generated by LLM from database context", 0.8

        except Exception as e:
            return self._generate_fallback_answer(query, observation, context_items), f"LLM error: {str(e)}", 0.5
