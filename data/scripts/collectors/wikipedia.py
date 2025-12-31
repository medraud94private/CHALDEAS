"""
Wikipedia API Collector

API: https://en.wikipedia.org/w/api.php
Type: MediaWiki API for Wikipedia data

Contains:
- Article summaries and extracts
- Links to related articles
- Historical figure biographies

License: CC BY-SA 3.0
"""
import httpx
import asyncio
from pathlib import Path
import json
from typing import Optional, List


class WikipediaCollector:
    """
    Collector for Wikipedia articles related to FGO servants.

    Uses the MediaWiki API to fetch article summaries and extracts.
    """

    API_URL = "https://en.wikipedia.org/w/api.php"

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.client = httpx.AsyncClient(
            timeout=60.0,
            follow_redirects=True,
            headers={
                "User-Agent": "CHALDEAS/0.1 (Historical Knowledge System; Educational Research; contact@example.com)"
            }
        )
        self.articles = []

    async def get_article_summary(self, title: str) -> Optional[dict]:
        """Get summary/extract for a Wikipedia article."""
        params = {
            "action": "query",
            "titles": title,
            "prop": "extracts|pageimages|categories|links",
            "exintro": True,
            "explaintext": True,
            "pithumbsize": 300,
            "format": "json",
            "redirects": 1,
        }

        try:
            response = await self.client.get(self.API_URL, params=params)
            response.raise_for_status()

            data = response.json()
            pages = data.get("query", {}).get("pages", {})

            for page_id, page in pages.items():
                if page_id == "-1":
                    return None

                return {
                    "title": page.get("title"),
                    "pageid": page.get("pageid"),
                    "extract": page.get("extract", ""),
                    "thumbnail": page.get("thumbnail", {}).get("source"),
                    "categories": [c.get("title") for c in page.get("categories", [])],
                }

        except Exception as e:
            return None

    async def search_article(self, query: str, limit: int = 5) -> List[dict]:
        """Search for Wikipedia articles."""
        params = {
            "action": "query",
            "list": "search",
            "srsearch": query,
            "srlimit": limit,
            "format": "json",
        }

        try:
            response = await self.client.get(self.API_URL, params=params)
            response.raise_for_status()

            data = response.json()
            results = data.get("query", {}).get("search", [])

            return [
                {
                    "title": r.get("title"),
                    "pageid": r.get("pageid"),
                    "snippet": r.get("snippet"),
                }
                for r in results
            ]

        except Exception as e:
            return []

    async def collect_fgo_servants_wikipedia(self, servants_file: Path):
        """Collect Wikipedia articles for FGO servants."""
        print("Loading FGO servants...")

        if not servants_file.exists():
            print(f"Servants file not found: {servants_file}")
            return

        with open(servants_file, "r", encoding="utf-8") as f:
            servants = json.load(f)

        print(f"Found {len(servants)} servants")
        print("Fetching Wikipedia articles...")

        collected = []
        for i, servant in enumerate(servants):
            fgo_name = servant.get("fgo_name") or servant.get("name", "")
            original_name = servant.get("original_name", fgo_name)

            # Skip non-historical
            if not fgo_name:
                continue

            # Safe print
            safe_name = fgo_name.encode('ascii', 'replace').decode('ascii')
            print(f"  [{i+1}/{len(servants)}] {safe_name}...")

            # Try original name first, then FGO name
            article = await self.get_article_summary(original_name)

            if not article and original_name != fgo_name:
                article = await self.get_article_summary(fgo_name)

            if not article:
                # Try search
                results = await self.search_article(f"{original_name} mythology OR history")
                if results:
                    article = await self.get_article_summary(results[0]["title"])

            if article:
                collected.append({
                    "fgo_name": fgo_name,
                    "original_name": original_name,
                    "class": servant.get("class"),
                    "wikipedia": article,
                })

            await asyncio.sleep(0.2)  # Rate limiting

        # Save
        output_file = self.output_dir / "wikipedia_servants.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(collected, f, indent=2, ensure_ascii=False)

        print(f"Collected {len(collected)} Wikipedia articles")
        return collected

    async def collect_historical_figures(self, figures: List[str]):
        """Collect Wikipedia articles for a list of historical figures."""
        print(f"Collecting Wikipedia articles for {len(figures)} figures...")

        collected = []
        for i, name in enumerate(figures):
            safe_name = name.encode('ascii', 'replace').decode('ascii')
            print(f"  [{i+1}/{len(figures)}] {safe_name}...")

            article = await self.get_article_summary(name)

            if article:
                collected.append({
                    "name": name,
                    "wikipedia": article,
                })

            await asyncio.sleep(0.2)

        return collected

    async def collect_all(self):
        """Collect Wikipedia data for FGO servants."""
        print("\n" + "=" * 60)
        print("Collecting from Wikipedia")
        print("=" * 60)

        # Look for FGO historical figures file
        atlas_file = Path("data/raw/atlas_academy/fgo_historical_figures.json")

        if atlas_file.exists():
            await self.collect_fgo_servants_wikipedia(atlas_file)
        else:
            print(f"Atlas Academy data not found at {atlas_file}")
            print("Run atlas_academy collector first")

        # Save metadata
        metadata = {
            "source": "wikipedia",
            "url": "https://en.wikipedia.org/",
            "api": self.API_URL,
            "description": "Wikipedia articles for FGO historical figures",
            "license": "CC BY-SA 3.0",
        }

        metadata_file = self.output_dir / "wikipedia_metadata.json"
        with open(metadata_file, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)

        print("\nWikipedia collection complete!")

    async def close(self):
        await self.client.aclose()


async def main():
    """Main entry point."""
    output_dir = Path("data/raw/wikipedia")
    collector = WikipediaCollector(output_dir)

    try:
        await collector.collect_all()
    finally:
        await collector.close()


if __name__ == "__main__":
    asyncio.run(main())
