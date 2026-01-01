"""
Chain Generator Service
Generates historical chains using AI (Ollama local FREE, or OpenAI cloud)
"""
import json
import httpx
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload

from app.config import settings
from app.models import HistoricalChain, ChainSegment, Event, Person, Location, Period
from app.models.person import EventPerson
from app.schemas.chain import CurationRequest


class ChainGenerator:
    """
    Generates curated historical chains based on request type.

    Chain Types:
    - person_story: Events related to a person's life
    - place_story: Events that occurred at a location
    - era_story: Key events of a period
    - causal_chain: Cause-effect linked events
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.openai_client = None  # Lazy initialization

    async def _get_openai_client(self):
        """Lazy load OpenAI client."""
        if self.openai_client is None:
            if settings.openai_api_key:
                from openai import AsyncOpenAI
                self.openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
        return self.openai_client

    async def _call_ollama(self, prompt: str) -> Optional[str]:
        """Call Ollama API (local, FREE)."""
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    f"{settings.ollama_base_url}/api/generate",
                    json={
                        "model": settings.ollama_model,
                        "prompt": prompt,
                        "stream": False,
                        "options": {
                            "temperature": 0.7  # More creative for narratives
                        }
                    }
                )
                if response.status_code == 200:
                    result = response.json()
                    return result.get("response", "").strip()
                else:
                    print(f"Ollama error: {response.status_code}")
                    return None
        except httpx.ConnectError:
            print("Ollama not running. Start with: ollama serve")
            return None
        except Exception as e:
            print(f"Ollama error: {e}")
            return None

    async def find_cached_chain(self, request: CurationRequest) -> Optional[HistoricalChain]:
        """Find an existing cached chain matching the request."""
        query = select(HistoricalChain).options(
            selectinload(HistoricalChain.segments)
        ).where(
            HistoricalChain.chain_type == request.chain_type,
            HistoricalChain.visibility.in_(["cached", "featured", "system"])
        )

        # Match entity based on chain type
        if request.chain_type == "person_story" and request.person_id:
            query = query.where(HistoricalChain.person_id == request.person_id)
        elif request.chain_type == "place_story" and request.location_id:
            query = query.where(HistoricalChain.location_id == request.location_id)
        elif request.chain_type == "era_story" and request.period_id:
            query = query.where(HistoricalChain.period_id == request.period_id)

        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def generate_chain(self, request: CurationRequest) -> HistoricalChain:
        """Generate a new historical chain."""
        if request.chain_type == "person_story":
            return await self._generate_person_story(request)
        elif request.chain_type == "place_story":
            return await self._generate_place_story(request)
        elif request.chain_type == "era_story":
            return await self._generate_era_story(request)
        elif request.chain_type == "causal_chain":
            return await self._generate_causal_chain(request)
        else:
            raise ValueError(f"Unknown chain type: {request.chain_type}")

    async def _generate_person_story(self, request: CurationRequest) -> HistoricalChain:
        """Generate a biography chain for a person."""
        # Get the person
        person = await self.db.get(Person, request.person_id)
        if not person:
            raise ValueError(f"Person not found: {request.person_id}")

        # Get events related to this person
        # For PoC, we'll use a simple query - in production, use vector search
        events = await self._get_person_events(person.id, request.max_segments)

        # Create chain
        chain = HistoricalChain(
            title=f"The Story of {person.name}",
            title_ko=f"{person.name_ko or person.name}의 이야기" if person.name_ko else None,
            description=f"Key events in the life of {person.name}",
            chain_type="person_story",
            person_id=person.id,
            visibility="user"
        )

        # Create segments
        segments = []
        for order, event in enumerate(events, 1):
            narrative = await self._generate_narrative(event, person=person)
            segment = ChainSegment(
                segment_order=order,
                event_id=event.id,
                narrative=narrative,
                connection_type="follows" if order > 1 else None
            )
            segments.append(segment)

        chain.segments = segments
        return chain

    async def _generate_place_story(self, request: CurationRequest) -> HistoricalChain:
        """Generate a history chain for a location."""
        location = await self.db.get(Location, request.location_id)
        if not location:
            raise ValueError(f"Location not found: {request.location_id}")

        events = await self._get_location_events(
            location.id,
            request.year_start,
            request.year_end,
            request.max_segments
        )

        chain = HistoricalChain(
            title=f"History of {location.name}",
            title_ko=f"{location.name_ko or location.name}의 역사" if location.name_ko else None,
            description=f"Historical events at {location.name}",
            chain_type="place_story",
            location_id=location.id,
            visibility="user"
        )

        segments = []
        for order, event in enumerate(events, 1):
            narrative = await self._generate_narrative(event, location=location)
            segment = ChainSegment(
                segment_order=order,
                event_id=event.id,
                narrative=narrative,
                connection_type="follows" if order > 1 else None
            )
            segments.append(segment)

        chain.segments = segments
        return chain

    async def _generate_era_story(self, request: CurationRequest) -> HistoricalChain:
        """Generate an overview chain for a period/era."""
        period = await self.db.get(Period, request.period_id)
        if not period:
            raise ValueError(f"Period not found: {request.period_id}")

        events = await self._get_period_events(period, request.max_segments)

        chain = HistoricalChain(
            title=f"The {period.name} Era",
            title_ko=f"{period.name_ko or period.name} 시대" if period.name_ko else None,
            description=f"Key events of the {period.name} ({period.year_start}-{period.year_end or 'present'})",
            chain_type="era_story",
            period_id=period.id,
            visibility="user"
        )

        segments = []
        for order, event in enumerate(events, 1):
            narrative = await self._generate_narrative(event, period=period)
            segment = ChainSegment(
                segment_order=order,
                event_id=event.id,
                narrative=narrative,
                connection_type="parallel" if order > 1 else None
            )
            segments.append(segment)

        chain.segments = segments
        return chain

    async def _generate_causal_chain(self, request: CurationRequest) -> HistoricalChain:
        """Generate a cause-effect chain of events."""
        # Start with a seed event
        if request.year_start:
            query = select(Event).where(
                Event.date_start >= request.year_start
            ).order_by(Event.importance.desc()).limit(1)
            result = await self.db.execute(query)
            seed_event = result.scalar_one_or_none()
        else:
            raise ValueError("Causal chain requires year_start parameter")

        if not seed_event:
            raise ValueError("No events found for causal chain")

        # Follow causal relationships
        events = await self._follow_causal_chain(seed_event.id, request.max_segments)

        chain = HistoricalChain(
            title=f"Chain of Events: {seed_event.name[:50]}...",
            description=f"Cause-and-effect sequence starting from {seed_event.name}",
            chain_type="causal_chain",
            visibility="user"
        )

        segments = []
        for order, event in enumerate(events, 1):
            narrative = await self._generate_narrative(event)
            segment = ChainSegment(
                segment_order=order,
                event_id=event.id,
                narrative=narrative,
                connection_type="causes" if order > 1 else None
            )
            segments.append(segment)

        chain.segments = segments
        return chain

    # --- Helper Methods ---

    async def _get_person_events(self, person_id: int, limit: int) -> List[Event]:
        """Get events related to a person."""
        # First, try to get events via EventPerson junction table
        query = (
            select(Event)
            .join(EventPerson, Event.id == EventPerson.event_id)
            .where(EventPerson.person_id == person_id)
            .order_by(Event.date_start)
            .limit(limit)
        )
        result = await self.db.execute(query)
        events = list(result.scalars().all())

        # If no events found via junction table, filter by person's lifespan
        if not events:
            person = await self.db.get(Person, person_id)
            if person and person.birth_year:
                # Get events during person's lifetime (or nearby)
                year_start = person.birth_year - 20  # 20 years before birth
                year_end = (person.death_year or person.birth_year + 80) + 10

                query = (
                    select(Event)
                    .where(and_(
                        Event.date_start >= year_start,
                        Event.date_start <= year_end
                    ))
                    .order_by(Event.importance.desc(), Event.date_start)
                    .limit(limit)
                )
                result = await self.db.execute(query)
                events = list(result.scalars().all())

        return events

    async def _get_location_events(
        self,
        location_id: int,
        year_start: Optional[int],
        year_end: Optional[int],
        limit: int
    ) -> List[Event]:
        """Get events at a location within time range."""
        query = select(Event)
        if year_start:
            query = query.where(Event.date_start >= year_start)
        if year_end:
            query = query.where(Event.date_start <= year_end)
        query = query.order_by(Event.date_start).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def _get_period_events(self, period: Period, limit: int) -> List[Event]:
        """Get key events within a period."""
        query = select(Event).where(
            and_(
                Event.date_start >= period.year_start,
                Event.date_start <= (period.year_end or 2025)
            )
        ).order_by(Event.importance.desc(), Event.date_start).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def _follow_causal_chain(self, seed_event_id: int, limit: int) -> List[Event]:
        """Follow causal relationships from a seed event."""
        events = []
        current_id = seed_event_id

        for _ in range(limit):
            event = await self.db.get(Event, current_id)
            if not event:
                break
            events.append(event)

            # Look for caused events
            query = select(Event).where(Event.caused_by_id == current_id).limit(1)
            result = await self.db.execute(query)
            next_event = result.scalar_one_or_none()

            if not next_event:
                break
            current_id = next_event.id

        return events

    async def _generate_narrative(
        self,
        event: Event,
        person: Optional[Person] = None,
        location: Optional[Location] = None,
        period: Optional[Period] = None
    ) -> str:
        """Generate narrative text for a chain segment using AI."""
        # Prepare context
        context_parts = [f"Event: {event.name} ({event.date_start})"]
        if event.description:
            context_parts.append(f"Description: {event.description}")
        if person:
            context_parts.append(f"Person: {person.name}")
        if location:
            context_parts.append(f"Location: {location.name}")
        if period:
            context_parts.append(f"Period: {period.name}")

        prompt = f"""Write a brief (2-3 sentences) narrative about this historical event in the context provided.
