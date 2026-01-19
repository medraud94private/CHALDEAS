"""
SHEBA - Near-Future Observation Lens (근미래관측렌즈)

Named after the Queen of Sheba who sought wisdom,
this system observes and interprets queries.

Responsibilities:
1. Parse user queries to extract temporal/spatial context
2. Identify relevant events, persons, and locations
3. Provide structured observation for other systems
"""
import re
from dataclasses import dataclass
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_, not_

from app.models.event import Event
from app.models.person import Person
from app.models.location import Location
from app.schemas.chat import ChatContext

# Noise patterns to exclude
NOISE_PATTERNS = [
    "Mrs.%", "Mrs %", "Miss %", "Mr. %", "Mr %",
    "Sig.%", "Sig %", "Junr%", "Senr%",
    "Madame %", "Mme.%", "Mlle.%",
]


@dataclass
class Observation:
    """Result of SHEBA observation."""
    query: str
    interpretation: str  # What SHEBA understood
    time_context: Optional[dict] = None  # Extracted year/era
    location_context: Optional[dict] = None  # Extracted location
    related_events: list = None
    related_persons: list = None
    related_locations: list = None
    summary: str = ""

    def __post_init__(self):
        if self.related_events is None:
            self.related_events = []
        if self.related_persons is None:
            self.related_persons = []
        if self.related_locations is None:
            self.related_locations = []


class ShebaObserver:
    """
    SHEBA observation system.

    Analyzes queries to extract:
    - Temporal context (years, eras, periods)
    - Spatial context (locations, regions)
    - Entity references (persons, events)
    """

    # Common era patterns
    YEAR_PATTERNS = [
        r'(\d+)\s*(BCE|BC|B\.C\.E?\.|B\.C\.)',  # 490 BCE
        r'(\d+)\s*(CE|AD|A\.D\.)',               # 476 CE
        r'(\d+)(?:th|st|nd|rd)\s*century',       # 5th century
    ]

    def __init__(self, db: Session):
        self.db = db

    async def observe(
        self,
        query: str,
        context: Optional[ChatContext] = None,
    ) -> Observation:
        """
        Observe and interpret a user query.

        Extracts:
        - Time references (years, centuries, eras)
        - Location references
        - Named entities (persons, events)
        """
        query_lower = query.lower()

        # Extract temporal context
        time_context = self._extract_time(query)

        # Extract location context
        location_context = self._extract_location(query)

        # Find related entities
        related_events = self._find_related_events(query_lower, time_context)
        related_persons = self._find_related_persons(query_lower)
        related_locations = self._find_related_locations(query_lower)

        # Generate interpretation
        interpretation = self._generate_interpretation(
            query, time_context, location_context,
            related_events, related_persons
        )

        return Observation(
            query=query,
            interpretation=interpretation,
            time_context=time_context,
            location_context=location_context,
            related_events=related_events[:10],  # Limit to 10
            related_persons=related_persons[:10],
            related_locations=related_locations[:5],
            summary=f"Found {len(related_events)} events, {len(related_persons)} persons"
        )

    def _extract_time(self, query: str) -> Optional[dict]:
        """Extract temporal references from query."""
        for pattern in self.YEAR_PATTERNS:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                year = int(match.group(1))
                era = match.group(2).upper() if len(match.groups()) > 1 else "CE"

                # Convert to internal format (negative for BCE)
                if era in ("BCE", "BC", "B.C.E.", "B.C."):
                    year = -year

                return {"year": year, "era": era, "raw": match.group(0)}

        return None

    def _extract_location(self, query: str) -> Optional[dict]:
        """Extract location references from query."""
        # Search for known locations in the query
        locations = self.db.query(Location).all()

        for loc in locations:
            if loc.name.lower() in query.lower():
                return {
                    "id": loc.id,
                    "name": loc.name,
                    "latitude": float(loc.latitude),
                    "longitude": float(loc.longitude),
                }
            if loc.modern_name and loc.modern_name.lower() in query.lower():
                return {
                    "id": loc.id,
                    "name": loc.name,
                    "modern_name": loc.modern_name,
                    "latitude": float(loc.latitude),
                    "longitude": float(loc.longitude),
                }

        return None

    def _find_related_events(
        self,
        query: str,
        time_context: Optional[dict] = None,
    ) -> list[Event]:
        """Find events related to the query."""
        events_query = self.db.query(Event)

        # If we have a time context, filter by it
        if time_context and "year" in time_context:
            year = time_context["year"]
            # Find events within 50 years of the mentioned year
            events_query = events_query.filter(
                Event.date_start.between(year - 50, year + 50)
            )

        # Text search in titles
        words = query.split()
        for word in words:
            if len(word) > 3:  # Skip short words
                events_query = events_query.filter(
                    Event.title.ilike(f"%{word}%")
                )

        return events_query.limit(20).all()

    def _find_related_persons(self, query: str) -> list[Person]:
        """Find persons mentioned in the query."""
        # Exclude noise data
        noise_filters = [Person.name.ilike(p) for p in NOISE_PATTERNS]
        base_query = self.db.query(Person).filter(not_(or_(*noise_filters)))

        # Search by name match instead of loading all
        words = query.lower().split()
        if not words:
            return []

        # Try to find persons whose name appears in query
        related = []
        for word in words:
            if len(word) > 2:
                matches = base_query.filter(
                    or_(
                        Person.name.ilike(f"%{word}%"),
                        Person.name_ko.ilike(f"%{word}%") if Person.name_ko else False
                    )
                ).limit(10).all()
                related.extend(matches)

        # Deduplicate
        seen = set()
        unique = []
        for p in related:
            if p.id not in seen:
                seen.add(p.id)
                unique.append(p)

        return unique[:20]

    def _find_related_locations(self, query: str) -> list[Location]:
        """Find locations mentioned in the query."""
        locations = self.db.query(Location).all()

        related = []
        for loc in locations:
            if loc.name.lower() in query:
                related.append(loc)

        return related

    def _generate_interpretation(
        self,
        query: str,
        time_context: Optional[dict],
        location_context: Optional[dict],
        events: list[Event],
        persons: list[Person],
    ) -> str:
        """Generate a human-readable interpretation of the observation."""
        parts = [f"Query about"]

        if time_context:
            year = abs(time_context["year"])
            era = "BCE" if time_context["year"] < 0 else "CE"
            parts.append(f"time period around {year} {era}")

        if location_context:
            parts.append(f"location: {location_context['name']}")

        if persons:
            names = [p.name for p in persons[:3]]
            parts.append(f"persons: {', '.join(names)}")

        if events:
            parts.append(f"({len(events)} related events found)")

        return " ".join(parts)
