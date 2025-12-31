"""
Fordham Internet History Sourcebooks Collector

Website: https://sourcebooks.fordham.edu/
Type: Primary source collections for teaching history

Contains:
- Ancient History Sourcebook
- Medieval Sourcebook
- Modern History Sourcebook
- Subsidiary sourcebooks (Byzantine, Islamic, Jewish, etc.)

License: Public domain texts, educational use permitted
"""
import httpx
import asyncio
from pathlib import Path
import json
from typing import Optional, List
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import re


class FordhamCollector:
    """
    Collector for Fordham Internet History Sourcebooks.
    """

    BASE_URL = "https://sourcebooks.fordham.edu"

    # Main sourcebooks
    SOURCEBOOKS = {
        "ancient": "/ancient/asbook.asp",
        "medieval": "/sbook.asp",
        "modern": "/mod/modsbook.asp",
    }

    # Subsidiary sourcebooks
    SUBSIDIARY = {
        "byzantine": "/byzantium/index.asp",
        "islamic": "/islam/islambook.asp",
        "jewish": "/jewish/jewishbook.asp",
        "african": "/africa/africanbook.asp",
        "eastasian": "/eastasia/eastasiabook.asp",
        "indian": "/india/indiabook.asp",
        "women": "/women/wombook.asp",
        "science": "/science/sciencebook.asp",
        "lgbtq": "/pwh/index.asp",
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
        self.sources = []

    async def get_page(self, url: str) -> Optional[BeautifulSoup]:
        """Fetch and parse a page."""
        try:
            response = await self.client.get(url)
            response.raise_for_status()
            return BeautifulSoup(response.text, "html.parser")
        except Exception as e:
            print(f"  Error: {e}")
            return None

    async def collect_sourcebook_index(self, name: str, path: str) -> List[dict]:
        """Collect source list from a sourcebook main page."""
        url = urljoin(self.BASE_URL, path)
        print(f"  Fetching {name} sourcebook...")

        soup = await self.get_page(url)
        if not soup:
            return []

        sources = []
        for link in soup.find_all("a", href=True):
            href = link.get("href", "")
            text = link.get_text(strip=True)

            # Filter for source pages
            if text and len(text) > 10:
                # Skip navigation and index links
                if any(x in href.lower() for x in ["index", "book.asp", "menu", "#"]):
                    continue
                if any(x in text.lower() for x in ["index", "home", "search"]):
                    continue

                # Handle relative URLs
                if not href.startswith("http"):
                    full_url = urljoin(url, href)
                else:
                    full_url = href

                # Only include fordham sources
                if "fordham.edu" in full_url or not href.startswith("http"):
                    sources.append({
                        "title": text[:200],
                        "url": full_url,
                        "sourcebook": name,
                        "source": "fordham",
                    })

        await asyncio.sleep(0.5)
        return sources

    async def collect_source_content(self, source: dict) -> dict:
        """Collect full text of a source document."""
        soup = await self.get_page(source["url"])
        if not soup:
            return source

        # Extract main content
        content = ""

        # Remove navigation
        for nav in soup.find_all(["script", "style", "nav", "header", "footer"]):
            nav.decompose()

        # Try to find main content area
        main = soup.find("main") or soup.find("article") or soup.find("body")
        if main:
            content = main.get_text(separator="\n", strip=True)
            content = re.sub(r'\n{3,}', '\n\n', content)

        source["content"] = content[:30000]  # Limit size
        source["content_length"] = len(content)

        return source

    async def collect_all(self):
        """Collect all Fordham Sourcebook materials."""
        print("\n" + "=" * 60)
        print("Collecting from Fordham Internet History Sourcebooks")
        print("=" * 60)

        all_sources = []

        # Collect main sourcebooks
        print("\nCollecting main sourcebooks...")
        for name, path in self.SOURCEBOOKS.items():
            sources = await self.collect_sourcebook_index(name, path)
            all_sources.extend(sources)
            print(f"    {name}: {len(sources)} sources")

        # Collect subsidiary sourcebooks
        print("\nCollecting subsidiary sourcebooks...")
        for name, path in self.SUBSIDIARY.items():
            sources = await self.collect_sourcebook_index(name, path)
            all_sources.extend(sources)
            print(f"    {name}: {len(sources)} sources")

        # Remove duplicates
        seen_urls = set()
        unique_sources = []
        for source in all_sources:
            if source["url"] not in seen_urls:
                seen_urls.add(source["url"])
                unique_sources.append(source)

        print(f"\nTotal unique sources: {len(unique_sources)}")

        # Save index
        index_file = self.output_dir / "fordham_index.json"
        with open(index_file, "w", encoding="utf-8") as f:
            json.dump(unique_sources, f, indent=2, ensure_ascii=False)

        # Collect content for subset
        print(f"\nCollecting content for up to 150 key sources...")
        detailed_sources = []

        for i, source in enumerate(unique_sources[:150]):
            safe_title = source['title'][:40].encode('ascii', 'replace').decode('ascii')
            print(f"  [{i+1}/150] {safe_title}...")

            detailed = await self.collect_source_content(source)
            detailed_sources.append(detailed)
            await asyncio.sleep(0.8)

        # Save detailed sources
        detailed_file = self.output_dir / "fordham_sources.json"
        with open(detailed_file, "w", encoding="utf-8") as f:
            json.dump(detailed_sources, f, indent=2, ensure_ascii=False)

        # Save metadata
        metadata = {
            "source": "fordham",
            "url": self.BASE_URL,
            "description": "Fordham Internet History Sourcebooks Project",
            "total_sources": len(unique_sources),
            "detailed_collected": len(detailed_sources),
            "main_sourcebooks": list(self.SOURCEBOOKS.keys()),
            "subsidiary_sourcebooks": list(self.SUBSIDIARY.keys()),
            "license": "Public domain texts, educational use",
        }

        metadata_file = self.output_dir / "fordham_metadata.json"
        with open(metadata_file, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)

        print("\nFordham Sourcebooks collection complete!")

    async def close(self):
        await self.client.aclose()


async def main():
    output_dir = Path("data/raw/fordham")
    collector = FordhamCollector(output_dir)
    try:
        await collector.collect_all()
    finally:
        await collector.close()


if __name__ == "__main__":
    asyncio.run(main())
