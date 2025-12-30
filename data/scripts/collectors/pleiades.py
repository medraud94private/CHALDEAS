"""
Pleiades Gazetteer Collector

Website: https://pleiades.stoa.org/
Data: https://pleiades.stoa.org/downloads

The premier gazetteer for ancient world places.
34,000+ places with coordinates, names, and connections.

License: CC BY 3.0 (free to use with attribution)
"""
import httpx
import asyncio
from pathlib import Path
import json
import zipfile
from io import BytesIO


class PleiadesCollector:
    """
    Collector for Pleiades Gazetteer.

    Downloads the complete dataset and extracts location information.
    """

    # Latest JSON dump URL
    JSON_DUMP_URL = "https://atlantides.org/downloads/pleiades/json/pleiades-places-latest.json.gz"
    CSV_DUMP_URL = "https://atlantides.org/downloads/pleiades/dumps/pleiades-places-latest.csv.gz"

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.client = httpx.AsyncClient(timeout=120.0, follow_redirects=True)

    async def download_json_dump(self) -> dict:
        """Download the complete Pleiades JSON dump."""
        import gzip

        print("Downloading Pleiades JSON dump (~50MB)...")
        print(f"URL: {self.JSON_DUMP_URL}")

        response = await self.client.get(self.JSON_DUMP_URL)
        response.raise_for_status()

        # Decompress gzip
        data = gzip.decompress(response.content)
        places = json.loads(data)

        print(f"Downloaded {len(places.get('@graph', []))} places")

        # Save raw dump
        dump_path = self.output_dir / "pleiades_raw.json"
        with open(dump_path, "w", encoding="utf-8") as f:
            json.dump(places, f, indent=2)

        return places

    def extract_locations(self, places_data: dict) -> list[dict]:
        """Extract location data from Pleiades dump."""
        locations = []

        graph = places_data.get("@graph", [])

        for place in graph:
            # Pleiades uses type=FeatureCollection for places
            if place.get("type") not in ("FeatureCollection", "Place"):
                # Also check @type for older format
                if place.get("@type") != "Place":
                    continue

            # Extract coordinates from reprPoint or features
            coords = None
            repr_point = place.get("reprPoint")
            if repr_point and len(repr_point) >= 2:
                # reprPoint is [longitude, latitude]
                lon, lat = repr_point[0], repr_point[1]
                coords = {"latitude": lat, "longitude": lon}

            # Try features if no reprPoint
            if not coords:
                features = place.get("features", [])
                for feat in features:
                    geom = feat.get("geometry")
                    if geom and geom.get("type") == "Point":
                        coord_list = geom.get("coordinates", [])
                        if len(coord_list) >= 2:
                            lon, lat = coord_list[0], coord_list[1]
                            coords = {"latitude": lat, "longitude": lon}
                            break

            if not coords:
                continue

            # Get ID from id field or @id field
            pleiades_id = str(place.get("id", "")) or place.get("@id", "").split("/")[-1]
            uri = place.get("uri") or place.get("@id")

            location = {
                "pleiades_id": pleiades_id,
                "uri": uri,
                "title": place.get("title"),
                "description": place.get("description"),
                "names": [],
                "coordinates": coords,
                "place_types": place.get("placeTypes", []),
                "time_periods": [],
                "connections": [],
            }

            # Extract names
            for name in place.get("names", []):
                if isinstance(name, dict):
                    location["names"].append({
                        "name": name.get("romanized") or name.get("attested"),
                        "language": name.get("language"),
                        "time_periods": name.get("attestations", []),
                    })

            # Extract time periods
            for attestation in place.get("attestations", []):
                if isinstance(attestation, dict):
                    location["time_periods"].append({
                        "period": attestation.get("timePeriod"),
                        "confidence": attestation.get("confidence"),
                    })

            # Extract connections to other places
            connections = place.get("connectsWith", []) or place.get("connections", [])
            for conn in connections:
                if isinstance(conn, str):
                    location["connections"].append(conn.split("/")[-1])

            locations.append(location)

        return locations

    async def collect_all(self):
        """Collect all Pleiades data."""
        print("\n" + "=" * 60)
        print("Collecting from Pleiades Gazetteer")
        print("=" * 60)

        # Download JSON dump
        places_data = await self.download_json_dump()

        # Extract locations
        print("Extracting location data...")
        locations = self.extract_locations(places_data)

        # Save extracted locations
        output_file = self.output_dir / "pleiades_locations.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(locations, f, indent=2, ensure_ascii=False)

        print(f"Extracted {len(locations)} locations with coordinates")
        print(f"Saved to {output_file}")

        # Create summary statistics
        stats = self._generate_stats(locations)
        stats_file = self.output_dir / "pleiades_stats.json"
        with open(stats_file, "w", encoding="utf-8") as f:
            json.dump(stats, f, indent=2)

        print(f"\nStatistics:")
        print(f"  Total places: {stats['total']}")
        print(f"  With coordinates: {stats['with_coords']}")
        print(f"  Place types: {len(stats['place_types'])}")

        return locations

    def _generate_stats(self, locations: list[dict]) -> dict:
        """Generate statistics about the collected data."""
        place_types = {}
        for loc in locations:
            for pt in loc.get("place_types", []):
                place_types[pt] = place_types.get(pt, 0) + 1

        return {
            "total": len(locations),
            "with_coords": sum(1 for l in locations if l.get("coordinates")),
            "place_types": place_types,
        }

    async def close(self):
        await self.client.aclose()


# Important ancient places to prioritize
IMPORTANT_PLACES = [
    "athens",
    "rome",
    "sparta",
    "thebes",
    "corinth",
    "alexandria",
    "carthage",
    "babylon",
    "persepolis",
    "marathon",
    "thermopylae",
    "delphi",
    "olympia",
    "troy",
    "jerusalem",
    "constantinople",
]


async def main():
    """Main entry point."""
    output_dir = Path("data/raw/pleiades")
    collector = PleiadesCollector(output_dir)

    try:
        await collector.collect_all()
    finally:
        await collector.close()


if __name__ == "__main__":
    asyncio.run(main())
