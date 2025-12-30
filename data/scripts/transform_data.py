#!/usr/bin/env python3
"""
Data Transformation Script for CHALDEAS.

Transforms raw collected data into a unified format and enriches
with geographic coordinates using the GeoResolver.

Usage:
    python transform_data.py --input data/raw --output data/processed
    python transform_data.py --source wikidata
    python transform_data.py --resolve-only  # Just resolve missing coordinates
"""
import argparse
import asyncio
from pathlib import Path
import json
from typing import Optional
from dataclasses import dataclass, asdict
from datetime import datetime
import re
import sys

sys.path.insert(0, str(Path(__file__).parent))

from geo_resolver import GeoResolver, ResolvedLocation


@dataclass
class UnifiedEvent:
    """Unified event format for CHALDEAS."""
    id: str
    title: str
    title_ko: Optional[str]
    description: Optional[str]
    description_ko: Optional[str]
    date_start: int  # BCE as negative
    date_end: Optional[int]
    date_precision: str  # year, month, day, decade, century
    location_name: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]
    location_source: Optional[str]
    location_confidence: Optional[float]
    category: str
    importance: int  # 1-5
    source_type: str  # wikidata, perseus, gutenberg, etc.
    source_id: Optional[str]
    source_url: Optional[str]
    related_persons: list[str]
    related_events: list[str]
    tags: list[str]


@dataclass
class UnifiedPerson:
    """Unified person format for CHALDEAS."""
    id: str
    name: str
    name_ko: Optional[str]
    description: Optional[str]
    birth_year: Optional[int]
    death_year: Optional[int]
    birth_place: Optional[str]
    birth_latitude: Optional[float]
    birth_longitude: Optional[float]
    death_place: Optional[str]
    death_latitude: Optional[float]
    death_longitude: Optional[float]
    occupation: Optional[str]
    source_type: str
    source_id: Optional[str]
    source_url: Optional[str]
    related_events: list[str]
    tags: list[str]


@dataclass
class UnifiedLocation:
    """Unified location format for CHALDEAS."""
    id: str
    name: str
    name_ko: Optional[str]
    modern_name: Optional[str]
    latitude: float
    longitude: float
    location_type: str  # city, battle_site, temple, etc.
    time_periods: list[str]
    source_type: str
    source_id: Optional[str]
    source_url: Optional[str]
    pleiades_id: Optional[str]
    wikidata_id: Optional[str]