Focus on its significance and connections. Be concise and factual.

{chr(10).join(context_parts)}

Narrative:"""

        # Use Ollama (free, local) by default
        if settings.llm_provider == "ollama":
            result = await self._call_ollama(prompt)
            if result:
                # Clean up any thinking tags from Qwen
                if "<think>" in result:
                    result = result.split("</think>")[-1].strip()
                return result
            # Fallback to template if Ollama fails
            return self._template_narrative(event, person, location, period)

        # OpenAI fallback
        client = await self._get_openai_client()
        if not client:
            return self._template_narrative(event, person, location, period)

        try:
            response = await client.chat.completions.create(
                model=settings.chain_model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=150
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"AI narrative generation failed: {e}")
            return self._template_narrative(event, person, location, period)

    def _template_narrative(
        self,
        event: Event,
        person: Optional[Person] = None,
        location: Optional[Location] = None,
        period: Optional[Period] = None
    ) -> str:
        """Fallback template-based narrative."""
        year_str = f"{abs(event.date_start)} {'BCE' if event.date_start < 0 else 'CE'}"

        if person:
            return f"In {year_str}, {person.name} was involved in {event.name}."
        elif location:
            return f"In {year_str}, {event.name} took place at {location.name}."
        elif period:
            return f"During the {period.name}, {event.name} occurred in {year_str}."
        else:
            return f"{event.name} occurred in {year_str}."
