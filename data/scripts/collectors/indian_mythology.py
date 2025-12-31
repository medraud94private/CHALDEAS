"""
Indian Mythology & History Collector

Sources:
- Wikipedia API (primary)

Contains:
- Hindu mythology (Vedic, Puranic)
- Buddhist history and mythology
- Indian epics (Mahabharata, Ramayana)
- Indian historical figures

License: CC BY-SA 3.0
"""
import httpx
import asyncio
from pathlib import Path
import json
from typing import Optional, List


# Hindu Deities - Major
HINDU_DEITIES = [
    # Trimurti
    "Brahma",
    "Vishnu",
    "Shiva",

    # Major Deities
    "Ganesha",
    "Parvati",
    "Lakshmi",
    "Saraswati",
    "Hanuman",
    "Krishna",
    "Rama",
    "Indra",
    "Surya",
    "Agni",
    "Varuna",
    "Yama",
    "Kubera",
    "Kartikeya",

    # Goddesses
    "Durga",
    "Kali",
    "Sita",
    "Radha",
    "Shakti",
    "Devi",

    # Other Deities
    "Kamadeva",
    "Vayu",
    "Chandra",
    "Brihaspati",
    "Shukra",
    "Rahu",
    "Ketu",
]

# Epic Characters (Mahabharata & Ramayana)
EPIC_CHARACTERS = [
    # Mahabharata Heroes
    "Arjuna",
    "Karna",
    "Bhishma",
    "Drona",
    "Ashwatthama",
    "Yudhishthira",
    "Bhima",
    "Nakula",
    "Sahadeva",
    "Duryodhana",
    "Abhimanyu",
    "Ekalavya",
    "Parashurama",

    # Mahabharata Other
    "Draupadi",
    "Kunti",
    "Gandhari",
    "Shakuni",
    "Vidura",

    # Ramayana Characters
    "Rama",
    "Sita",
    "Lakshmana",
    "Ravana",
    "Hanuman",
    "Bharata (Ramayana)",
    "Vibhishana",
    "Kumbhakarna",
    "Indrajit",
    "Jatayu",
    "Sugriva",
]

# Mythological Concepts & Creatures
MYTHOLOGY_CONCEPTS = [
    # Core Concepts
    "Hindu mythology",
    "Vedic mythology",
    "Mahabharata",
    "Ramayana",
    "Bhagavad Gita",
    "Vedas",
    "Upanishads",
    "Puranas",

    # Cosmology
    "Hindu cosmology",
    "Yuga",
    "Kali Yuga",
    "Satya Yuga",
    "Dvapara Yuga",
    "Treta Yuga",
    "Kalki",
    "Pralaya",

    # Creatures
    "Naga (mythology)",
    "Garuda",
    "Asura",
    "Deva (Hinduism)",
    "Rakshasa",
    "Yaksha",
    "Gandharva",
    "Apsara",
    "Vanara",
    "Makara (Hindu mythology)",

    # Weapons/Objects
    "Brahmastra",
    "Pashupatastra",
    "Gandiva",
    "Vijaya (bow)",
    "Sudarshana Chakra",
    "Trishula",
    "Vajra",
    "Kaumodaki",

    # Places
    "Lanka",
    "Kurukshetra",
    "Ayodhya",
    "Dwarka",
    "Mount Meru",
    "Svarga",
    "Naraka (Hinduism)",
    "Patala",
]

# Buddhist Topics
BUDDHIST_TOPICS = [
    "Gautama Buddha",
    "Buddhism",
    "Buddhist mythology",
    "Bodhisattva",
    "Avalokiteśvara",
    "Maitreya",
    "Amitābha",
    "Vairocana",
    "Manjushri",
    "Ashoka",
    "Nagarjuna",
    "Xuanzang",

    # Concepts
    "Nirvana",
    "Karma",
    "Dharma",
    "Samsara",
    "Four Noble Truths",
    "Jataka tales",
]

# Historical Figures
HISTORICAL_FIGURES = [
    "Chandragupta Maurya",
    "Ashoka",
    "Chanakya",
    "Akbar",
    "Prithviraj Chauhan",
    "Rani Padmini",
    "Shivaji",
    "Rani of Jhansi",
    "Tipu Sultan",
    "Chandragupta II",
    "Samudragupta",
]