class DataTransformer:
    """Transforms and enriches collected data."""

    def __init__(self, input_dir: Path, output_dir: Path, pleiades_path: Optional[Path] = None):
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Initialize GeoResolver
        self.resolver = GeoResolver(pleiades_path)

        # Statistics
        self.stats = {
            "events_processed": 0,
            "events_with_coords": 0,
            "events_resolved": 0,
            "persons_processed": 0,
            "persons_with_coords": 0,
            "locations_processed": 0,
            "resolution_by_source": {},
        }

    async def transform_all(self):
        """Transform all data sources."""
        print("\n" + "=" * 60)
        print("CHALDEAS Data Transformation")
        print("=" * 60)

        # Transform each source
        await self.transform_wikidata()
        await self.transform_pleiades()
        # await self.transform_perseus()  # Future
        # await self.transform_gutenberg()  # Future

        # Save statistics
        self._save_stats()

        print("\n" + "=" * 60)
        print("Transformation Complete!")
        print("=" * 60)
        self._print_stats()

    async def transform_wikidata(self):
        """Transform Wikidata collected data."""
        wikidata_dir = self.input_dir / "wikidata"
        if not wikidata_dir.exists():
            print("Wikidata data not found, skipping...")
            return

        print("\nTransforming Wikidata data...")

        # Process events
        events_file = wikidata_dir / "wikidata_events.json"
        if events_file.exists():
            await self._transform_wikidata_events(events_file)

        # Process persons
        persons_file = wikidata_dir / "wikidata_persons.json"
        if persons_file.exists():
            await self._transform_wikidata_persons(persons_file)

        # Process cities (as locations)
        cities_file = wikidata_dir / "wikidata_cities.json"
        if cities_file.exists():
            await self._transform_wikidata_cities(cities_file)

    async def _transform_wikidata_events(self, file_path: Path):
        """Transform Wikidata events."""
        print(f"  Processing events from {file_path.name}...")

        with open(file_path, "r", encoding="utf-8") as f:
            raw_events = json.load(f)

        unified_events = []

        for raw in raw_events:
            self.stats["events_processed"] += 1

            # Parse date
            date_start, date_precision = self._parse_date(raw.get("date"))
            if date_start is None:
                continue

            # Get or resolve coordinates
            lat, lng, loc_source, loc_confidence = None, None, None, None
            coords = raw.get("coordinates")

            if coords:
                lat = coords.get("latitude")
                lng = coords.get("longitude")
                loc_source = "wikidata"
                loc_confidence = 0.9
                self.stats["events_with_coords"] += 1
            elif raw.get("location"):
                # Try to resolve
                resolved = await self.resolver.resolve(
                    raw["location"],
                    context={"year": date_start}
                )
                if resolved:
                    lat = resolved.latitude
                    lng = resolved.longitude
                    loc_source = resolved.source
                    loc_confidence = resolved.confidence
                    self.stats["events_resolved"] += 1
                    self._track_resolution_source(resolved.source)

            # Use category from raw if available, otherwise determine from description
            category = raw.get("category") or self._categorize_event(raw.get("description", ""))

            event = UnifiedEvent(
                id=f"wd_{raw.get('wikidata_id', '')}",
                title=raw.get("name"),
                title_ko=None,
                description=raw.get("description"),
                description_ko=None,
                date_start=date_start,
                date_end=None,
                date_precision=date_precision,
                location_name=raw.get("location"),
                latitude=lat,
                longitude=lng,
                location_source=loc_source,
                location_confidence=loc_confidence,
                category=category,
                importance=self._estimate_importance(raw),
                source_type="wikidata",
                source_id=raw.get("wikidata_id"),
                source_url=f"https://www.wikidata.org/wiki/{raw.get('wikidata_id')}",
                related_persons=[],
                related_events=[],
                tags=self._extract_tags(raw),
            )

            unified_events.append(asdict(event))

            # Rate limiting for API calls
            if self.stats["events_processed"] % 100 == 0:
                print(f"    Processed {self.stats['events_processed']} events...")
                await asyncio.sleep(0.1)

        # Save unified events
        output_file = self.output_dir / "events_wikidata.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(unified_events, f, indent=2, ensure_ascii=False)

        print(f"  Saved {len(unified_events)} events to {output_file.name}")

    async def _transform_wikidata_persons(self, file_path: Path):
        """Transform Wikidata persons."""
        print(f"  Processing persons from {file_path.name}...")

        with open(file_path, "r", encoding="utf-8") as f:
            raw_persons = json.load(f)

        unified_persons = []

        for raw in raw_persons:
            self.stats["persons_processed"] += 1

            # Parse dates
            birth_year, _ = self._parse_date(raw.get("birth_date"))
            death_year, _ = self._parse_date(raw.get("death_date"))

            # Birth coordinates
            birth_lat, birth_lng = None, None
            if raw.get("birth_coordinates"):
                birth_lat = raw["birth_coordinates"].get("latitude")
                birth_lng = raw["birth_coordinates"].get("longitude")
                self.stats["persons_with_coords"] += 1
            elif raw.get("birth_place"):
                resolved = await self.resolver.resolve(raw["birth_place"])
                if resolved:
                    birth_lat = resolved.latitude
                    birth_lng = resolved.longitude
                    self._track_resolution_source(resolved.source)

            # Death coordinates
            death_lat, death_lng = None, None
            if raw.get("death_coordinates"):
                death_lat = raw["death_coordinates"].get("latitude")
                death_lng = raw["death_coordinates"].get("longitude")
            elif raw.get("death_place"):
                resolved = await self.resolver.resolve(raw["death_place"])
                if resolved:
                    death_lat = resolved.latitude
                    death_lng = resolved.longitude

            wikidata_id = raw.get("wikidata_id", "")
            person = UnifiedPerson(
                id=f"wd_{wikidata_id}",
                name=raw.get("name"),
                name_ko=None,
                description=raw.get("description"),
                birth_year=birth_year,
                death_year=death_year,
                birth_place=raw.get("birth_place"),
                birth_latitude=birth_lat,
                birth_longitude=birth_lng,
                death_place=raw.get("death_place"),
                death_latitude=death_lat,
                death_longitude=death_lng,
                occupation=raw.get("occupation"),
                source_type="wikidata",
                source_id=wikidata_id,
                source_url=f"https://www.wikidata.org/wiki/{wikidata_id}" if wikidata_id else None,
                related_events=[],
                tags=[],
            )

            unified_persons.append(asdict(person))

            if self.stats["persons_processed"] % 100 == 0:
                print(f"    Processed {self.stats['persons_processed']} persons...")
                await asyncio.sleep(0.1)

        # Save unified persons
        output_file = self.output_dir / "persons_wikidata.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(unified_persons, f, indent=2, ensure_ascii=False)

        print(f"  Saved {len(unified_persons)} persons to {output_file.name}")

    async def _transform_wikidata_cities(self, file_path: Path):
        """Transform Wikidata cities to locations."""
        print(f"  Processing cities from {file_path.name}...")

        with open(file_path, "r", encoding="utf-8") as f:
            raw_cities = json.load(f)

        unified_locations = []

        for raw in raw_cities:
            self.stats["locations_processed"] += 1

            coords = raw.get("coordinates")
            if not coords:
                continue

            wikidata_id = raw.get("wikidata_id", "")
            location = UnifiedLocation(
                id=f"wd_{wikidata_id}",
                name=raw.get("name"),
                name_ko=None,
                modern_name=None,
                latitude=coords.get("latitude"),
                longitude=coords.get("longitude"),
                location_type="city",
                time_periods=[],
                source_type="wikidata",
                source_id=wikidata_id,
                source_url=f"https://www.wikidata.org/wiki/{wikidata_id}" if wikidata_id else None,
                pleiades_id=None,
                wikidata_id=wikidata_id,
            )

            unified_locations.append(asdict(location))

        # Save unified locations
        output_file = self.output_dir / "locations_wikidata.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(unified_locations, f, indent=2, ensure_ascii=False)

        print(f"  Saved {len(unified_locations)} locations to {output_file.name}")

    async def transform_pleiades(self):
        """Transform Pleiades collected data."""
        pleiades_dir = self.input_dir / "pleiades"
        if not pleiades_dir.exists():
            print("Pleiades data not found, skipping...")
            return

        print("\nTransforming Pleiades data...")

        locations_file = pleiades_dir / "pleiades_locations.json"
        if not locations_file.exists():
            return

        with open(locations_file, "r", encoding="utf-8") as f:
            raw_locations = json.load(f)

        unified_locations = []

        for raw in raw_locations:
            self.stats["locations_processed"] += 1

            coords = raw.get("coordinates")
            if not coords:
                continue

            # Extract time periods
            time_periods = []
            for tp in raw.get("time_periods", []):
                if isinstance(tp, dict) and tp.get("period"):
                    time_periods.append(tp["period"])

            pleiades_id = raw.get("pleiades_id", "")
            location = UnifiedLocation(
                id=f"pl_{pleiades_id}",
                name=raw.get("title"),
                name_ko=None,
                modern_name=None,
                latitude=coords.get("latitude"),
                longitude=coords.get("longitude"),
                location_type=raw.get("place_types", ["unknown"])[0] if raw.get("place_types") else "unknown",
                time_periods=time_periods,
                source_type="pleiades",
                source_id=pleiades_id,
                source_url=f"https://pleiades.stoa.org/places/{pleiades_id}" if pleiades_id else None,
                pleiades_id=pleiades_id,
                wikidata_id=None,
            )

            unified_locations.append(asdict(location))

        # Save unified locations
        output_file = self.output_dir / "locations_pleiades.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(unified_locations, f, indent=2, ensure_ascii=False)

        print(f"  Saved {len(unified_locations)} locations to {output_file.name}")

    def _parse_date(self, date_str: str) -> tuple[Optional[int], str]:
        """
        Parse a date string into year (BCE as negative) and precision.

        Returns:
            (year, precision) where year is negative for BCE
        """
        if not date_str:
            return None, "unknown"

        try:
            # ISO format: 2024-01-15T00:00:00Z or -0490-01-01T00:00:00Z
            if "T" in date_str:
                date_part = date_str.split("T")[0]

                # Handle BCE dates (negative years)
                if date_part.startswith("-"):
                    # Format: -YYYY-MM-DD
                    year = int(date_part.split("-")[1]) * -1
                    return year, "year"
                else:
                    # Format: YYYY-MM-DD
                    year = int(date_part.split("-")[0])
                    return year, "year"

            # Simple year
            if date_str.lstrip("-").isdigit():
                return int(date_str), "year"

        except (ValueError, IndexError):
            pass

        return None, "unknown"

    def _categorize_event(self, description: str) -> str:
        """Determine event category from description."""
        desc_lower = (description or "").lower()

        categories = {
            "battle": ["battle", "war", "siege", "conquest", "invasion"],
            "political": ["treaty", "revolution", "coronation", "election", "republic"],
            "cultural": ["festival", "games", "theater", "art", "literature"],
            "religious": ["temple", "prophet", "religious", "church", "ritual"],
            "scientific": ["discovery", "invention", "scientific", "astronomy"],
            "natural": ["earthquake", "flood", "plague", "famine", "volcanic"],
        }

        for category, keywords in categories.items():
            if any(kw in desc_lower for kw in keywords):
                return category

        return "general"

    def _estimate_importance(self, raw: dict) -> int:
        """Estimate event importance (1-5)."""
        # Could be enhanced with Wikipedia pageviews, link counts, etc.
        description = (raw.get("description") or "").lower()

        # World-changing events
        major_keywords = ["world war", "empire", "revolution", "ancient"]
        if any(kw in description for kw in major_keywords):
            return 5

        # Significant events
        significant_keywords = ["battle", "treaty", "king", "emperor"]
        if any(kw in description for kw in significant_keywords):
            return 4

        return 3  # Default

    def _extract_tags(self, raw: dict) -> list[str]:
        """Extract tags from raw data."""
        tags = []

        # Add country as tag
        if raw.get("country"):
            tags.append(raw["country"])

        return tags

    def _track_resolution_source(self, source: str):
        """Track which sources resolved locations."""
        if source not in self.stats["resolution_by_source"]:
            self.stats["resolution_by_source"][source] = 0
        self.stats["resolution_by_source"][source] += 1

    def _save_stats(self):
        """Save transformation statistics."""
        stats_file = self.output_dir / "transform_stats.json"
        with open(stats_file, "w", encoding="utf-8") as f:
            json.dump(self.stats, f, indent=2)

    def _print_stats(self):
        """Print transformation statistics."""
        print(f"\nStatistics:")
        print(f"  Events processed: {self.stats['events_processed']}")
        print(f"  Events with coordinates: {self.stats['events_with_coords']}")
        print(f"  Events resolved via GeoResolver: {self.stats['events_resolved']}")
        print(f"  Persons processed: {self.stats['persons_processed']}")
        print(f"  Persons with coordinates: {self.stats['persons_with_coords']}")
        print(f"  Locations processed: {self.stats['locations_processed']}")
        print(f"\nResolution by source:")
        for source, count in self.stats["resolution_by_source"].items():
            print(f"    {source}: {count}")

    async def close(self):
        """Close resources."""
        await self.resolver.close()


