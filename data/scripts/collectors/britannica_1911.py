"""
1911 Encyclopedia Britannica Collector

Source: Wikisource (en.wikisource.org)
Type: Public domain encyclopedia

The 11th edition of Encyclopedia Britannica (1910-1911) is considered
one of the greatest encyclopedias ever published. It's fully in the
public domain and contains extensive historical, biographical, and
geographical content.

License: Public Domain (published 1910-1911, copyright expired)
Note: High-quality scholarly content, invaluable for historical context
"""
import httpx
import asyncio
from pathlib import Path
import json
from typing import Optional, List
import re


class Britannica1911Collector:
    """
    Collector for 1911 Encyclopedia Britannica from Wikisource.
    """

    API_URL = "https://en.wikisource.org/w/api.php"

    # Priority categories for historical relevance
    PRIORITY_CATEGORIES = [
        # Ancient civilizations
        "Category:1911 Encyclopædia Britannica articles about ancient Greece",
        "Category:1911 Encyclopædia Britannica articles about ancient Rome",
        "Category:1911 Encyclopædia Britannica articles about ancient Egypt",
        "Category:1911 Encyclopædia Britannica articles about Mesopotamia",
        "Category:1911 Encyclopædia Britannica articles about Persia",

        # Historical figures and biography
        "Category:1911 Encyclopædia Britannica articles about people",
        "Category:1911 Encyclopædia Britannica articles about philosophers",
        "Category:1911 Encyclopædia Britannica articles about rulers",

        # Historical topics
        "Category:1911 Encyclopædia Britannica articles about history",
        "Category:1911 Encyclopædia Britannica articles about wars",
        "Category:1911 Encyclopædia Britannica articles about mythology",
        "Category:1911 Encyclopædia Britannica articles about religion",

        # Places
        "Category:1911 Encyclopædia Britannica articles about cities",
        "Category:1911 Encyclopædia Britannica articles about countries",
    ]

    # Key articles to prioritize (FGO/history relevant)
    KEY_ARTICLES = [
        # Ancient figures
        "1911 Encyclopædia Britannica/Alexander III., King of Macedonia",
        "1911 Encyclopædia Britannica/Julius Caesar",
        "1911 Encyclopædia Britannica/Cleopatra",
        "1911 Encyclopædia Britannica/Nero",
        "1911 Encyclopædia Britannica/Socrates",
        "1911 Encyclopædia Britannica/Plato",
        "1911 Encyclopædia Britannica/Aristotle",
        "1911 Encyclopædia Britannica/Homer",
        "1911 Encyclopædia Britannica/Herodotus",
        "1911 Encyclopædia Britannica/Leonidas",

        # Medieval figures
        "1911 Encyclopædia Britannica/Charlemagne",
        "1911 Encyclopædia Britannica/Richard I., King of England",
        "1911 Encyclopædia Britannica/Joan of Arc",
        "1911 Encyclopædia Britannica/Saladin",
        "1911 Encyclopædia Britannica/Frederick I., Roman Emperor",

        # Asian history
        "1911 Encyclopædia Britannica/Confucius",
        "1911 Encyclopædia Britannica/Buddha",
        "1911 Encyclopædia Britannica/Genghis Khan",
        "1911 Encyclopædia Britannica/Tamerlane",

        # Mythology
        "1911 Encyclopædia Britannica/Heracles",
        "1911 Encyclopædia Britannica/Achilles",
        "1911 Encyclopædia Britannica/Gilgamesh",
        "1911 Encyclopædia Britannica/Mythology",

        # Civilizations
        "1911 Encyclopædia Britannica/Rome, History",
        "1911 Encyclopædia Britannica/Greece, History",
        "1911 Encyclopædia Britannica/Egypt, History",
        "1911 Encyclopædia Britannica/Persia",
        "1911 Encyclopædia Britannica/Babylon",
        "1911 Encyclopædia Britannica/Assyria",

        # Wars and events
        "1911 Encyclopædia Britannica/Trojan War",
        "1911 Encyclopædia Britannica/Punic Wars",
        "1911 Encyclopædia Britannica/Crusades",
        "1911 Encyclopædia Britannica/Hundred Years' War",
    ]

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

    async def get_category_members(self, category: str, limit: int = 500) -> List[str]:
        """Get pages in a category."""
        members = []
        cmcontinue = None

        while True:
            params = {
                "action": "query",
                "list": "categorymembers",
                "cmtitle": category,
                "cmlimit": min(limit, 500),
                "cmtype": "page",
                "format": "json",
            }
            if cmcontinue:
                params["cmcontinue"] = cmcontinue

            try:
                response = await self.client.get(self.API_URL, params=params)
                response.raise_for_status()
                data = response.json()

                for member in data.get("query", {}).get("categorymembers", []):
                    title = member.get("title", "")
                    if title.startswith("1911 Encyclopædia Britannica/"):
                        members.append(title)

                # Check for continuation
                if "continue" in data and len(members) < limit:
                    cmcontinue = data["continue"].get("cmcontinue")
                else:
                    break

            except Exception as e:
                print(f"  Error getting category {category}: {e}")
                break

            await asyncio.sleep(0.3)

        return members[:limit]

    async def search_britannica_articles(self, query: str, limit: int = 50) -> List[str]:
        """Search for 1911 Britannica articles."""
        params = {
            "action": "query",
            "list": "search",
            "srsearch": f"intitle:\"1911 Encyclopædia Britannica\" {query}",
            "srlimit": limit,
            "srnamespace": 0,
            "format": "json",
        }

        try:
            response = await self.client.get(self.API_URL, params=params)
            response.raise_for_status()
            data = response.json()

            articles = []
            for result in data.get("query", {}).get("search", []):
                title = result.get("title", "")
                if title.startswith("1911 Encyclopædia Britannica/"):
                    articles.append(title)

            return articles

        except Exception as e:
            print(f"  Search error: {e}")
            return []

    async def get_all_britannica_pages(self, limit: int = 5000) -> List[str]:
        """Get all 1911 Britannica article titles."""
        print("  Fetching article index...")

        all_pages = []
        apcontinue = None

        while len(all_pages) < limit:
            params = {
                "action": "query",
                "list": "allpages",
                "apprefix": "1911 Encyclopædia Britannica/",
                "aplimit": 500,
                "apnamespace": 0,
                "format": "json",
            }
            if apcontinue:
                params["apcontinue"] = apcontinue

            try:
                response = await self.client.get(self.API_URL, params=params)
                response.raise_for_status()
                data = response.json()

                for page in data.get("query", {}).get("allpages", []):
                    all_pages.append(page["title"])

                if "continue" in data:
                    apcontinue = data["continue"].get("apcontinue")
                else:
                    break

            except Exception as e:
                print(f"  Error: {e}")
                break

            await asyncio.sleep(0.2)

        return all_pages[:limit]

    async def get_article_content(self, title: str) -> Optional[dict]:
        """Get the wikitext content of an article."""
        params = {
            "action": "query",
            "titles": title,
            "prop": "revisions|categories",
            "rvprop": "content",
            "rvslots": "main",
            "format": "json",
        }

        try:
            response = await self.client.get(self.API_URL, params=params)
            response.raise_for_status()
            data = response.json()

            pages = data.get("query", {}).get("pages", {})
            for page_id, page_data in pages.items():
                if page_id == "-1":
                    return None

                revisions = page_data.get("revisions", [])
                if not revisions:
                    return None

                content = revisions[0].get("slots", {}).get("main", {}).get("*", "")

                # Extract plain text from wikitext
                plain_text = self._wikitext_to_plain(content)

                # Get article name from title
                article_name = title.replace("1911 Encyclopædia Britannica/", "")

                # Get categories
                categories = [
                    cat.get("title", "").replace("Category:", "")
                    for cat in page_data.get("categories", [])
                ]

                return {
                    "title": article_name,
                    "full_title": title,
                    "url": f"https://en.wikisource.org/wiki/{title.replace(' ', '_')}",
                    "content": plain_text[:80000],
                    "content_length": len(plain_text),
                    "categories": categories,
                    "source": "britannica_1911",
                    "source_url": "https://en.wikisource.org/wiki/1911_Encyclop%C3%A6dia_Britannica",
                    "license": "Public Domain",
                }

        except Exception as e:
            print(f"  Error getting {title}: {e}")
            return None

    def _wikitext_to_plain(self, wikitext: str) -> str:
        """Convert wikitext to plain text."""
        text = wikitext

        # Remove templates
        text = re.sub(r'\{\{[^}]+\}\}', '', text)

        # Remove file/image links
        text = re.sub(r'\[\[(?:File|Image):[^\]]+\]\]', '', text)

        # Convert wiki links to plain text
        text = re.sub(r'\[\[[^\]|]+\|([^\]]+)\]\]', r'\1', text)
        text = re.sub(r'\[\[([^\]]+)\]\]', r'\1', text)

        # Remove HTML tags
        text = re.sub(r'<[^>]+>', '', text)

        # Remove bold/italic markup
        text = re.sub(r"'{2,}", '', text)

        # Remove headings markup but keep text
        text = re.sub(r'={2,}\s*([^=]+)\s*={2,}', r'\n\1\n', text)

        # Remove extra whitespace
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r' +', ' ', text)

        return text.strip()

    async def collect_all(self, max_articles: int = 500):
        """Collect 1911 Britannica articles."""
        print("\n" + "=" * 60)
        print("Collecting from 1911 Encyclopedia Britannica (Wikisource)")
        print("=" * 60)

        # First, get total count
        all_titles = await self.get_all_britannica_pages(limit=10000)
        print(f"Found {len(all_titles)} total articles")

        # Save full index
        index_file = self.output_dir / "britannica_index.json"
        with open(index_file, "w", encoding="utf-8") as f:
            json.dump({
                "total_count": len(all_titles),
                "titles": all_titles,
            }, f, indent=2, ensure_ascii=False)

        # Prioritize key articles first
        articles_to_collect = []

        # Add key articles
        for title in self.KEY_ARTICLES:
            if title in all_titles:
                articles_to_collect.append(title)
        print(f"Priority key articles: {len(articles_to_collect)}")

        # Search for history-related articles
        search_terms = [
            "ancient", "history", "emperor", "king", "queen",
            "war", "battle", "mythology", "legend", "hero",
            "philosophy", "religion", "civilization"
        ]

        for term in search_terms:
            results = await self.search_britannica_articles(term, limit=50)
            for title in results:
                if title not in articles_to_collect:
                    articles_to_collect.append(title)
            await asyncio.sleep(0.5)

        print(f"After search: {len(articles_to_collect)} priority articles")

        # Fill remaining with alphabetical order
        for title in all_titles:
            if title not in articles_to_collect:
                articles_to_collect.append(title)
            if len(articles_to_collect) >= max_articles:
                break

        articles_to_collect = articles_to_collect[:max_articles]
        print(f"\nCollecting content for {len(articles_to_collect)} articles...")

        collected = []
        for i, title in enumerate(articles_to_collect):
            safe_title = title[-50:].encode('ascii', 'replace').decode('ascii')
            print(f"  [{i+1}/{len(articles_to_collect)}] ...{safe_title}")

            article = await self.get_article_content(title)
            if article:
                collected.append(article)

            await asyncio.sleep(0.5)

            # Save periodically
            if (i + 1) % 100 == 0:
                self._save_articles(collected)

        # Final save
        self._save_articles(collected)

        # Save metadata
        metadata = {
            "source": "britannica_1911",
            "source_url": "https://en.wikisource.org/wiki/1911_Encyclop%C3%A6dia_Britannica",
            "description": "1911 Encyclopedia Britannica (11th edition) - Public domain scholarly encyclopedia",
            "total_available": len(all_titles),
            "collected": len(collected),
            "license": "Public Domain (published 1910-1911)",
            "note": "One of the greatest encyclopedias, invaluable for historical research",
        }

        metadata_file = self.output_dir / "britannica_metadata.json"
        with open(metadata_file, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)

        print(f"\n1911 Britannica collection complete!")
        print(f"  Total available: {len(all_titles)}")
        print(f"  Collected: {len(collected)}")

    def _save_articles(self, articles: List[dict]):
        """Save collected articles."""
        articles_file = self.output_dir / "britannica_articles.json"
        with open(articles_file, "w", encoding="utf-8") as f:
            json.dump(articles, f, indent=2, ensure_ascii=False)

    async def close(self):
        await self.client.aclose()


async def main():
    output_dir = Path("data/raw/britannica_1911")
    collector = Britannica1911Collector(output_dir)
    try:
        await collector.collect_all(max_articles=500)
    finally:
        await collector.close()


if __name__ == "__main__":
    asyncio.run(main())
