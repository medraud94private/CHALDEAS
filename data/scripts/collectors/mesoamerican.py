"""
Mesoamerican Mythology & History Collector

Sources:
- Wikipedia API (primary)

Contains:
- Aztec mythology and history
- Maya mythology and history
- Inca mythology and history
- Olmec, Toltec civilizations

License: CC BY-SA 3.0
"""
import httpx
import asyncio
from pathlib import Path
import json
from typing import Optional, List


# Aztec Topics (FGO LB7 Nahui Mictlan focus)
AZTEC_TOPICS = [
    # Major Deities
    "Quetzalcoatl",
    "Tezcatlipoca",
    "Huitzilopochtli",
    "Tlaloc",
    "Xipe Totec",
    "Mictlantecuhtli",
    "Mictecacihuatl",
    "Chalchiuhtlicue",
    "Coatlicue",
    "Tonatiuh",
    "Xochiquetzal",
    "Tlazolteotl",
    "Xiuhtecuhtli",
    "Ehecatl",
    "Mixcoatl",
    "Xolotl",
    "Itzpapalotl",

    # Mythology Concepts
    "Aztec mythology",
    "Aztec calendar",
    "Mictlan",
    "Xibalba",
    "Five Suns (Aztec mythology)",
    "Aztec creation myth",
    "Nahuatl",
    "Toltec",

    # Historical Figures
    "Montezuma II",
    "Cuauhtémoc",
    "Hernán Cortés",
    "La Malinche",
    "Nezahualcoyotl",

    # Places
    "Tenochtitlan",
    "Teotihuacan",
    "Chichen Itza",
    "Templo Mayor",

    # Creatures
    "Ahuizotl",
    "Cipactli",
    "Nagual",
    "Tzitzimime",
]

# Maya Topics
MAYA_TOPICS = [
    # Deities
    "Maya mythology",
    "Itzamna",
    "Kukulkan",
    "Chaac",
    "Ah Puch",
    "Ixchel",
    "Hunab Ku",
    "Kinich Ahau",
    "Yum Kaax",
    "Ix Tab",

    # Mythology
    "Popol Vuh",
    "Hero Twins",
    "Maya creation myth",
    "Maya calendar",
    "Xibalba",

    # History
    "Maya civilization",
    "K'inich Janaab Pakal",
    "Maya script",

    # Places
    "Tikal",
    "Palenque",
    "Uxmal",
    "Copán",
]

# Inca Topics
INCA_TOPICS = [
    # Deities
    "Inca mythology",
    "Inti",
    "Viracocha",
    "Mama Quilla",
    "Pachamama",
    "Supay",
    "Illapa",
    "Mama Cocha",

    # Historical Figures
    "Pachacuti",
    "Atahualpa",
    "Huayna Capac",
    "Manco Inca Yupanqui",
    "Tupac Amaru",
    "Francisco Pizarro",

    # Empire
    "Inca Empire",
    "Inca civilization",
    "Quechua people",
    "Inca road system",

    # Places
    "Cusco",
    "Machu Picchu",
    "Sacsayhuamán",
]

# Additional Topics
ADDITIONAL_TOPICS = [
    # Olmec
    "Olmec",
    "Olmec colossal heads",

    # General
    "Mesoamerica",
    "Mesoamerican chronology",
    "Pre-Columbian era",
    "Spanish conquest of the Aztec Empire",
    "Spanish conquest of the Inca Empire",
    "Human sacrifice in Aztec culture",
    "Aztec warfare",
    "Jaguar warrior",
    "Eagle warrior",
    "Obsidian",
    "Macuahuitl",
]


class MesoamericanCollector:
    """
    Collector for Mesoamerican (Aztec, Maya, Inca) mythology and history.
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
                article["civilization"] = category
                articles.append(article)

            await asyncio.sleep(0.3)

        return articles

    async def collect_all(self):
        """Collect all Mesoamerican data."""
        print("\n" + "=" * 60)
        print("Collecting Mesoamerican Mythology & History")
        print("=" * 60)

        all_articles = []

        # Aztec
        print("\n[1/4] Collecting Aztec topics...")
        aztec = await self.collect_topics(AZTEC_TOPICS, "aztec")
        all_articles.extend(aztec)

        # Maya
        print("\n[2/4] Collecting Maya topics...")
        maya = await self.collect_topics(MAYA_TOPICS, "maya")
        all_articles.extend(maya)

        # Inca
        print("\n[3/4] Collecting Inca topics...")
        inca = await self.collect_topics(INCA_TOPICS, "inca")
        all_articles.extend(inca)

        # Additional
        print("\n[4/4] Collecting additional topics...")
        additional = await self.collect_topics(ADDITIONAL_TOPICS, "general")
        all_articles.extend(additional)

        # Save all articles
        all_file = self.output_dir / "mesoamerican_wikipedia.json"
        with open(all_file, "w", encoding="utf-8") as f:
            json.dump(all_articles, f, indent=2, ensure_ascii=False)

        # Save by civilization
        by_civ = {
            "aztec": aztec,
            "maya": maya,
            "inca": inca,
            "general": additional,
        }

        civ_file = self.output_dir / "mesoamerican_by_civilization.json"
        with open(civ_file, "w", encoding="utf-8") as f:
            json.dump(by_civ, f, indent=2, ensure_ascii=False)

        # Extract deities for quick reference
        deities = [a for a in all_articles
                   if any(k in " ".join(a.get("categories", [])).lower()
                          for k in ["deity", "god", "goddess", "mythology"])]

        deities_file = self.output_dir / "mesoamerican_deities.json"
        with open(deities_file, "w", encoding="utf-8") as f:
            json.dump(deities, f, indent=2, ensure_ascii=False)

        # Save metadata
        metadata = {
            "source": "mesoamerican",
            "description": "Mesoamerican mythology for FGO LB7 Nahui Mictlan coverage",
            "total_articles": len(all_articles),
            "by_civilization": {
                "aztec": len(aztec),
                "maya": len(maya),
                "inca": len(inca),
                "general": len(additional),
            },
            "deities_count": len(deities),
            "license": "CC BY-SA 3.0",
            "fgo_relevance": [
                "Lostbelt 7: Nahui Mictlan",
                "Quetzalcoatl (Rider)",
                "Jaguar Warrior (Lancer)",
                "Tezcatlipoca",
                "ORT (Type Mercury connection)",
            ],
        }

        metadata_file = self.output_dir / "mesoamerican_metadata.json"
        with open(metadata_file, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)

        print(f"\nMesoamerican collection complete!")
        print(f"  Aztec: {len(aztec)} articles")
        print(f"  Maya: {len(maya)} articles")
        print(f"  Inca: {len(inca)} articles")
        print(f"  General: {len(additional)} articles")
        print(f"  Total: {len(all_articles)} articles")

    async def close(self):
        await self.client.aclose()


async def main():
    output_dir = Path("data/raw/mesoamerican")
    collector = MesoamericanCollector(output_dir)

    try:
        await collector.collect_all()
    finally:
        await collector.close()


if __name__ == "__main__":
    asyncio.run(main())