async def main():
    parser = argparse.ArgumentParser(description="CHALDEAS Data Transformer")
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("data/raw"),
        help="Input directory with raw data",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/processed"),
        help="Output directory for processed data",
    )
    parser.add_argument(
        "--pleiades",
        type=Path,
        help="Path to Pleiades locations JSON for resolver",
    )
    parser.add_argument(
        "--source",
        choices=["all", "wikidata", "pleiades", "perseus", "gutenberg"],
        default="all",
        help="Source to transform",
    )

    args = parser.parse_args()

    print("CHALDEAS Data Transformer")
    print(f"Input: {args.input}")
    print(f"Output: {args.output}")

    # Initialize transformer
    pleiades_path = args.pleiades
    if not pleiades_path:
        default_pleiades = args.input / "pleiades" / "pleiades_locations.json"
        if default_pleiades.exists():
            pleiades_path = default_pleiades

    transformer = DataTransformer(args.input, args.output, pleiades_path)

    try:
        if args.source == "all":
            await transformer.transform_all()
        elif args.source == "wikidata":
            await transformer.transform_wikidata()
        elif args.source == "pleiades":
            await transformer.transform_pleiades()
        else:
            print(f"Source {args.source} not yet implemented")
    finally:
        await transformer.close()


if __name__ == "__main__":
    asyncio.run(main())
