"""
World History Encyclopedia Collector

Website: https://www.worldhistory.org/
Type: Historical encyclopedia with articles on civilizations, people, events

Contains:
- Ancient civilizations (Egypt, Mesopotamia, Greece, Rome, etc.)
- Medieval and Renaissance history
- Asian, African, American history
- Historical figures and mythology
- Archaeological sites and artifacts

License: Creative Commons Attribution-NonCommercial-ShareAlike
Note: Non-commercial educational use permitted
"""
import httpx
import asyncio
from pathlib import Path
import json
from typing import Optional, List
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import re


class WorldHistoryCollector:
    """
    Collector for World History Encyclopedia articles.
    """

    BASE_URL = "https://www.worldhistory.org"

    # Main category indexes
    CATEGORIES = {
        "civilizations": "/civilization/",
        "definitions": "/definition/",
        "timelines": "/timeline/",
        "maps": "/map/",
        "collections": "/collection/",
    }

    # Specific civilization/region pages
    REGIONS = {
        "egypt": "/ancient-egypt/",
        "mesopotamia": "/mesopotamia/",
        "greece": "/ancient-greece/",
        "rome": "/ancient-rome/",
        "persia": "/ancient-persia/",
        "china": "/ancient-china/",
        "india": "/ancient-india/",
        "japan": "/ancient-japan/",
        "celtic": "/celtic/",
        "viking": "/viking/",
        "maya": "/maya/",
        "aztec": "/aztec/",
        "inca": "/inca/",
        "medieval": "/medieval/",
        "byzantine": "/byzantine/",
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
        self.articles = []

    async def get_page(self, url: str) -> Optional[BeautifulSoup]:
        """Fetch and parse a page."""
        try:
            response = await self.client.get(url)
            response.raise_for_status()
            return BeautifulSoup(response.text, "html.parser")
        except Exception as e:
            print(f"  Error: {e}")
            return None

    async def collect_index_page(self, name: str, path: str) -> List[dict]:
        """Collect article links from an index page."""
        url = urljoin(self.BASE_URL, path)
        print(f"  Fetching {name}...")

        soup = await self.get_page(url)
        if not soup:
            return []

        articles = []

        # Find article links
        for link in soup.find_all("a", href=True):
            href = link.get("href", "")
            text = link.get_text(strip=True)

            # Look for article links (typically /article/, /definition/, etc.)
            if text and len(text) > 3:
                if any(x in href for x in ["/article/", "/definition/"]):
                    if not href.startswith("http"):
                        full_url = urljoin(url, href)
                    else:
                        full_url = href

                    if "worldhistory.org" in full_url:
                        articles.append({
                            "title": text[:200],
                            "url": full_url,
                            "category": name,
                            "source": "worldhistory",
                        })

        await asyncio.sleep(0.5)
        return articles

    async def collect_sitemap_articles(self) -> List[dict]:
        """Try to get articles from sitemap or browse pages."""
        print("  Fetching popular articles...")

        articles = []

        # Try different browse pages
        browse_urls = [
            "/index/A/",
            "/index/B/",
            "/index/C/",
            "/index/D/",
            "/index/E/",
        ]

        for browse_path in browse_urls:
            url = urljoin(self.BASE_URL, browse_path)
            soup = await self.get_page(url)
            if not soup:
                continue

            for link in soup.find_all("a", href=True):
                href = link.get("href", "")
                text = link.get_text(strip=True)

                if "/article/" in href or "/definition/" in href:
                    if not href.startswith("http"):
                        full_url = urljoin(url, href)
                    else:
                        full_url = href

                    articles.append({
                        "title": text[:200],
                        "url": full_url,
                        "category": "index",
                        "source": "worldhistory",
                    })

            await asyncio.sleep(0.5)

        return articles

    async def collect_article_content(self, article: dict) -> dict:
        """Collect full text of an article."""
        soup = await self.get_page(article["url"])
        if not soup:
            return article

        content = ""

        # Remove navigation and scripts
        for nav in soup.find_all(["script", "style", "nav", "header", "footer", "aside"]):
            nav.decompose()

        # Try to find main article content
        main = (
            soup.find("article") or
            soup.find("div", class_="article-content") or
            soup.find("div", class_="content") or
            soup.find("main") or
            soup.find("body")
        )

        if main:
            content = main.get_text(separator="\n", strip=True)
            content = re.sub(r'\n{3,}', '\n\n', content)

        article["content"] = content[:50000]
        article["content_length"] = len(content)

        return article

    async def collect_all(self):
        """Collect all World History Encyclopedia articles."""
        print("\n" + "=" * 60)
        print("Collecting from World History Encyclopedia")
        print("=" * 60)

        all_articles = []

        # Collect from region pages
        print("\nCollecting from region/civilization pages...")
        for name, path in self.REGIONS.items():
            articles = await self.collect_index_page(name, path)
            all_articles.extend(articles)
            print(f"    {name}: {len(articles)} articles")

        # Collect from category pages
        print("\nCollecting from category pages...")
        for name, path in self.CATEGORIES.items():
            articles = await self.collect_index_page(name, path)
            all_articles.extend(articles)
            print(f"    {name}: {len(articles)} articles")

        # Collect from index pages
        print("\nCollecting from alphabetical index...")
        index_articles = await self.collect_sitemap_articles()
        all_articles.extend(index_articles)
        print(f"    index: {len(index_articles)} articles")

        # Remove duplicates
        seen_urls = set()
        unique_articles = []
        for article in all_articles:
            if article["url"] not in seen_urls:
                seen_urls.add(article["url"])
                unique_articles.append(article)

        print(f"\nTotal unique articles: {len(unique_articles)}")

        # Save index
        index_file = self.output_dir / "worldhistory_index.json"
        with open(index_file, "w", encoding="utf-8") as f:
            json.dump(unique_articles, f, indent=2, ensure_ascii=False)

        # Collect content for subset
        print(f"\nCollecting content for up to 200 key articles...")
        detailed_articles = []

        for i, article in enumerate(unique_articles[:200]):
            safe_title = article['title'][:40].encode('ascii', 'replace').decode('ascii')
            print(f"  [{i+1}/200] {safe_title}...")

            detailed = await self.collect_article_content(article)
            detailed_articles.append(detailed)
            await asyncio.sleep(0.8)

        # Save detailed articles
        detailed_file = self.output_dir / "worldhistory_articles.json"
        with open(detailed_file, "w", encoding="utf-8") as f:
            json.dump(detailed_articles, f, indent=2, ensure_ascii=False)

        # Save metadata
        metadata = {
            "source": "worldhistory",
            "url": self.BASE_URL,
            "description": "World History Encyclopedia - Historical articles and definitions",
            "total_articles": len(unique_articles),
            "detailed_collected": len(detailed_articles),
            "regions": list(self.REGIONS.keys()),
            "categories": list(self.CATEGORIES.keys()),
            "license": "CC BY-NC-SA (educational use)",
        }

        metadata_file = self.output_dir / "worldhistory_metadata.json"
        with open(metadata_file, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)

        print("\nWorld History Encyclopedia collection complete!")

    async def close(self):
        await self.client.aclose()


async def main():
    output_dir = Path("data/raw/worldhistory")
    collector = WorldHistoryCollector(output_dir)
    try:
        await collector.collect_all()
    finally:
        await collector.close()


if __name__ == "__main__":
    asyncio.run(main())
