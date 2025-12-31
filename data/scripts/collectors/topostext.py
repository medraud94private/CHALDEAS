"""
ToposText Collector

Website: https://topostext.org/
Data: Gazetteer available as GeoJSON/KML

Contains:
- 860+ Greek and Latin classical texts (translated)
- 8,000+ ancient places with coordinates
- 21,000+ proper names (people, places, etc.)

License: Creative Commons (educational use)
"""
import httpx
import asyncio
from pathlib import Path
import json
from typing import Optional


class ToposTextCollector:
    """
    Collector for ToposText gazetteer and place data.

    ToposText provides excellent geographic data for the ancient world.
    """

    # Gazetteer downloads (updated 2025)
    GEOJSON_URL = "https://topostext.org/downloads/ToposText_places_2025-11-20.geojson"
    JSONLD_URL = "https://topostext.org/downloads/ToposTextGazetteer.jsonld"
    KML_URL = "https://topostext.org/downloads/ToposText_Ancient_PlacesbyRegions2025-11-14.kmz"

    # API endpoints (if available)
    BASE_URL = "https://topostext.org"

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.client = httpx.AsyncClient(
            timeout=120.0,
            follow_redirects=True,
            headers={
                "User-Agent": "CHALDEAS/0.1 (Historical Knowledge System; Educational Research)"
            }
        )

    async def download_gazetteer_geojson(self) -> Optional[dict]:
        """Download the ToposText gazetteer in GeoJSON format."""
        print("Downloading ToposText gazetteer (GeoJSON)...")

        try:
            response = await self.client.get(self.GEOJSON_URL)
            response.raise_for_status()

            data = response.json()

            # Save raw GeoJSON
            output_file = self.output_dir / "topostext_places.geojson"
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            # Extract and save as simplified JSON
            if "features" in data:
                places = []
                for feature in data["features"]:
                    props = feature.get("properties", {})
                    geom = feature.get("geometry", {})
                    coords = geom.get("coordinates", [None, None])

                    places.append({
                        "id": props.get("id"),
                        "name": props.get("name"),
                        "name_greek": props.get("nameGreek"),
                        "name_latin": props.get("nameLatin"),
                        "type": props.get("featureType"),
                        "description": props.get("description"),
                        "time_periods": props.get("timePeriods"),
                        "longitude": coords[0] if len(coords) > 0 else None,
                        "latitude": coords[1] if len(coords) > 1 else None,
                        "source": "topostext",
                    })

                # Save simplified version
                simplified_file = self.output_dir / "topostext_places.json"
                with open(simplified_file, "w", encoding="utf-8") as f:
                    json.dump(places, f, indent=2, ensure_ascii=False)

                print(f"Saved {len(places)} places")
                return data

        except Exception as e:
            print(f"Error downloading gazetteer: {e}")
            return None

    async def download_gazetteer_jsonld(self) -> Optional[dict]:
        """Download the ToposText gazetteer in JSON-LD format (includes text citations)."""
        print("Downloading ToposText gazetteer (JSON-LD with citations)...")

        try:
            response = await self.client.get(self.JSONLD_URL)
            response.raise_for_status()

            data = response.json()

            # Save raw JSON-LD
            output_file = self.output_dir / "topostext_gazetteer.jsonld"
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            print(f"Saved JSON-LD gazetteer")
            return data

        except Exception as e:
            print(f"Error downloading JSON-LD: {e}")
            return None

    async def collect_all(self):
        """Collect all available ToposText data."""
        print("\n" + "=" * 60)
        print("Collecting from ToposText")
        print("=" * 60)

        await self.download_gazetteer_geojson()
        await self.download_gazetteer_jsonld()

        # Save collection metadata
        metadata = {
            "source": "topostext",
            "url": self.BASE_URL,
            "description": "Ancient world gazetteer with 8000+ places",
            "license": "Creative Commons with attribution",
        }

        metadata_file = self.output_dir / "topostext_metadata.json"
        with open(metadata_file, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)

        print("ToposText collection complete!")

    async def close(self):
        await self.client.aclose()


async def main():
    """Main entry point."""
    output_dir = Path("data/raw/topostext")
    collector = ToposTextCollector(output_dir)

    try:
        await collector.collect_all()
    finally:
        await collector.close()


if __name__ == "__main__":
    asyncio.run(main())
