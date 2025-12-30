"""
DBpedia SPARQL Collector

Website: https://dbpedia.org/
SPARQL Endpoint: https://dbpedia.org/sparql

Structured data extracted from Wikipedia.
Millions of entities with coordinates, dates, and relationships.

License: CC BY-SA 3.0
"""
import httpx
import asyncio
from pathlib import Path
import json
from typing import Optional


class DBpediaCollector:
    """
    Collector for DBpedia using SPARQL queries.

    Extracts historical events and places from Wikipedia's structured data.
    """

    SPARQL_ENDPOINT = "https://dbpedia.org/sparql"

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.client = httpx.AsyncClient(
            timeout=180.0,
            headers={
                "User-Agent": "CHALDEAS/0.1 (Historical Knowledge System)",
                "Accept": "application/sparql-results+json",
            }
        )

    async def query(self, sparql: str, retries: int = 3) -> dict:
        """Execute a SPARQL query with retries."""
        for attempt in range(retries):
            try:
                response = await self.client.post(
                    self.SPARQL_ENDPOINT,
                    data={"query": sparql, "format": "json"}
                )
                response.raise_for_status()
                return response.json()
            except Exception as e:
                print(f"  Query error (attempt {attempt + 1}/{retries}): {e}")
                if attempt < retries - 1:
                    await asyncio.sleep(5)
        return {"results": {"bindings": []}}

    async def get_historical_events(self, limit: int = 5000) -> list[dict]:
        """Get historical military conflicts and events with locations."""
        all_events = []
        seen_ids = set()

        # Query for military conflicts
        print("Querying military conflicts from DBpedia...")
        sparql = f"""
        PREFIX dbo: <http://dbpedia.org/ontology/>
        PREFIX dbp: <http://dbpedia.org/property/>
        PREFIX geo: <http://www.w3.org/2003/01/geo/wgs84_pos#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

        SELECT DISTINCT ?event ?name ?abstract ?date ?lat ?long ?place
        WHERE {{
          ?event a dbo:MilitaryConflict .
          ?event rdfs:label ?name .
          FILTER(LANG(?name) = "en")

          OPTIONAL {{ ?event dbo:abstract ?abstract . FILTER(LANG(?abstract) = "en") }}
          OPTIONAL {{ ?event dbo:date ?date }}
          OPTIONAL {{ ?event dbp:date ?date }}
          OPTIONAL {{
            ?event dbo:place ?placeEntity .
            ?placeEntity geo:lat ?lat .
            ?placeEntity geo:long ?long .
            ?placeEntity rdfs:label ?place .
            FILTER(LANG(?place) = "en")
          }}
        }}
        LIMIT {limit}
        """

        result = await self.query(sparql)
        events = self._parse_events(result, "battle", seen_ids)
        all_events.extend(events)
        print(f"  Found {len(events)} military conflicts")
        await asyncio.sleep(3)

        # Query for historical events
        print("Querying historical events from DBpedia...")
        sparql = f"""
        PREFIX dbo: <http://dbpedia.org/ontology/>
        PREFIX geo: <http://www.w3.org/2003/01/geo/wgs84_pos#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

        SELECT DISTINCT ?event ?name ?abstract ?date ?lat ?long ?place
        WHERE {{
          ?event a dbo:Event .
          ?event rdfs:label ?name .
          FILTER(LANG(?name) = "en")

          OPTIONAL {{ ?event dbo:abstract ?abstract . FILTER(LANG(?abstract) = "en") }}
          OPTIONAL {{ ?event dbo:date ?date }}
          OPTIONAL {{
            ?event dbo:place ?placeEntity .
            ?placeEntity geo:lat ?lat .
            ?placeEntity geo:long ?long .
            ?placeEntity rdfs:label ?place .
            FILTER(LANG(?place) = "en")
          }}
        }}
        LIMIT {limit}
        """

        result = await self.query(sparql)
        events = self._parse_events(result, "general", seen_ids)
        all_events.extend(events)
        print(f"  Found {len(events)} general events")
        await asyncio.sleep(3)

        # Query for natural disasters
        print("Querying natural disasters from DBpedia...")
        sparql = f"""
        PREFIX dbo: <http://dbpedia.org/ontology/>
        PREFIX geo: <http://www.w3.org/2003/01/geo/wgs84_pos#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

        SELECT DISTINCT ?event ?name ?abstract ?date ?lat ?long
        WHERE {{
          {{ ?event a dbo:Earthquake }} UNION
          {{ ?event a dbo:NaturalEvent }} UNION
          {{ ?event a dbo:Storm }}

          ?event rdfs:label ?name .
          FILTER(LANG(?name) = "en")

          OPTIONAL {{ ?event dbo:abstract ?abstract . FILTER(LANG(?abstract) = "en") }}
          OPTIONAL {{ ?event dbo:date ?date }}
          OPTIONAL {{ ?event geo:lat ?lat . ?event geo:long ?long }}
        }}
        LIMIT {limit}
        """

        result = await self.query(sparql)
        events = self._parse_events(result, "natural", seen_ids)
        all_events.extend(events)
        print(f"  Found {len(events)} natural disasters")

        print(f"\nTotal DBpedia events: {len(all_events)}")
        return all_events

    async def get_historical_places(self, limit: int = 5000) -> list[dict]:
        """Get ancient cities and historical sites."""
        all_places = []
        seen_ids = set()

        # Query for ancient cities
        print("Querying historical places from DBpedia...")
        sparql = f"""
        PREFIX dbo: <http://dbpedia.org/ontology/>
        PREFIX geo: <http://www.w3.org/2003/01/geo/wgs84_pos#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

        SELECT DISTINCT ?place ?name ?abstract ?lat ?long ?country
        WHERE {{
          {{ ?place a dbo:HistoricPlace }} UNION
          {{ ?place a dbo:WorldHeritageSite }} UNION
          {{ ?place a dbo:ArchaeologicalSite }}

          ?place rdfs:label ?name .
          ?place geo:lat ?lat .
          ?place geo:long ?long .
          FILTER(LANG(?name) = "en")

          OPTIONAL {{ ?place dbo:abstract ?abstract . FILTER(LANG(?abstract) = "en") }}
          OPTIONAL {{ ?place dbo:country ?countryEntity . ?countryEntity rdfs:label ?country . FILTER(LANG(?country) = "en") }}
        }}
        LIMIT {limit}
        """

        result = await self.query(sparql)
        places = self._parse_places(result, seen_ids)
        all_places.extend(places)
        print(f"  Found {len(places)} historical places")

        print(f"\nTotal DBpedia places: {len(all_places)}")
        return all_places

    async def get_historical_persons(self, limit: int = 3000) -> list[dict]:
        """Get historical figures with birth/death places."""
        all_persons = []
        seen_ids = set()

        # Query for monarchs and rulers
        print("Querying historical persons from DBpedia...")
        sparql = f"""
        PREFIX dbo: <http://dbpedia.org/ontology/>
        PREFIX geo: <http://www.w3.org/2003/01/geo/wgs84_pos#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

        SELECT DISTINCT ?person ?name ?abstract ?birthDate ?deathDate
                        ?birthLat ?birthLong ?birthPlace ?deathLat ?deathLong ?deathPlace
        WHERE {{
          {{ ?person a dbo:Monarch }} UNION
          {{ ?person a dbo:Philosopher }} UNION
          {{ ?person a dbo:MilitaryPerson }}

          ?person rdfs:label ?name .
          FILTER(LANG(?name) = "en")

          OPTIONAL {{ ?person dbo:abstract ?abstract . FILTER(LANG(?abstract) = "en") }}
          OPTIONAL {{ ?person dbo:birthDate ?birthDate }}
          OPTIONAL {{ ?person dbo:deathDate ?deathDate }}
          OPTIONAL {{
            ?person dbo:birthPlace ?bp .
            ?bp geo:lat ?birthLat .
            ?bp geo:long ?birthLong .
            ?bp rdfs:label ?birthPlace .
            FILTER(LANG(?birthPlace) = "en")
          }}
          OPTIONAL {{
            ?person dbo:deathPlace ?dp .
            ?dp geo:lat ?deathLat .
            ?dp geo:long ?deathLong .
            ?dp rdfs:label ?deathPlace .
            FILTER(LANG(?deathPlace) = "en")
          }}
        }}
        LIMIT {limit}
        """

        result = await self.query(sparql)
        persons = self._parse_persons(result, seen_ids)
        all_persons.extend(persons)
        print(f"  Found {len(persons)} historical persons")

        print(f"\nTotal DBpedia persons: {len(all_persons)}")
        return all_persons

    def _parse_events(self, result: dict, category: str, seen_ids: set) -> list[dict]:
        """Parse SPARQL results for events."""
        events = []

        for binding in result.get("results", {}).get("bindings", []):
            event_uri = binding.get("event", {}).get("value", "")
            event_id = event_uri.split("/")[-1]

            if event_id in seen_ids:
                continue
            seen_ids.add(event_id)

            lat = binding.get("lat", {}).get("value")
            lng = binding.get("long", {}).get("value")

            coords = None
            if lat and lng:
                try:
                    coords = {"latitude": float(lat), "longitude": float(lng)}
                except:
                    pass

            events.append({
                "dbpedia_id": event_id,
                "uri": event_uri,
                "name": binding.get("name", {}).get("value"),
                "description": binding.get("abstract", {}).get("value"),
                "date": binding.get("date", {}).get("value"),
                "location": binding.get("place", {}).get("value"),
                "coordinates": coords,
                "category": category,
            })

        return events

    def _parse_places(self, result: dict, seen_ids: set) -> list[dict]:
        """Parse SPARQL results for places."""
        places = []

        for binding in result.get("results", {}).get("bindings", []):
            place_uri = binding.get("place", {}).get("value", "")
            place_id = place_uri.split("/")[-1]

            if place_id in seen_ids:
                continue
            seen_ids.add(place_id)

            lat = binding.get("lat", {}).get("value")
            lng = binding.get("long", {}).get("value")

            coords = None
            if lat and lng:
                try:
                    coords = {"latitude": float(lat), "longitude": float(lng)}
                except:
                    pass

            if not coords:
                continue

            places.append({
                "dbpedia_id": place_id,
                "uri": place_uri,
                "name": binding.get("name", {}).get("value"),
                "description": binding.get("abstract", {}).get("value"),
                "coordinates": coords,
                "country": binding.get("country", {}).get("value"),
            })

        return places

    def _parse_persons(self, result: dict, seen_ids: set) -> list[dict]:
        """Parse SPARQL results for persons."""
        persons = []

        for binding in result.get("results", {}).get("bindings", []):
            person_uri = binding.get("person", {}).get("value", "")
            person_id = person_uri.split("/")[-1]

            if person_id in seen_ids:
                continue
            seen_ids.add(person_id)

            birth_lat = binding.get("birthLat", {}).get("value")
            birth_lng = binding.get("birthLong", {}).get("value")
            death_lat = binding.get("deathLat", {}).get("value")
            death_lng = binding.get("deathLong", {}).get("value")

            birth_coords = None
            if birth_lat and birth_lng:
                try:
                    birth_coords = {"latitude": float(birth_lat), "longitude": float(birth_lng)}
                except:
                    pass

            death_coords = None
            if death_lat and death_lng:
                try:
                    death_coords = {"latitude": float(death_lat), "longitude": float(death_lng)}
                except:
                    pass

            persons.append({
                "dbpedia_id": person_id,
                "uri": person_uri,
                "name": binding.get("name", {}).get("value"),
                "description": binding.get("abstract", {}).get("value"),
                "birth_date": binding.get("birthDate", {}).get("value"),
                "death_date": binding.get("deathDate", {}).get("value"),
                "birth_place": binding.get("birthPlace", {}).get("value"),
                "birth_coordinates": birth_coords,
                "death_place": binding.get("deathPlace", {}).get("value"),
                "death_coordinates": death_coords,
            })

        return persons

    async def collect_all(self):
        """Collect all historical data from DBpedia."""
        print("\n" + "=" * 60)
        print("Collecting from DBpedia")
        print("=" * 60)

        # Collect events
        events = await self.get_historical_events(limit=5000)
        events_file = self.output_dir / "dbpedia_events.json"
        with open(events_file, "w", encoding="utf-8") as f:
            json.dump(events, f, indent=2, ensure_ascii=False)
        print(f"Saved events to {events_file}")

        await asyncio.sleep(5)

        # Collect places
        places = await self.get_historical_places(limit=5000)
        places_file = self.output_dir / "dbpedia_places.json"
        with open(places_file, "w", encoding="utf-8") as f:
            json.dump(places, f, indent=2, ensure_ascii=False)
        print(f"Saved places to {places_file}")

        await asyncio.sleep(5)

        # Collect persons
        persons = await self.get_historical_persons(limit=3000)
        persons_file = self.output_dir / "dbpedia_persons.json"
        with open(persons_file, "w", encoding="utf-8") as f:
            json.dump(persons, f, indent=2, ensure_ascii=False)
        print(f"Saved persons to {persons_file}")

        print(f"\n" + "=" * 60)
        print(f"DBpedia Collection Summary:")
        print(f"  Events: {len(events)}")
        print(f"  Places: {len(places)}")
        print(f"  Persons: {len(persons)}")
        print(f"  Total: {len(events) + len(places) + len(persons)}")
        print("=" * 60)

    async def close(self):
        await self.client.aclose()


async def main():
    """Main entry point."""
    output_dir = Path("data/raw/dbpedia")
    collector = DBpediaCollector(output_dir)

    try:
        await collector.collect_all()
    finally:
        await collector.close()


if __name__ == "__main__":
    asyncio.run(main())
