"""
Arthurian Legends Collector

Sources:
- Wikipedia API (primary)
- Project Gutenberg (texts)

Contains:
- King Arthur and Knights of the Round Table
- Camelot, Avalon, Holy Grail
- Morgan le Fay, Merlin, Lancelot, etc.

License: CC BY-SA 3.0 (Wikipedia), Public Domain (Gutenberg)
"""
import httpx
import asyncio
from pathlib import Path
import json
from typing import Optional, List


# Key Arthurian figures and concepts for FGO coverage
ARTHURIAN_TOPICS = [
    # Main Characters
    "King Arthur",
    "Guinevere",
    "Merlin (wizard)",
    "Morgan le Fay",
    "Mordred",
    "Lancelot",
    "Galahad",
    "Gawain",
    "Percival",
    "Tristan",
    "Bedivere",
    "Kay (Arthurian legend)",
    "Agravain",
    "Gareth",
    "Gaheris",

    # Places
    "Camelot",
    "Avalon",
    "Tintagel Castle",
    "Glastonbury",
    "Lyonesse",

    # Objects/Concepts
    "Excalibur",
    "Holy Grail",
    "Round Table",
    "Siege Perilous",
    "Sword in the Stone",
    "Caliburn",
    "Rhongomyniad",
    "Carnwennan",
    "Clarent",

    # Stories/Events
    "Quest for the Holy Grail",
    "Battle of Camlann",
    "Lady of the Lake",
    "Fisher King",
    "Waste Land (Arthurian)",

    # Other Characters
    "Uther Pendragon",
    "Igraine",
    "Viviane",
    "Nimue",
    "Elaine of Astolat",
    "Elaine of Corbenic",
    "Isolde",
    "Palamedes (knight)",
    "Bors",
    "Ector",

    # Related Mythology
    "Matter of Britain",
    "Mabinogion",
    "Historia Regum Britanniae",
    "Le Morte d'Arthur",
    "Welsh mythology",
    "Celtic mythology",
    "Fairy (Arthurian)",
]

# Gutenberg books on Arthurian legends
ARTHURIAN_GUTENBERG_IDS = [
    1251,   # Le Morte d'Arthur - Vol 1
    1252,   # Le Morte d'Arthur - Vol 2
    831,    # The Legends of King Arthur and His Knights
    5313,   # A Connecticut Yankee in King Arthur's Court
    1961,   # Idylls of the King (Tennyson)
    2041,   # The Boy's King Arthur
    25336,  # Celtic Fairy Tales
    14935,  # The Story of King Arthur and His Knights
    7581,   # King Arthur and the Knights of the Round Table
    35994,  # The Mabinogion
]


class ArthurianCollector:
    """
    Collector for Arthurian legends and mythology.
    """

    WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"
    GUTENBERG_URL = "https://www.gutenberg.org/cache/epub/{book_id}/pg{book_id}.txt"

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
            "prop": "extracts|pageimages|categories|links|revisions",
            "explaintext": True,
            "pithumbsize": 500,
            "format": "json",
            "redirects": 1,
            "rvprop": "content",
            "rvslots": "main",
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

    async def get_gutenberg_text(self, book_id: int) -> Optional[str]:
        """Download a Gutenberg book."""
        url = self.GUTENBERG_URL.format(book_id=book_id)
        try:
            response = await self.client.get(url)
            response.raise_for_status()
            return response.text
        except Exception as e:
            print(f"  Error fetching Gutenberg {book_id}: {e}")
            return None

    async def collect_wikipedia_articles(self) -> List[dict]:
        """Collect Wikipedia articles on Arthurian topics."""
        print("\nCollecting Arthurian Wikipedia articles...")

        articles = []
        for i, topic in enumerate(ARTHURIAN_TOPICS):
            safe_topic = topic.encode('ascii', 'replace').decode('ascii')
            print(f"  [{i+1}/{len(ARTHURIAN_TOPICS)}] {safe_topic}...")

            article = await self.get_wikipedia_article(topic)
            if article:
                article["topic_type"] = "arthurian"
                articles.append(article)

            await asyncio.sleep(0.3)  # Rate limiting

        print(f"Collected {len(articles)} Arthurian articles")
        return articles

    async def collect_gutenberg_texts(self) -> List[dict]:
        """Collect Arthurian texts from Gutenberg."""
        print("\nCollecting Arthurian Gutenberg texts...")

        texts = []
        for i, book_id in enumerate(ARTHURIAN_GUTENBERG_IDS):
            print(f"  [{i+1}/{len(ARTHURIAN_GUTENBERG_IDS)}] Book {book_id}...")

            text = await self.get_gutenberg_text(book_id)
            if text:
                # Save individual file
                output_file = self.output_dir / f"gutenberg_pg{book_id}.txt"
                with open(output_file, "w", encoding="utf-8") as f:
                    f.write(text)

                texts.append({
                    "book_id": book_id,
                    "source": "gutenberg",
                    "file": f"gutenberg_pg{book_id}.txt",
                    "length": len(text),
                })

            await asyncio.sleep(0.5)

        print(f"Collected {len(texts)} Gutenberg texts")
        return texts

    async def collect_all(self):
        """Collect all Arthurian data."""
        print("\n" + "=" * 60)
        print("Collecting Arthurian Legends Data")
        print("=" * 60)

        # Wikipedia articles
        articles = await self.collect_wikipedia_articles()

        # Save Wikipedia data
        wiki_file = self.output_dir / "arthurian_wikipedia.json"
        with open(wiki_file, "w", encoding="utf-8") as f:
            json.dump(articles, f, indent=2, ensure_ascii=False)

        # Gutenberg texts
        gutenberg_texts = await self.collect_gutenberg_texts()

        # Save Gutenberg index
        gutenberg_file = self.output_dir / "arthurian_gutenberg_index.json"
        with open(gutenberg_file, "w", encoding="utf-8") as f:
            json.dump(gutenberg_texts, f, indent=2)

        # Save metadata
        metadata = {
            "source": "arthurian_legends",
            "description": "Arthurian legends for FGO Camelot/Avalon coverage",
            "wikipedia_articles": len(articles),
            "gutenberg_texts": len(gutenberg_texts),
            "topics": ARTHURIAN_TOPICS,
            "license": "CC BY-SA 3.0 (Wikipedia), Public Domain (Gutenberg)",
            "fgo_relevance": [
                "Camelot Singularity",
                "Avalon le Fae Lostbelt",
                "Saber Artoria",
                "Knights of Round Table servants",
            ],
        }

        metadata_file = self.output_dir / "arthurian_metadata.json"
        with open(metadata_file, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)

        print(f"\nArthurian collection complete!")
        print(f"  Wikipedia: {len(articles)} articles")
        print(f"  Gutenberg: {len(gutenberg_texts)} texts")

    async def close(self):
        await self.client.aclose()


async def main():
    output_dir = Path("data/raw/arthurian")
    collector = ArthurianCollector(output_dir)

    try:
        await collector.collect_all()
    finally:
        await collector.close()


if __name__ == "__main__":
    asyncio.run(main())
