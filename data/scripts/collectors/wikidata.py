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
    - Historical events with locations and dates (battles, wars, treaties, etc.)
    - Historical figures with birth/death places
    - Ancient cities and landmarks
    """

    SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"

    # Event types to collect (Wikidata Q-codes)
    EVENT_TYPES = [
        ("Q178561", "battle"),           # battle
        ("Q198", "war"),                 # war
        ("Q131569", "treaty"),           # treaty
        ("Q3024240", "revolution"),      # revolution (historical event)
        ("Q7278", "political_event"),    # political event
        ("Q1190554", "natural_disaster"), # natural disaster (occurrence)
        ("Q8065", "natural_disaster"),   # earthquake
        ("Q8068", "natural_disaster"),   # flood
        ("Q168983", "natural_disaster"), # volcanic eruption
        ("Q625994", "political_event"),  # peace treaty
        ("Q82794", "political_event"),   # geographic region (for historical regions)
        ("Q35127", "cultural"),          # discovery
        ("Q15401930", "scientific"),     # scientific discovery
        ("Q170584", "project"),          # project (constructions like Great Wall)
        ("Q839954", "archaeological"),   # archaeological site
        ("Q5107", "general"),            # continent (for historical context)
    ]

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.client = httpx.AsyncClient(
            timeout=180.0,  # Increased timeout
            headers={
                "User-Agent": "CHALDEAS/0.1 (Historical Knowledge System)",
                "Accept": "application/json",
            }
        )

    async def query(self, sparql: str, retries: int = 3) -> dict:
        """Execute a SPARQL query with retries."""
        for attempt in range(retries):
            try:
                response = await self.client.get(
                    self.SPARQL_ENDPOINT,
                    params={"query": sparql, "format": "json"}
                )
                response.raise_for_status()
                return response.json()
            except Exception as e:
                print(f"  Query error (attempt {attempt + 1}/{retries}): {e}")
                if attempt < retries - 1:
                    await asyncio.sleep(5)  # Wait before retry
        return {"results": {"bindings": []}}

    async def get_historical_events(self, limit_per_type: int = 3000) -> list[dict]:
        """
        Get historical events with locations.

        Queries for multiple event types: battles, wars, treaties, etc.
        """
        all_events = []
        seen_ids = set()

        # Collect battles
        print("Querying battles...")
        sparql = f"""
        SELECT DISTINCT ?event ?eventLabel ?eventDescription
               ?date ?coord ?countryLabel
        WHERE {{
          ?event wdt:P31 wd:Q178561.  # instance of battle
          ?event wdt:P625 ?coord.      # has coordinates

          OPTIONAL {{ ?event wdt:P585 ?date. }}
          OPTIONAL {{ ?event wdt:P17 ?country. }}

          SERVICE wikibase:label {{
            bd:serviceParam wikibase:language "en".
          }}
        }}
        LIMIT {limit_per_type}
        """
        result = await self.query(sparql)
        events = self._parse_events(result, "battle", seen_ids)
        all_events.extend(events)
        print(f"  Found {len(events)} battles")
        await asyncio.sleep(2)

        # Collect wars
        print("Querying wars...")
        sparql = f"""
        SELECT DISTINCT ?event ?eventLabel ?eventDescription
               ?date ?coord ?countryLabel
        WHERE {{
          ?event wdt:P31 wd:Q198.  # instance of war
          OPTIONAL {{ ?event wdt:P625 ?coord. }}
          OPTIONAL {{ ?event wdt:P276 ?location. ?location wdt:P625 ?coord. }}

          OPTIONAL {{ ?event wdt:P580 ?date. }}  # start date
          OPTIONAL {{ ?event wdt:P585 ?date. }}  # point in time
          OPTIONAL {{ ?event wdt:P17 ?country. }}

          SERVICE wikibase:label {{
            bd:serviceParam wikibase:language "en".
          }}
        }}
        LIMIT {limit_per_type}
        """
        result = await self.query(sparql)
        events = self._parse_events(result, "war", seen_ids)
        all_events.extend(events)
        print(f"  Found {len(events)} wars")
        await asyncio.sleep(2)

        # Collect treaties
        print("Querying treaties...")
        sparql = f"""
        SELECT DISTINCT ?event ?eventLabel ?eventDescription
               ?date ?coord ?countryLabel
        WHERE {{
          ?event wdt:P31 wd:Q131569.  # instance of treaty
          OPTIONAL {{ ?event wdt:P625 ?coord. }}
          OPTIONAL {{ ?event wdt:P276 ?location. ?location wdt:P625 ?coord. }}

          OPTIONAL {{ ?event wdt:P585 ?date. }}
          OPTIONAL {{ ?event wdt:P571 ?date. }}  # inception
          OPTIONAL {{ ?event wdt:P17 ?country. }}

          SERVICE wikibase:label {{
            bd:serviceParam wikibase:language "en".
          }}
        }}
        LIMIT {limit_per_type}
        """
        result = await self.query(sparql)
        events = self._parse_events(result, "political", seen_ids)
        all_events.extend(events)
        print(f"  Found {len(events)} treaties")
        await asyncio.sleep(2)

        # Collect revolutions
        print("Querying revolutions...")
        sparql = f"""
        SELECT DISTINCT ?event ?eventLabel ?eventDescription
               ?date ?coord ?countryLabel
        WHERE {{
          ?event wdt:P31 wd:Q10931.  # revolution
          OPTIONAL {{ ?event wdt:P625 ?coord. }}
          OPTIONAL {{ ?event wdt:P276 ?location. ?location wdt:P625 ?coord. }}

          OPTIONAL {{ ?event wdt:P580 ?date. }}
          OPTIONAL {{ ?event wdt:P585 ?date. }}
          OPTIONAL {{ ?event wdt:P17 ?country. }}

          SERVICE wikibase:label {{
            bd:serviceParam wikibase:language "en".
          }}
        }}
        LIMIT {limit_per_type}
        """
        result = await self.query(sparql)
        events = self._parse_events(result, "political", seen_ids)
        all_events.extend(events)
        print(f"  Found {len(events)} revolutions")
        await asyncio.sleep(2)

        # Collect natural disasters (earthquakes)
        print("Querying earthquakes...")
        sparql = f"""
        SELECT DISTINCT ?event ?eventLabel ?eventDescription
               ?date ?coord ?countryLabel
        WHERE {{
          ?event wdt:P31 wd:Q7944.  # earthquake
          ?event wdt:P625 ?coord.

          OPTIONAL {{ ?event wdt:P585 ?date. }}
          OPTIONAL {{ ?event wdt:P17 ?country. }}

          SERVICE wikibase:label {{
            bd:serviceParam wikibase:language "en".
          }}
        }}
        LIMIT {limit_per_type}
        """
        result = await self.query(sparql)
        events = self._parse_events(result, "natural", seen_ids)
        all_events.extend(events)
        print(f"  Found {len(events)} earthquakes")
        await asyncio.sleep(2)

        # Collect volcanic eruptions
        print("Querying volcanic eruptions...")
        sparql = f"""
        SELECT DISTINCT ?event ?eventLabel ?eventDescription
               ?date ?coord ?countryLabel
        WHERE {{
          ?event wdt:P31 wd:Q168983.  # volcanic eruption
          OPTIONAL {{ ?event wdt:P625 ?coord. }}
          OPTIONAL {{ ?event wdt:P276 ?location. ?location wdt:P625 ?coord. }}

          OPTIONAL {{ ?event wdt:P585 ?date. }}
          OPTIONAL {{ ?event wdt:P17 ?country. }}

          SERVICE wikibase:label {{
            bd:serviceParam wikibase:language "en".
          }}
        }}
        LIMIT {limit_per_type}
        """
        result = await self.query(sparql)
        events = self._parse_events(result, "natural", seen_ids)
        all_events.extend(events)
        print(f"  Found {len(events)} volcanic eruptions")
        await asyncio.sleep(2)

        # Collect sieges
        print("Querying sieges...")
        sparql = f"""
        SELECT DISTINCT ?event ?eventLabel ?eventDescription
               ?date ?coord ?countryLabel
        WHERE {{
          ?event wdt:P31 wd:Q188055.  # siege
          OPTIONAL {{ ?event wdt:P625 ?coord. }}
          OPTIONAL {{ ?event wdt:P276 ?location. ?location wdt:P625 ?coord. }}

          OPTIONAL {{ ?event wdt:P585 ?date. }}
          OPTIONAL {{ ?event wdt:P17 ?country. }}

          SERVICE wikibase:label {{
            bd:serviceParam wikibase:language "en".
          }}
        }}
        LIMIT {limit_per_type}
        """
        result = await self.query(sparql)
        events = self._parse_events(result, "battle", seen_ids)
        all_events.extend(events)
        print(f"  Found {len(events)} sieges")
        await asyncio.sleep(2)

        # Collect coronations
        print("Querying coronations...")
        sparql = f"""
        SELECT DISTINCT ?event ?eventLabel ?eventDescription
               ?date ?coord ?countryLabel
        WHERE {{
          ?event wdt:P31 wd:Q319652.  # coronation
          OPTIONAL {{ ?event wdt:P625 ?coord. }}
          OPTIONAL {{ ?event wdt:P276 ?location. ?location wdt:P625 ?coord. }}

          OPTIONAL {{ ?event wdt:P585 ?date. }}
          OPTIONAL {{ ?event wdt:P17 ?country. }}

          SERVICE wikibase:label {{
            bd:serviceParam wikibase:language "en".
          }}
        }}
        LIMIT {limit_per_type}
        """
        result = await self.query(sparql)
        events = self._parse_events(result, "political", seen_ids)
        all_events.extend(events)
        print(f"  Found {len(events)} coronations")

        print(f"\nTotal events collected: {len(all_events)}")
        return all_events

    async def get_historical_figures(self, limit_per_query: int = 2000) -> list[dict]:
        """
        Get historical figures by occupation type.
        Uses targeted queries by profession to avoid timeout.
        """
        all_persons = []
        seen_ids = set()

        # Occupation types to query (Q-codes)
        occupations = [
            ("Q116", "monarch", 3000),           # monarch/king/queen
            ("Q36180", "writer", 2000),          # writer
            ("Q4964182", "philosopher", 2000),   # philosopher
            ("Q593644", "military_commander", 2000),  # military commander
            ("Q82955", "politician", 2000),      # politician
            ("Q901", "scientist", 2000),         # scientist
            ("Q1930187", "explorer", 1500),      # explorer
            ("Q36834", "composer", 1500),        # composer
            ("Q1028181", "painter", 1500),       # painter
            ("Q3621491", "emperor", 1500),       # emperor
            ("Q10873124", "religious_leader", 1000),  # religious leader
            ("Q170790", "mathematician", 1000),   # mathematician
            ("Q15980158", "inventor", 1000),     # inventor
        ]

        for qcode, occupation_name, limit in occupations:
            print(f"Querying {occupation_name}s...")
            sparql = f"""
            SELECT DISTINCT ?person ?personLabel ?personDescription
                   ?birthDate ?deathDate ?birthCoord ?deathCoord
                   ?occupationLabel ?birthPlaceLabel ?deathPlaceLabel
            WHERE {{
              ?person wdt:P31 wd:Q5.
              ?person wdt:P106 wd:{qcode}.

              OPTIONAL {{ ?person wdt:P569 ?birthDate. }}
              OPTIONAL {{ ?person wdt:P570 ?deathDate. }}
              OPTIONAL {{ ?person wdt:P19 ?birthPlace. ?birthPlace wdt:P625 ?birthCoord. }}
              OPTIONAL {{ ?person wdt:P20 ?deathPlace. ?deathPlace wdt:P625 ?deathCoord. }}
              OPTIONAL {{ ?person wdt:P106 ?occupation. }}

              SERVICE wikibase:label {{
                bd:serviceParam wikibase:language "en".
              }}
            }}
            LIMIT {limit}
            """
            result = await self.query(sparql)
            persons = self._parse_persons(result, seen_ids)
            all_persons.extend(persons)
            print(f"  Found {len(persons)} {occupation_name}s")
            await asyncio.sleep(3)  # Rate limiting

        print(f"\nTotal persons collected: {len(all_persons)}")
        return all_persons

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

    def _parse_events(self, result: dict, category: str = "general", seen_ids: set = None) -> list[dict]:
        """Parse SPARQL results for events."""
        events = []
        if seen_ids is None:
            seen_ids = set()

        for binding in result.get("results", {}).get("bindings", []):
            event_id = binding.get("event", {}).get("value", "").split("/")[-1]

            if event_id in seen_ids:
                continue
            seen_ids.add(event_id)

            coord = self._parse_coords(
                binding.get("coord", {}).get("value")
            )

            events.append({
                "wikidata_id": event_id,
                "name": binding.get("eventLabel", {}).get("value"),
                "description": binding.get("eventDescription", {}).get("value"),
                "date": binding.get("date", {}).get("value"),
                "location": None,
                "country": binding.get("countryLabel", {}).get("value"),
                "coordinates": coord,
                "category": category,
            })

        return events

    def _parse_persons(self, result: dict, seen_ids: set = None) -> list[dict]:
        """Parse SPARQL results for persons."""
        persons = []
        if seen_ids is None:
            seen_ids = set()

        for binding in result.get("results", {}).get("bindings", []):
            person_id = binding.get("person", {}).get("value", "").split("/")[-1]

            if person_id in seen_ids:
                continue
            seen_ids.add(person_id)

            birth_coord = self._parse_coords(
                binding.get("birthCoord", {}).get("value")
            )
            death_coord = self._parse_coords(
                binding.get("deathCoord", {}).get("value")
            )

            persons.append({
                "wikidata_id": person_id,
                "name": binding.get("personLabel", {}).get("value"),
                "description": binding.get("personDescription", {}).get("value"),
                "birth_date": binding.get("birthDate", {}).get("value"),
                "death_date": binding.get("deathDate", {}).get("value"),
                "birth_place": binding.get("birthPlaceLabel", {}).get("value"),
                "birth_coordinates": birth_coord,
                "death_place": binding.get("deathPlaceLabel", {}).get("value"),
                "death_coordinates": death_coord,
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
        print("Collecting from Wikidata (Extended)")
        print("=" * 60)

        # Collect events (multiple types)
        events = await self.get_historical_events(limit_per_type=5000)
        events_file = self.output_dir / "wikidata_events.json"
        with open(events_file, "w", encoding="utf-8") as f:
            json.dump(events, f, indent=2, ensure_ascii=False)
        print(f"Saved events to {events_file}")

        await asyncio.sleep(5)  # Rate limiting

        # Collect persons (multiple time periods)
        persons = await self.get_historical_figures(limit_per_query=5000)
        persons_file = self.output_dir / "wikidata_persons.json"
        with open(persons_file, "w", encoding="utf-8") as f:
            json.dump(persons, f, indent=2, ensure_ascii=False)
        print(f"Saved persons to {persons_file}")

        await asyncio.sleep(5)

        # Collect cities
        cities = await self.get_ancient_cities(limit=5000)
        cities_file = self.output_dir / "wikidata_cities.json"
        with open(cities_file, "w", encoding="utf-8") as f:
            json.dump(cities, f, indent=2, ensure_ascii=False)
        print(f"Saved cities to {cities_file}")

        print(f"\n" + "=" * 60)
        print(f"Collection Summary:")
        print(f"  Events: {len(events)}")
        print(f"  Persons: {len(persons)}")
        print(f"  Cities: {len(cities)}")
        print(f"  Total: {len(events) + len(persons) + len(cities)}")
        print("=" * 60)

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
