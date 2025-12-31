"""
JSON-based data service for development/testing without PostgreSQL.

Loads data from processed JSON files.
"""
import json
from pathlib import Path
from typing import Optional
from functools import lru_cache


class JSONDataService:
    """Serves data from processed JSON files."""

    def __init__(self, data_dir: Path = None):
        if data_dir is None:
            # Try multiple paths for flexibility (local dev vs Docker)
            possible_paths = [
                Path(__file__).parent.parent.parent.parent / "data" / "processed",  # Local dev
                Path("/app/data/processed"),  # Docker absolute
                Path("./data/processed"),  # Docker relative
            ]
            for path in possible_paths:
                if path.exists():
                    data_dir = path
                    break
            else:
                data_dir = possible_paths[0]  # Fallback

        self.data_dir = data_dir
        self._events = None
        self._locations = None
        self._persons = None

    @property
    def events(self) -> list[dict]:
        """Load and cache events."""
        if self._events is None:
            self._events = self._load_json("events_wikidata.json")
        return self._events

    @property
    def locations(self) -> list[dict]:
        """Load and cache locations (merged from all sources)."""
        if self._locations is None:
            pleiades = self._load_json("locations_pleiades.json")
            wikidata = self._load_json("locations_wikidata.json")
            self._locations = pleiades + wikidata
        return self._locations

    @property
    def persons(self) -> list[dict]:
        """Load and cache persons."""
        if self._persons is None:
            self._persons = self._load_json("persons_wikidata.json")
        return self._persons

    def _load_json(self, filename: str) -> list:
        """Load a JSON file."""
        filepath = self.data_dir / filename
        if not filepath.exists():
            return []
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading {filename}: {e}")
            return []

    def get_events(
        self,
        year_start: Optional[int] = None,
        year_end: Optional[int] = None,
        category: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict]:
        """Get events with optional filtering."""
        result = self.events

        if year_start is not None:
            result = [e for e in result if e.get("date_start") and e["date_start"] >= year_start]

        if year_end is not None:
            result = [e for e in result if e.get("date_start") and e["date_start"] <= year_end]

        if category:
            result = [e for e in result if e.get("category") == category]

        # Sort by date
        result = sorted(result, key=lambda x: x.get("date_start") or 0)

        return result[offset:offset + limit]

    def get_event_by_id(self, event_id: str) -> Optional[dict]:
        """Get a single event by ID."""
        for event in self.events:
            if event.get("id") == event_id:
                return event
        return None

    def get_locations(
        self,
        lat_min: Optional[float] = None,
        lat_max: Optional[float] = None,
        lng_min: Optional[float] = None,
        lng_max: Optional[float] = None,
        limit: int = 1000,
    ) -> list[dict]:
        """Get locations with optional bounding box."""
        result = self.locations

        if lat_min is not None:
            result = [l for l in result if l.get("latitude") and l["latitude"] >= lat_min]
        if lat_max is not None:
            result = [l for l in result if l.get("latitude") and l["latitude"] <= lat_max]
        if lng_min is not None:
            result = [l for l in result if l.get("longitude") and l["longitude"] >= lng_min]
        if lng_max is not None:
            result = [l for l in result if l.get("longitude") and l["longitude"] <= lng_max]

        return result[:limit]

    def get_events_for_map(
        self,
        year: Optional[int] = None,
        year_range: int = 50,
    ) -> list[dict]:
        """Get events formatted for map display."""
        events = self.events

        if year is not None:
            events = [
                e for e in events
                if e.get("date_start")
                and year - year_range <= e["date_start"] <= year + year_range
            ]

        # Format for map markers
        markers = []
        for e in events:
            if e.get("latitude") and e.get("longitude"):
                markers.append({
                    "id": e["id"],
                    "title": e["title"],
                    "date": e.get("date_start"),
                    "lat": e["latitude"],
                    "lng": e["longitude"],
                    "category": e.get("category", "general"),
                    "importance": e.get("importance", 3),
                })

        return markers

    def search(self, query: str, limit: int = 20) -> dict:
        """Search across all data types."""
        query_lower = query.lower()

        event_results = [
            e for e in self.events
            if query_lower in (e.get("title") or "").lower()
            or query_lower in (e.get("description") or "").lower()
        ][:limit]

        location_results = [
            l for l in self.locations
            if query_lower in (l.get("name") or "").lower()
        ][:limit]

        person_results = [
            p for p in self.persons
            if query_lower in (p.get("name") or "").lower()
        ][:limit]

        return {
            "events": event_results,
            "locations": location_results,
            "persons": person_results,
        }

    def get_stats(self) -> dict:
        """Get data statistics."""
        return {
            "events": len(self.events),
            "locations": len(self.locations),
            "persons": len(self.persons),
            "events_with_coords": sum(1 for e in self.events if e.get("latitude")),
        }


@lru_cache()
def get_data_service() -> JSONDataService:
    """Get singleton data service instance."""
    return JSONDataService()
