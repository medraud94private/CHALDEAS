"""
FGO Gamepress Collector

Website: https://fgo.gamepress.gg/
Type: FGO Wiki/Guide with servant lore and historical backgrounds

Contains:
- Servant profiles with historical background
- Lore analysis and real-world connections
- Strategy guides and team compositions

License: Fan wiki content, for educational use
Note: Be respectful of server load
"""
import httpx
import asyncio
from pathlib import Path
import json
from typing import Optional
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import re


class FGOGamepressCollector:
    """
    Collector for FGO Gamepress servant lore and backgrounds.

    Focuses on collecting historical context for FGO servants.
    """

    BASE_URL = "https://fgo.gamepress.gg"
    SERVANTS_LIST_URL = "https://fgo.gamepress.gg/servants"

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.client = httpx.AsyncClient(
            timeout=60.0,
            follow_redirects=True,
            headers={
                "User-Agent": "CHALDEAS/0.1 (Historical Knowledge System; Educational Research)"
            }
        )
        self.servants = []

    async def get_page(self, url: str) -> Optional[BeautifulSoup]:
        """Fetch and parse a page."""
        try:
            response = await self.client.get(url)
            response.raise_for_status()
            return BeautifulSoup(response.text, "html.parser")
        except Exception as e:
            safe_url = url[:50].encode('ascii', 'replace').decode('ascii')
            print(f"  Error fetching {safe_url}...: {e}")
            return None

    async def collect_servants_list(self) -> list:
        """Collect list of all servants from Gamepress."""
        print("Collecting servants list from Gamepress...")

        soup = await self.get_page(self.SERVANTS_LIST_URL)
        if not soup:
            return []

        servants = []

        # Find servant links
        for link in soup.find_all("a", href=True):
            href = link.get("href", "")

            # Servant pages are like /servant/artoria-pendragon
            if "/servant/" in href and href.count("/") == 2:
                name = link.get_text(strip=True)
                if name and len(name) > 1:
                    full_url = urljoin(self.BASE_URL, href)
                    servants.append({
                        "name": name,
                        "url": full_url,
                        "slug": href.split("/")[-1],
                    })

        # Remove duplicates
        seen_urls = set()
        unique_servants = []
        for s in servants:
            if s["url"] not in seen_urls:
                seen_urls.add(s["url"])
                unique_servants.append(s)

        print(f"Found {len(unique_servants)} servants")
        return unique_servants

    async def collect_servant_lore(self, servant: dict) -> dict:
        """Collect detailed lore for a servant."""
        soup = await self.get_page(servant["url"])
        if not soup:
            return servant

        # Try to find lore/profile section
        lore_section = None
        profile_text = ""

        # Look for profile/lore tabs or sections
        for section in soup.find_all(["div", "section"]):
            section_class = section.get("class", [])
            section_id = section.get("id", "")

            if any(x in str(section_class).lower() + section_id.lower()
                   for x in ["lore", "profile", "biography", "background"]):
                lore_section = section
                break

        if lore_section:
            profile_text = lore_section.get_text(separator="\n", strip=True)

        # Also try to get character info table
        info = {}
        for table in soup.find_all("table"):
            for row in table.find_all("tr"):
                cells = row.find_all(["th", "td"])
                if len(cells) >= 2:
                    key = cells[0].get_text(strip=True).lower()
                    value = cells[1].get_text(strip=True)
                    if key and value:
                        info[key] = value

        servant["profile_text"] = profile_text[:2000] if profile_text else ""
        servant["info"] = info

        return servant

    async def collect_all(self):
        """Collect all servant data from Gamepress."""
        print("\n" + "=" * 60)
        print("Collecting from FGO Gamepress")
        print("=" * 60)

        # Get servants list
        servants = await self.collect_servants_list()

        # Save basic list first
        list_file = self.output_dir / "gamepress_servants_list.json"
        with open(list_file, "w", encoding="utf-8") as f:
            json.dump(servants, f, indent=2, ensure_ascii=False)

        # Collect detailed lore for subset (to be respectful)
        print(f"\nCollecting lore for up to 50 servants...")
        detailed_servants = []

        for i, servant in enumerate(servants[:50]):
            safe_name = servant['name'].encode('ascii', 'replace').decode('ascii')
            print(f"  [{i+1}/50] {safe_name}...")

            detailed = await self.collect_servant_lore(servant)
            detailed_servants.append(detailed)

            await asyncio.sleep(1)  # Rate limiting

        # Save detailed data
        detailed_file = self.output_dir / "gamepress_servants_detailed.json"
        with open(detailed_file, "w", encoding="utf-8") as f:
            json.dump(detailed_servants, f, indent=2, ensure_ascii=False)

        # Save metadata
        metadata = {
            "source": "fgo_gamepress",
            "url": self.BASE_URL,
            "description": "FGO servant lore and historical backgrounds",
            "total_servants": len(servants),
            "detailed_collected": len(detailed_servants),
            "license": "Fan wiki content, educational use",
        }

        metadata_file = self.output_dir / "gamepress_metadata.json"
        with open(metadata_file, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)

        print("\nGamepress collection complete!")

    async def close(self):
        await self.client.aclose()


async def main():
    """Main entry point."""
    output_dir = Path("data/raw/gamepress")
    collector = FGOGamepressCollector(output_dir)

    try:
        await collector.collect_all()
    finally:
        await collector.close()


if __name__ == "__main__":
    asyncio.run(main())
