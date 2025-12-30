"""
Wikidata SPARQL Collector

Website: https://www.wikidata.org/
Query Service: https://query.wikidata.org/

The most comprehensive structured knowledge base.
Millions of entities with coordinates, dates, and relationships.

License: CC0 (public domain)
"""
import httpx
import asyncio
from pathlib import Path
import json
from typing import Optional
from urllib.parse import quote


class WikidataCollector:
    """
    Collector for Wikidata using SPARQL queries.

    Extracts:
    - Historical events with locations and dates
    - Historical figures with birth/death places
    - Ancient cities and landmarks
    """

    SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.client = httpx.AsyncClient(
            timeout=120.0,
            headers={
                "User-Agent": "CHALDEAS/0.1 (Historical Knowledge System)",
                "Accept": "application/json",
            }
        )

    async def query(self, sparql: str) -> dict:
        """Execute a SPARQL query."""
        try:
            response = await self.client.get(
                self.SPARQL_ENDPOINT,
                params={"query": sparql, "format": "json"}
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"  Query error: {e}")
            return {"results": {"bindings": []}}

    async def get_historical_events(self, limit: int = 2000) -> list[dict]:
        """
        Get historical events with locations.

        Queries for battles - the most geolocatable event type.
        """
        print("Querying historical events (battles)...")

        # Simpler query - just battles with coordinates
        sparql = f"""
        SELECT DISTINCT ?event ?eventLabel ?eventDescription
               ?date ?coord ?countryLabel
        WHERE {{
          ?event wdt:P31 wd:Q178561.  # instance of battle
          ?event wdt:P625 ?coord.      # has coordinates

          OPTIONAL {{ ?event wdt:P585 ?date. }}
          OPTIONAL {{ ?event wdt:P17 ?country. }}

          SERVICE wikibase:label {{
            bd:serviceParam wikibase:language "en,ko".
          }}
        }}
        LIMIT {limit}
        """

        result = await self.query(sparql)
        events = self._parse_events(result)

        print(f"Found {len(events)} battle events")
        return events

    async def get_historical_figures(self, limit: int = 1000) -> list[dict]:
        """
        Get historical figures (before 1800) with birth/death places.
        """
        print("Querying historical figures...")

        # Simpler query - just people with birth coordinates
        sparql = f"""
        SELECT DISTINCT ?person ?personLabel ?personDescription
               ?birthDate ?deathDate ?birthCoord
               ?occupationLabel
        WHERE {{
          ?person wdt:P31 wd:Q5.  # Is a human
          ?person wdt:P569 ?birthDate.
          ?person wdt:P19 ?birthPlace.
          ?birthPlace wdt:P625 ?birthCoord.

          FILTER(YEAR(?birthDate) < 1800)

          OPTIONAL {{ ?person wdt:P570 ?deathDate. }}
          OPTIONAL {{ ?person wdt:P106 ?occupation. }}

          SERVICE wikibase:label {{
            bd:serviceParam wikibase:language "en,ko".
          }}
        }}
        LIMIT {limit}
        """

        result = await self.query(sparql)
        persons = self._parse_persons(result)

        print(f"Found {len(persons)} historical figures")
        return persons

    async def get_ancient_cities(self, limit: int = 2000) -> list[dict]:
        """
        Get ancient cities and settlements.
        """
        print("Querying ancient cities...")

        # Simpler query - just archaeological sites with coordinates
        sparql = f"""
        SELECT DISTINCT ?city ?cityLabel ?cityDescription
               ?coord ?countryLabel
        WHERE {{
          ?city wdt:P31 wd:Q839954.  # archaeological site
          ?city wdt:P625 ?coord.

          OPTIONAL {{ ?city wdt:P17 ?country. }}

          SERVICE wikibase:label {{
            bd:serviceParam wikibase:language "en,ko".
          }}
        }}
        LIMIT {limit}
        """

        result = await self.query(sparql)
        cities = self._parse_cities(result)

        print(f"Found {len(cities)} ancient cities")
        return cities

    def _parse_coords(self, coord_str: str) -> Optional[dict]:
        """Parse 'Point(lon lat)' format."""
        if not coord_str:
            return None
        try:
            # Format: "Point(-0.1275 51.507222222)"
            coord_str = coord_str.replace("Point(", "").replace(")", "")
            lon, lat = coord_str.split()
            return {"latitude": float(lat), "longitude": float(lon)}
        except:
            return None

    def _parse_events(self, result: dict) -> list[dict]:
        """Parse SPARQL results for events."""
        events = []
        seen = set()

        for binding in result.get("results", {}).get("bindings", []):
            event_id = binding.get("event", {}).get("value", "").split("/")[-1]

            if event_id in seen:
                continue
            seen.add(event_id)

            coord = self._parse_coords(
                binding.get("coord", {}).get("value")
            )

            events.append({
                "wikidata_id": event_id,
                "name": binding.get("eventLabel", {}).get("value"),
                "description": binding.get("eventDescription", {}).get("value"),
                "date": binding.get("date", {}).get("value"),
                "location": None,  # Will be extracted from coordinates
                "country": binding.get("countryLabel", {}).get("value"),
                "coordinates": coord,
            })

        return events

    def _parse_persons(self, result: dict) -> list[dict]:
        """Parse SPARQL results for persons."""
        persons = []
        seen = set()

        for binding in result.get("results", {}).get("bindings", []):
            person_id = binding.get("person", {}).get("value", "").split("/")[-1]

            if person_id in seen:
                continue
            seen.add(person_id)

            birth_coord = self._parse_coords(
                binding.get("birthCoord", {}).get("value")
            )

            persons.append({
                "wikidata_id": person_id,
                "name": binding.get("personLabel", {}).get("value"),
                "description": binding.get("personDescription", {}).get("value"),
                "birth_date": binding.get("birthDate", {}).get("value"),
                "death_date": binding.get("deathDate", {}).get("value"),
                "birth_place": None,  # Will derive from coordinates
                "birth_coordinates": birth_coord,
                "death_place": None,
                "death_coordinates": None,
                "occupation": binding.get("occupationLabel", {}).get("value"),
            })

        return persons

    def _parse_cities(self, result: dict) -> list[dict]:
        """Parse SPARQL results for cities."""
        cities = []
        seen = set()

        for binding in result.get("results", {}).get("bindings", []):
            city_id = binding.get("city", {}).get("value", "").split("/")[-1]

            if city_id in seen:
                continue
            seen.add(city_id)

            coord = self._parse_coords(
                binding.get("coord", {}).get("value")
            )

            cities.append({
                "wikidata_id": city_id,
                "name": binding.get("cityLabel", {}).get("value"),
                "description": binding.get("cityDescription", {}).get("value"),
                "coordinates": coord,
                "founded": None,
                "dissolved": None,
                "country": binding.get("countryLabel", {}).get("value"),
            })

        return cities

    async def collect_all(self):
        """Collect all historical data from Wikidata."""
        print("\n" + "=" * 60)
        print("Collecting from Wikidata")
        print("=" * 60)

        # Collect events
        events = await self.get_historical_events(limit=2000)
        events_file = self.output_dir / "wikidata_events.json"
        with open(events_file, "w", encoding="utf-8") as f:
            json.dump(events, f, indent=2, ensure_ascii=False)
        print(f"Saved events to {events_file}")

        await asyncio.sleep(2)  # Rate limiting

        # Collect persons
        persons = await self.get_historical_figures(limit=1000)
        persons_file = self.output_dir / "wikidata_persons.json"
        with open(persons_file, "w", encoding="utf-8") as f:
            json.dump(persons, f, indent=2, ensure_ascii=False)
        print(f"Saved persons to {persons_file}")

        await asyncio.sleep(2)

        # Collect cities
        cities = await self.get_ancient_cities(limit=2000)
        cities_file = self.output_dir / "wikidata_cities.json"
        with open(cities_file, "w", encoding="utf-8") as f:
            json.dump(cities, f, indent=2, ensure_ascii=False)
        print(f"Saved cities to {cities_file}")

        print(f"\nTotal collected:")
        print(f"  Events: {len(events)}")
        print(f"  Persons: {len(persons)}")
        print(f"  Cities: {len(cities)}")

    async def close(self):
        await self.client.aclose()


async def main():
    """Main entry point."""
    output_dir = Path("data/raw/wikidata")
    collector = WikidataCollector(output_dir)

    try:
        await collector.collect_all()
    finally:
        await collector.close()


if __name__ == "__main__":
    asyncio.run(main())
