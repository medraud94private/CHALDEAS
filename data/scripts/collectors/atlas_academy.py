"""
Atlas Academy FGO API Collector

API: https://api.atlasacademy.io/docs
Data: FGO game data (servants, craft essences, items, etc.)

Contains:
- All FGO servants with stats, skills, lore
- Multiple regions (JP, NA, CN, KR, TW)
- Regularly updated with new content

License: Open/Free API, no authentication required
"""
import httpx
import asyncio
from pathlib import Path
import json
from typing import Optional


class AtlasAcademyCollector:
    """
    Collector for Atlas Academy FGO API.

    Collects servant data, profiles, and lore from Fate/Grand Order.
    """

    BASE_URL = "https://api.atlasacademy.io"

    # Export endpoints for bulk data
    EXPORTS = {
        "servants_basic_na": "/export/NA/basic_servant.json",
        "servants_basic_jp": "/export/JP/basic_servant.json",
        "servants_na": "/export/NA/nice_servant.json",
        "servants_jp": "/export/JP/nice_servant.json",
        "craft_essences_na": "/export/NA/nice_equip.json",
        "items_na": "/export/NA/nice_item.json",
        "mystic_codes_na": "/export/NA/nice_mystic_code.json",
        "command_codes_na": "/export/NA/nice_command_code.json",
    }

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

    async def download_export(self, name: str, endpoint: str) -> Optional[dict]:
        """Download a bulk export file."""
        url = f"{self.BASE_URL}{endpoint}"
        print(f"  Downloading {name}...")

        try:
            response = await self.client.get(url)
            response.raise_for_status()

            data = response.json()

            # Save raw data
            output_file = self.output_dir / f"{name}.json"
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            count = len(data) if isinstance(data, list) else "N/A"
            print(f"    Saved {count} entries")
            return data

        except Exception as e:
            print(f"    Error: {e}")
            return None

    async def get_servant_details(self, servant_id: int, region: str = "NA") -> Optional[dict]:
        """Get detailed information for a specific servant."""
        url = f"{self.BASE_URL}/nice/{region}/servant/{servant_id}?lore=true"

        try:
            response = await self.client.get(url)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"  Error fetching servant {servant_id}: {e}")
            return None

    async def collect_servant_profiles(self, region: str = "NA", limit: int = None):
        """Collect detailed profiles with lore for all servants."""
        print(f"\nCollecting servant profiles with lore ({region})...")

        # First get basic list
        basic_url = f"{self.BASE_URL}/export/{region}/basic_servant.json"
        response = await self.client.get(basic_url)
        response.raise_for_status()
        basic_servants = response.json()

        profiles = []
        total = len(basic_servants) if limit is None else min(limit, len(basic_servants))

        for i, servant in enumerate(basic_servants[:total]):
            servant_id = servant.get("id")
            name = servant.get("name", "Unknown")

            # Safe print
            safe_name = name.encode('ascii', 'replace').decode('ascii')
            print(f"  [{i+1}/{total}] {safe_name}...")

            details = await self.get_servant_details(servant_id, region)
            if details:
                # Extract key information
                profile = {
                    "id": servant_id,
                    "name": details.get("name"),
                    "original_name": details.get("originalName"),
                    "class": details.get("className"),
                    "rarity": details.get("rarity"),
                    "gender": details.get("gender"),
                    "attribute": details.get("attribute"),
                    "traits": details.get("traits", []),
                    "profile": details.get("profile", {}),
                    "lore": self._extract_lore(details),
                }
                profiles.append(profile)

            # Rate limiting
            await asyncio.sleep(0.3)

        # Save profiles
        profiles_file = self.output_dir / f"servant_profiles_{region.lower()}.json"
        with open(profiles_file, "w", encoding="utf-8") as f:
            json.dump(profiles, f, indent=2, ensure_ascii=False)

        print(f"Saved {len(profiles)} servant profiles")
        return profiles

    def _extract_lore(self, servant_data: dict) -> dict:
        """Extract lore/biography from servant data."""
        lore = {}

        profile = servant_data.get("profile", {})
        if profile:
            # Character info
            if "cv" in profile:
                lore["voice_actor"] = profile["cv"]
            if "illustrator" in profile:
                lore["illustrator"] = profile["illustrator"]

            # Comments (biography entries)
            comments = profile.get("comments", [])
            for comment in comments:
                comment_id = comment.get("id", 0)
                comment_text = comment.get("comment", "")
                lore[f"profile_{comment_id}"] = comment_text

        return lore

    async def extract_historical_figures(self):
        """Extract list of historical/mythological figures from servant data."""
        print("\nExtracting historical figures from servants...")

        # Load servant data
        servants_file = self.output_dir / "servants_na.json"
        if not servants_file.exists():
            print("  Servant data not found, downloading first...")
            await self.download_export("servants_na", self.EXPORTS["servants_na"])

        with open(servants_file, "r", encoding="utf-8") as f:
            servants = json.load(f)

        # Extract unique historical figures
        figures = []
        seen_names = set()

        for servant in servants:
            name = servant.get("name", "")
            original_name = servant.get("originalName", name)

            # Skip duplicates and non-historical
            if name in seen_names:
                continue
            seen_names.add(name)

            # Get traits for classification
            traits = [t.get("name", "") for t in servant.get("traits", [])]

            figure = {
                "fgo_name": name,
                "original_name": original_name,
                "class": servant.get("className"),
                "rarity": servant.get("rarity"),
                "gender": servant.get("gender"),
                "attribute": servant.get("attribute"),
                "traits": traits,
                "origin": self._classify_origin(traits, name),
            }
            figures.append(figure)

        # Save historical figures list
        figures_file = self.output_dir / "fgo_historical_figures.json"
        with open(figures_file, "w", encoding="utf-8") as f:
            json.dump(figures, f, indent=2, ensure_ascii=False)

        print(f"Extracted {len(figures)} historical/mythological figures")
        return figures

    def _classify_origin(self, traits: list, name: str) -> str:
        """Classify the cultural/historical origin of a servant."""
        # Trait-based classification
        trait_origins = {
            "Greek Mythology Males": "Greek",
            "Roman": "Roman",
            "Arthurian": "Arthurian/Celtic",
            "Brynhildr's Beloved": "Norse",
            "Divine": "Divine/Mythological",
            "King": "Royalty",
            "Dragon": "Mythological",
            "Japanese Servants": "Japanese",
        }

        for trait in traits:
            for trait_key, origin in trait_origins.items():
                if trait_key.lower() in trait.lower():
                    return origin

        return "Historical"

    async def collect_all(self):
        """Collect all available FGO data."""
        print("\n" + "=" * 60)
        print("Collecting from Atlas Academy (FGO)")
        print("=" * 60)

        # Download bulk exports
        print("\nDownloading bulk data exports...")
        for name, endpoint in self.EXPORTS.items():
            await self.download_export(name, endpoint)
            await asyncio.sleep(0.5)

        # Extract historical figures
        await self.extract_historical_figures()

        # Save metadata
        metadata = {
            "source": "atlas_academy",
            "url": self.BASE_URL,
            "api_docs": "https://api.atlasacademy.io/docs",
            "description": "Fate/Grand Order game data",
            "regions": ["JP", "NA", "CN", "KR", "TW"],
            "license": "Open/Free API",
        }

        metadata_file = self.output_dir / "atlas_academy_metadata.json"
        with open(metadata_file, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)

        print("\nAtlas Academy collection complete!")

    async def close(self):
        await self.client.aclose()


async def main():
    """Main entry point."""
    output_dir = Path("data/raw/atlas_academy")
    collector = AtlasAcademyCollector(output_dir)

    try:
        await collector.collect_all()
    finally:
        await collector.close()


if __name__ == "__main__":
    asyncio.run(main())
