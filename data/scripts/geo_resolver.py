"""
GeoResolver - Location Resolution System

Resolves locations for historical events and persons that lack coordinates.

Strategy:
1. Direct lookup in Pleiades (ancient places)
2. Wikidata SPARQL query
3. World Historical Gazetteer API
4. Fallback to country/region centroid

Sources:
- Pleiades: https://pleiades.stoa.org/
- Wikidata: https://www.wikidata.org/
- World Historical Gazetteer: https://whgazetteer.org/
"""
import httpx
import asyncio
from pathlib import Path
import json
from typing import Optional
from dataclasses import dataclass
import re


@dataclass
class ResolvedLocation:
    """Result of location resolution."""
    name: str
    latitude: float
    longitude: float
    source: str  # pleiades, wikidata, whg, centroid
    confidence: float  # 0.0 - 1.0
    pleiades_id: Optional[str] = None
    wikidata_id: Optional[str] = None
    modern_name: Optional[str] = None


class GeoResolver:
    """
    Resolves location names to coordinates using multiple sources.
    """

    WIKIDATA_ENDPOINT = "https://query.wikidata.org/sparql"
    WHG_API = "https://whgazetteer.org/api/index/"

    def __init__(self, pleiades_data_path: Optional[Path] = None):
        self.client = httpx.AsyncClient(
            timeout=30.0,
            headers={"User-Agent": "CHALDEAS/0.1"}
        )

        # Load Pleiades data if available
        self.pleiades_index = {}
        if pleiades_data_path and pleiades_data_path.exists():
            self._load_pleiades(pleiades_data_path)

        # Country centroids for fallback
        self.country_centroids = {
            "Greece": (39.0742, 21.8243),
            "Italy": (41.8719, 12.5674),
            "Egypt": (26.8206, 30.8025),
            "Turkey": (38.9637, 35.2433),
            "Iran": (32.4279, 53.6880),
            "Iraq": (33.2232, 43.6793),
            "China": (35.8617, 104.1954),
            "India": (20.5937, 78.9629),
            "France": (46.2276, 2.2137),
            "Germany": (51.1657, 10.4515),
            "United Kingdom": (55.3781, -3.4360),
            "Spain": (40.4637, -3.7492),
            "Russia": (61.5240, 105.3188),
            "Japan": (36.2048, 138.2529),
        }

        # Ancient region mappings
        self.ancient_regions = {
            "attica": ("Greece", (37.9, 23.7)),
            "laconia": ("Greece", (36.9, 22.4)),
            "boeotia": ("Greece", (38.4, 23.1)),
            "ionia": ("Turkey", (38.0, 27.0)),
            "persia": ("Iran", (32.0, 53.0)),
            "mesopotamia": ("Iraq", (33.0, 44.0)),
            "judea": ("Israel", (31.5, 35.0)),
            "gallia": ("France", (46.0, 2.0)),
            "britannia": ("United Kingdom", (52.0, -1.0)),
            "aegyptus": ("Egypt", (26.0, 30.0)),
            "asia minor": ("Turkey", (39.0, 32.0)),
            "macedonia": ("Greece", (40.5, 22.0)),
            "thrace": ("Greece", (41.0, 25.0)),
        }

    def _load_pleiades(self, path: Path):
        """Load Pleiades data into memory index."""
        print(f"Loading Pleiades data from {path}...")
        with open(path, "r", encoding="utf-8") as f:
            locations = json.load(f)

        for loc in locations:
            # Index by various names
            title = loc.get("title", "").lower()
            if title and loc.get("coordinates"):
                self.pleiades_index[title] = loc

            for name_entry in loc.get("names", []):
                name = name_entry.get("name", "").lower()
                if name and loc.get("coordinates"):
                    self.pleiades_index[name] = loc

        print(f"Indexed {len(self.pleiades_index)} Pleiades entries")

    async def resolve(self, location_name: str, context: dict = None) -> Optional[ResolvedLocation]:
        """
        Resolve a location name to coordinates.

        Args:
            location_name: The place name to resolve
            context: Optional context (time period, region, etc.)

        Returns:
            ResolvedLocation or None if not found
        """
        if not location_name:
            return None

        name_lower = location_name.lower().strip()

        # 1. Try Pleiades first (best for ancient places)
        result = self._resolve_pleiades(name_lower)
        if result:
            return result

        # 2. Try Wikidata
        result = await self._resolve_wikidata(location_name)
        if result:
            return result

        # 3. Try World Historical Gazetteer
        result = await self._resolve_whg(location_name)
        if result:
            return result

        # 4. Try ancient region mappings
        result = self._resolve_ancient_region(name_lower)
        if result:
            return result

        # 5. Fallback to country centroid if country context given
        if context and context.get("country"):
            result = self._resolve_country_centroid(context["country"])
            if result:
                return result

        return None

    def _resolve_pleiades(self, name: str) -> Optional[ResolvedLocation]:
        """Lookup in Pleiades index."""
        if name in self.pleiades_index:
            loc = self.pleiades_index[name]
            coords = loc["coordinates"]
            return ResolvedLocation(
                name=loc["title"],
                latitude=coords["latitude"],
                longitude=coords["longitude"],
                source="pleiades",
                confidence=0.95,
                pleiades_id=loc.get("pleiades_id"),
            )
        return None

    async def _resolve_wikidata(self, name: str) -> Optional[ResolvedLocation]:
        """Query Wikidata for location."""
        sparql = f"""
        SELECT ?place ?placeLabel ?coord WHERE {{
          ?place rdfs:label "{name}"@en.
          ?place wdt:P625 ?coord.
          SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
        }}
        LIMIT 1
        """

        try:
            response = await self.client.get(
                self.WIKIDATA_ENDPOINT,
                params={"query": sparql, "format": "json"}
            )
            response.raise_for_status()
            data = response.json()

            bindings = data.get("results", {}).get("bindings", [])
            if bindings:
                binding = bindings[0]
                coord_str = binding.get("coord", {}).get("value", "")

                # Parse Point(lon lat)
                match = re.search(r"Point\(([-\d.]+)\s+([-\d.]+)\)", coord_str)
                if match:
                    lon, lat = float(match.group(1)), float(match.group(2))
                    wikidata_id = binding.get("place", {}).get("value", "").split("/")[-1]

                    return ResolvedLocation(
                        name=binding.get("placeLabel", {}).get("value", name),
                        latitude=lat,
                        longitude=lon,
                        source="wikidata",
                        confidence=0.9,
                        wikidata_id=wikidata_id,
                    )
        except Exception as e:
            print(f"Wikidata query failed for '{name}': {e}")

        return None

    async def _resolve_whg(self, name: str) -> Optional[ResolvedLocation]:
        """Query World Historical Gazetteer."""
        try:
            response = await self.client.get(
                self.WHG_API,
                params={"name": name}
            )
            response.raise_for_status()
            data = response.json()

            features = data.get("features", [])
            if features:
                feature = features[0]
                geometry = feature.get("geometry", {})
                coords = geometry.get("coordinates", [])

                if coords and len(coords) >= 2:
                    lon, lat = coords[0], coords[1]
                    props = feature.get("properties", {})

                    return ResolvedLocation(
                        name=props.get("title", name),
                        latitude=lat,
                        longitude=lon,
                        source="whg",
                        confidence=0.85,
                    )
        except Exception as e:
            print(f"WHG query failed for '{name}': {e}")

        return None

    def _resolve_ancient_region(self, name: str) -> Optional[ResolvedLocation]:
        """Resolve ancient region names."""
        if name in self.ancient_regions:
            country, (lat, lon) = self.ancient_regions[name]
            return ResolvedLocation(
                name=name.title(),
                latitude=lat,
                longitude=lon,
                source="region_mapping",
                confidence=0.6,
                modern_name=country,
            )
        return None

    def _resolve_country_centroid(self, country: str) -> Optional[ResolvedLocation]:
        """Get country centroid as fallback."""
        if country in self.country_centroids:
            lat, lon = self.country_centroids[country]
            return ResolvedLocation(
                name=country,
                latitude=lat,
                longitude=lon,
                source="centroid",
                confidence=0.3,
            )
        return None

    async def resolve_batch(self, locations: list[str], context: dict = None) -> dict[str, ResolvedLocation]:
        """Resolve multiple locations."""
        results = {}

        for loc in locations:
            result = await self.resolve(loc, context)
            if result:
                results[loc] = result

            # Rate limiting
            await asyncio.sleep(0.5)

        return results

    async def close(self):
        await self.client.aclose()


async def main():
    """Test the resolver."""
    resolver = GeoResolver()

    test_locations = [
        "Athens",
        "Marathon",
        "Rome",
        "Babylon",
        "Alexandria",
        "Thermopylae",
        "Persepolis",
    ]

    print("Testing GeoResolver...")
    print("=" * 60)

    for loc in test_locations:
        result = await resolver.resolve(loc)
        if result:
            print(f"\n{loc}:")
            print(f"  Coordinates: ({result.latitude}, {result.longitude})")
            print(f"  Source: {result.source}")
            print(f"  Confidence: {result.confidence}")
        else:
            print(f"\n{loc}: NOT FOUND")

        await asyncio.sleep(1)

    await resolver.close()


if __name__ == "__main__":
    asyncio.run(main())
