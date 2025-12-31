"""
Russian/Eastern European History Collector

Sources:
- Wikipedia API (primary)

Contains:
- Russian Empire history
- Ivan the Terrible, Anastasia
- Russian mythology (Slavic)
- Eastern European rulers and events

License: CC BY-SA 3.0
"""
import httpx
import asyncio
from pathlib import Path
import json
from typing import Optional, List


# Key Russian/Eastern European topics for FGO coverage (especially LB1 Anastasia)
RUSSIAN_TOPICS = [
    # Tsars and Rulers
    "Ivan the Terrible",
    "Ivan III of Russia",
    "Anastasia of Russia",  # Grand Duchess, FGO servant
    "Anastasia Romanov",
    "Peter the Great",
    "Catherine the Great",
    "Nicholas II of Russia",
    "Alexander II of Russia",
    "Rurik",
    "Vladimir the Great",
    "Boris Godunov",

    # Historical Figures
    "Rasputin",
    "Oprichnik",
    "Dmitry Donskoy",
    "Alexander Nevsky",
    "Ivan Susanin",

    # Slavic Mythology
    "Slavic mythology",
    "Slavic paganism",
    "Koschei",
    "Baba Yaga",
    "Firebird (Slavic folklore)",
    "Domovoi",
    "Leshy",
    "Rusalka",
    "Veles (god)",
    "Perun",
    "Morana (goddess)",
    "Rod (Slavic religion)",
    "Dazhbog",
    "Svarog",
    "Belobog",
    "Chernobog",

    # Russian Fairy Tales
    "Russian fairy tales",
    "Vasilisa the Beautiful",
    "The Snow Maiden",
    "Ilya Muromets",
    "Dobrynya Nikitich",
    "Alyosha Popovich",
    "Sadko",

    # Places
    "Moscow Kremlin",
    "Saint Petersburg",
    "Novgorod",
    "Kievan Rus'",
    "Golden Horde",
    "Muscovy",

    # Events
    "Time of Troubles",
    "Russian Revolution",
    "Mongol invasion of Rus'",
    "Oprichnina",
    "Romanov dynasty",
    "House of Rurik",

    # Eastern European (Polish, etc.)
    "Casimir III the Great",
    "Jan III Sobieski",
    "Stefan Batory",
    "Bohdan Khmelnytsky",
    "Vlad the Impaler",
    "Stephen the Great",

    # FGO Specific
    "Yaga (folklore)",
    "Russian Orthodox Church",
    "Winter Palace",
]

# Additional figures for broader coverage
RUSSIAN_FIGURES = [
    # Literary Figures
    "Alexander Pushkin",
    "Leo Tolstoy",
    "Fyodor Dostoevsky",

    # Military
    "Mikhail Kutuzov",
    "Alexander Suvorov",

    # Scientists/Artists
    "Dmitri Mendeleev",
    "Pyotr Ilyich Tchaikovsky",
]


class RussianHistoryCollector:
    """
    Collector for Russian and Eastern European history.
    """

    WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.client = httpx.AsyncClient(
            timeout=60.0,
            follow_redirects=True,
            headers={
                "User-Agent": "CHALDEAS/0.1 (Historical Knowledge System)"
            }
        )

    async def get_wikipedia_article(self, title: str) -> Optional[dict]:
        """Get full Wikipedia article content."""
        params = {
            "action": "query",
            "titles": title,
            "prop": "extracts|pageimages|categories",
            "explaintext": True,
            "pithumbsize": 500,
            "format": "json",
            "redirects": 1,
        }

        try:
            response = await self.client.get(self.WIKIPEDIA_API, params=params)
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
                    "categories": [c.get("title", "").replace("Category:", "")
                                   for c in page.get("categories", [])],
                }

        except Exception as e:
            print(f"  Error fetching {title}: {e}")
            return None

    async def collect_all(self):
        """Collect Russian/Eastern European history data."""
        print("\n" + "=" * 60)
        print("Collecting Russian/Eastern European History")
        print("=" * 60)

        all_topics = RUSSIAN_TOPICS + RUSSIAN_FIGURES
        articles = []

        for i, topic in enumerate(all_topics):
            safe_topic = topic.encode('ascii', 'replace').decode('ascii')
            print(f"  [{i+1}/{len(all_topics)}] {safe_topic}...")

            article = await self.get_wikipedia_article(topic)
            if article:
                articles.append(article)

            await asyncio.sleep(0.3)

        # Categorize articles
        mythology = []
        rulers = []
        events = []
        places = []
        other = []

        mythology_keywords = ["mythology", "folklore", "fairy", "god", "goddess", "slavic"]
        ruler_keywords = ["tsar", "emperor", "king", "queen", "prince", "duchess", "grand"]
        place_keywords = ["kremlin", "palace", "city", "rus", "empire", "kingdom"]
        event_keywords = ["war", "revolution", "invasion", "battle", "dynasty"]

        for article in articles:
            title_lower = article.get("title", "").lower()
            cats = " ".join(article.get("categories", [])).lower()

            if any(k in title_lower or k in cats for k in mythology_keywords):
                mythology.append(article)
            elif any(k in title_lower or k in cats for k in ruler_keywords):
                rulers.append(article)
            elif any(k in title_lower or k in cats for k in place_keywords):
                places.append(article)
            elif any(k in title_lower or k in cats for k in event_keywords):
                events.append(article)
            else:
                other.append(article)

        # Save all articles
        all_file = self.output_dir / "russian_wikipedia.json"
        with open(all_file, "w", encoding="utf-8") as f:
            json.dump(articles, f, indent=2, ensure_ascii=False)

        # Save categorized
        categorized = {
            "mythology": mythology,
            "rulers": rulers,
            "events": events,
            "places": places,
            "other": other,
        }

        cat_file = self.output_dir / "russian_categorized.json"
        with open(cat_file, "w", encoding="utf-8") as f:
            json.dump(categorized, f, indent=2, ensure_ascii=False)

        # Save metadata
        metadata = {
            "source": "russian_history",
            "description": "Russian/Eastern European history for FGO LB1 Anastasia coverage",
            "total_articles": len(articles),
            "categories": {
                "mythology": len(mythology),
                "rulers": len(rulers),
                "events": len(events),
                "places": len(places),
                "other": len(other),
            },
            "license": "CC BY-SA 3.0",
            "fgo_relevance": [
                "Lostbelt 1: Anastasia",
                "Ivan the Terrible (Rider)",
                "Anastasia (Caster)",
                "Rasputin/Kirei",
            ],
        }

        metadata_file = self.output_dir / "russian_metadata.json"
        with open(metadata_file, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)

        print(f"\nRussian history collection complete!")
        print(f"  Total: {len(articles)} articles")
        print(f"  Mythology: {len(mythology)}, Rulers: {len(rulers)}")
        print(f"  Events: {len(events)}, Places: {len(places)}")

    async def close(self):
        await self.client.aclose()


async def main():
    output_dir = Path("data/raw/russian_history")
    collector = RussianHistoryCollector(output_dir)

    try:
        await collector.collect_all()
    finally:
        await collector.close()


if __name__ == "__main__":
    asyncio.run(main())
