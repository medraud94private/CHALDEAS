"""
Theoi Project Collector

Website: https://www.theoi.com/
Type: Greek Mythology Encyclopedia

Contains:
- Greek gods, titans, monsters, heroes
- Classical text excerpts about each figure
- Organized by divine family/category

License: Educational use (cite source)
Note: Be respectful of server load - use rate limiting
"""
import httpx
import asyncio
from pathlib import Path
import json
from typing import Optional
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import re


class TheoiCollector:
    """
    Collector for Theoi Project Greek Mythology data.

    Collects structured data about Greek mythological figures.
    """

    BASE_URL = "https://www.theoi.com"

    # Main category pages
    CATEGORIES = {
        "olympians": "/greek-mythology/olympian-gods.html",
        "titans": "/greek-mythology/titans.html",
        "giants": "/greek-mythology/gigantes.html",
        "sea_gods": "/greek-mythology/sea-gods.html",
        "sky_gods": "/greek-mythology/sky-gods.html",
        "rustic_gods": "/greek-mythology/rustic-gods.html",
        "underworld": "/greek-mythology/underworld.html",
        "heroes": "/greek-mythology/heroes.html",
        "creatures": "/greek-mythology/creatures.html",
        "nymphs": "/greek-mythology/nymphs.html",
    }

    # Direct figure index pages (updated 2025)
    INDEX_PAGES = {
        "olympian_gods": "/greek-mythology/olympian-gods.html",
        "titans": "/greek-mythology/titans.html",
        "giants": "/greek-mythology/giants.html",
        "heroes": "/greek-mythology/heroes.html",
        "bestiary": "/greek-mythology/bestiary.html",
        "nymphs": "/greek-mythology/nymphs.html",
        "creatures": "/greek-mythology/fantastic-creatures.html",
        "star_myths": "/greek-mythology/star-myths.html",
    }

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
        self.figures = []

    async def get_page(self, url: str) -> Optional[BeautifulSoup]:
        """Fetch and parse a page."""
        try:
            response = await self.client.get(url)
            response.raise_for_status()
            return BeautifulSoup(response.text, "html.parser")
        except Exception as e:
            print(f"  Error fetching {url}: {e}")
            return None

    async def collect_index_page(self, category: str, path: str):
        """Collect figures from an index page."""
        url = urljoin(self.BASE_URL, path)
        print(f"  Fetching {category} index...")

        soup = await self.get_page(url)
        if not soup:
            return

        # Find all links to figure pages
        for link in soup.find_all("a", href=True):
            href = link.get("href", "")
            text = link.get_text(strip=True)

            # Filter for figure pages (typically end with .html and are internal)
            if text and href.endswith(".html") and not href.startswith("http"):
                if len(text) > 2 and not text.startswith("["):
                    self.figures.append({
                        "name": text,
                        "url": urljoin(url, href),
                        "category": category,
                        "source": "theoi",
                    })

        await asyncio.sleep(0.5)  # Rate limiting

    async def collect_figure_details(self, figure: dict) -> dict:
        """Collect detailed information about a mythological figure."""
        soup = await self.get_page(figure["url"])
        if not soup:
            return figure

        # Try to extract description
        description = ""

        # Look for main content
        main_content = soup.find("div", {"id": "main"}) or soup.find("td", {"class": "main"})
        if main_content:
            # Get first few paragraphs
            paragraphs = main_content.find_all("p", limit=3)
            description = " ".join(p.get_text(strip=True) for p in paragraphs)

        # Clean up description
        description = re.sub(r"\s+", " ", description)[:1000]

        figure["description"] = description

        # Try to find alternate names
        title = soup.find("title")
        if title:
            title_text = title.get_text(strip=True)
            figure["title"] = title_text

        return figure

    async def collect_basic_catalog(self):
        """Collect a basic catalog of all mythological figures."""
        print("\nCollecting Theoi figure catalog...")

        for category, path in self.INDEX_PAGES.items():
            await self.collect_index_page(category, path)

        # Remove duplicates by URL
        seen_urls = set()
        unique_figures = []
        for fig in self.figures:
            if fig["url"] not in seen_urls:
                seen_urls.add(fig["url"])
                unique_figures.append(fig)

        self.figures = unique_figures
        print(f"Found {len(self.figures)} unique figures")

        # Save catalog
        catalog_file = self.output_dir / "theoi_catalog.json"
        with open(catalog_file, "w", encoding="utf-8") as f:
            json.dump(self.figures, f, indent=2, ensure_ascii=False)

        return self.figures

    async def collect_figure_descriptions(self, limit: int = 100):
        """Collect descriptions for figures (limited to avoid overloading server)."""
        print(f"\nCollecting descriptions for up to {limit} figures...")

        detailed_figures = []
        for i, figure in enumerate(self.figures[:limit]):
            print(f"  [{i+1}/{min(limit, len(self.figures))}] {figure['name']}...")

            detailed = await self.collect_figure_details(figure)
            detailed_figures.append(detailed)

            await asyncio.sleep(1)  # Rate limiting - be nice to the server

        # Save detailed figures
        detailed_file = self.output_dir / "theoi_figures_detailed.json"
        with open(detailed_file, "w", encoding="utf-8") as f:
            json.dump(detailed_figures, f, indent=2, ensure_ascii=False)

        print(f"Saved {len(detailed_figures)} detailed figures")

    async def collect_all(self):
        """Collect all available Theoi data."""
        print("\n" + "=" * 60)
        print("Collecting from Theoi Project")
        print("=" * 60)

        # First get the catalog
        await self.collect_basic_catalog()

        # Then get details for a subset (to be respectful of server)
        await self.collect_figure_descriptions(limit=200)

        # Save metadata
        metadata = {
            "source": "theoi",
            "url": self.BASE_URL,
            "description": "Greek mythology encyclopedia",
            "total_figures": len(self.figures),
            "license": "Educational use with citation",
        }

        metadata_file = self.output_dir / "theoi_metadata.json"
        with open(metadata_file, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)

        print("\nTheoi collection complete!")

    async def close(self):
        await self.client.aclose()


# Key mythological figures for FGO/Fate context
PRIORITY_FIGURES = [
    "Zeus", "Hera", "Poseidon", "Athena", "Apollo", "Artemis",
    "Ares", "Aphrodite", "Hermes", "Hephaestus", "Demeter", "Dionysus",
    "Hades", "Persephone", "Hercules", "Perseus", "Achilles", "Odysseus",
    "Jason", "Theseus", "Medusa", "Medea", "Helen", "Paris",
    "Agamemnon", "Orion", "Chiron", "Prometheus", "Atlas", "Kronos",
]


async def main():
    """Main entry point."""
    output_dir = Path("data/raw/theoi")
    collector = TheoiCollector(output_dir)

    try:
        await collector.collect_all()
    finally:
        await collector.close()


if __name__ == "__main__":
    asyncio.run(main())