class IndianMythologyCollector:
    """
    Collector for Indian mythology and history.
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

    async def collect_topics(self, topics: List[str], category: str) -> List[dict]:
        """Collect Wikipedia articles for a list of topics."""
        articles = []

        for i, topic in enumerate(topics):
            safe_topic = topic.encode('ascii', 'replace').decode('ascii')
            print(f"    [{i+1}/{len(topics)}] {safe_topic}...")

            article = await self.get_wikipedia_article(topic)
            if article:
                article["topic_category"] = category
                articles.append(article)

            await asyncio.sleep(0.3)

        return articles

    async def collect_all(self):
        """Collect all Indian mythology and history data."""
        print("\n" + "=" * 60)
        print("Collecting Indian Mythology & History")
        print("=" * 60)

        all_articles = []

        # Hindu Deities
        print("\n[1/5] Collecting Hindu deities...")
        deities = await self.collect_topics(HINDU_DEITIES, "hindu_deity")
        all_articles.extend(deities)

        # Epic Characters
        print("\n[2/5] Collecting epic characters...")
        epics = await self.collect_topics(EPIC_CHARACTERS, "epic_character")
        all_articles.extend(epics)

        # Mythology Concepts
        print("\n[3/5] Collecting mythology concepts...")
        concepts = await self.collect_topics(MYTHOLOGY_CONCEPTS, "mythology_concept")
        all_articles.extend(concepts)

        # Buddhist
        print("\n[4/5] Collecting Buddhist topics...")
        buddhist = await self.collect_topics(BUDDHIST_TOPICS, "buddhist")
        all_articles.extend(buddhist)

        # Historical
        print("\n[5/5] Collecting historical figures...")
        historical = await self.collect_topics(HISTORICAL_FIGURES, "historical")
        all_articles.extend(historical)

        # Save all articles
        all_file = self.output_dir / "indian_wikipedia.json"
        with open(all_file, "w", encoding="utf-8") as f:
            json.dump(all_articles, f, indent=2, ensure_ascii=False)

        # Save by category
        by_category = {
            "hindu_deities": deities,
            "epic_characters": epics,
            "mythology_concepts": concepts,
            "buddhist": buddhist,
            "historical": historical,
        }

        cat_file = self.output_dir / "indian_by_category.json"
        with open(cat_file, "w", encoding="utf-8") as f:
            json.dump(by_category, f, indent=2, ensure_ascii=False)

        # FGO-relevant characters (quick reference)
        fgo_relevant = [
            "Arjuna", "Karna", "Rama", "Parvati", "Ganesha",
            "Ashwatthama", "Drona", "Lakshmi", "Hanuman",
            "Krishna", "Bhishma", "Parashurama", "Ravana",
        ]
        fgo_articles = [a for a in all_articles if a.get("title") in fgo_relevant]

        fgo_file = self.output_dir / "indian_fgo_servants.json"
        with open(fgo_file, "w", encoding="utf-8") as f:
            json.dump(fgo_articles, f, indent=2, ensure_ascii=False)

        # Save metadata
        metadata = {
            "source": "indian_mythology",
            "description": "Indian mythology for FGO LB4 Yuga Kshetra coverage",
            "total_articles": len(all_articles),
            "by_category": {
                "hindu_deities": len(deities),
                "epic_characters": len(epics),
                "mythology_concepts": len(concepts),
                "buddhist": len(buddhist),
                "historical": len(historical),
            },
            "fgo_relevant_count": len(fgo_articles),
            "license": "CC BY-SA 3.0",
            "fgo_relevance": [
                "Lostbelt 4: Yuga Kshetra",
                "Arjuna (Archer/Alter)",
                "Karna (Lancer)",
                "Rama (Saber)",
                "Parvati (Lancer)",
                "Ganesha (Moon Cancer)",
                "Ashwatthama (Archer)",
                "Lakshmi Bai (Saber)",
            ],
        }

        metadata_file = self.output_dir / "indian_metadata.json"
        with open(metadata_file, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)

        print(f"\nIndian mythology collection complete!")
        print(f"  Hindu Deities: {len(deities)}")
        print(f"  Epic Characters: {len(epics)}")
        print(f"  Mythology Concepts: {len(concepts)}")
        print(f"  Buddhist: {len(buddhist)}")
        print(f"  Historical: {len(historical)}")
        print(f"  Total: {len(all_articles)} articles")

    async def close(self):
        await self.client.aclose()


async def main():
    output_dir = Path("data/raw/indian_mythology")
    collector = IndianMythologyCollector(output_dir)

    try:
        await collector.collect_all()
    finally:
        await collector.close()


if __name__ == "__main__":
    asyncio.run(main())
