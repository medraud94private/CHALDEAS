"""
Sacred-Texts.com Collector

Website: https://sacred-texts.com/
Type: Internet Sacred Text Archive

Contains:
- Religious texts from all major religions
- Mythology and folklore from around the world
- Ancient wisdom literature
- Esoteric and occult texts

License: Public domain texts freely available
Note: Large archive - collect selectively
"""
import httpx
import asyncio
from pathlib import Path
import json
from typing import Optional
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import re


class SacredTextsCollector:
    """
    Collector for Sacred-Texts.com archive.

    Focuses on mythology, ancient religion, and historical texts
    relevant to CHALDEAS.
    """

    BASE_URL = "https://sacred-texts.com"

    # Key categories relevant to historical/mythological knowledge
    CATEGORIES = {
        # Classical
        "classics": "/cla/index.htm",  # Classical Paganism
        "greek": "/cla/gpr/index.htm",  # Greek Popular Religion

        # Mythology
        "celtic": "/neu/celt/index.htm",  # Celtic
        "norse": "/neu/ice/index.htm",  # Icelandic/Norse

        # Ancient Near East
        "ane": "/ane/index.htm",  # Ancient Near East
        "egypt": "/egy/index.htm",  # Egypt
        "mesopotamia": "/ane/mba/index.htm",  # Myths of Babylonia

        # Asian
        "hinduism": "/hin/index.htm",  # Hinduism
        "buddhism": "/bud/index.htm",  # Buddhism
        "confucianism": "/cfu/index.htm",  # Confucianism
        "taoism": "/tao/index.htm",  # Taoism
        "shinto": "/shi/index.htm",  # Shinto

        # Abrahamic
        "bible": "/bib/index.htm",  # Bible
        "apocrypha": "/chr/apo/index.htm",  # Apocrypha
        "judaism": "/jud/index.htm",  # Judaism
        "islam": "/isl/index.htm",  # Islam

        # Other
        "zoroastrianism": "/zor/index.htm",  # Zoroastrianism
        "legends": "/etc/index.htm",  # Legends and Sagas
    }

    # Specific important texts to collect metadata for
    IMPORTANT_TEXTS = [
        # Greek/Roman
        ("/cla/homer/ili/index.htm", "Iliad"),
        ("/cla/homer/ody/index.htm", "Odyssey"),
        ("/cla/hesiod/theogony.htm", "Theogony"),
        ("/cla/ovid/meta/index.htm", "Metamorphoses"),
        ("/cla/virgil/aen/index.htm", "Aeneid"),

        # Norse
        ("/neu/poe/index.htm", "Poetic Edda"),
        ("/neu/pre/index.htm", "Prose Edda"),

        # Celtic
        ("/neu/celt/cg1/index.htm", "Celtic Gods"),

        # Egyptian
        ("/egy/ebod/index.htm", "Egyptian Book of the Dead"),

        # Mesopotamian
        ("/ane/gilgamesh.htm", "Epic of Gilgamesh"),
        ("/ane/enuma.htm", "Enuma Elish"),

        # Hindu
        ("/hin/maha/index.htm", "Mahabharata"),
        ("/hin/rama/index.htm", "Ramayana"),
        ("/hin/rigveda/index.htm", "Rig Veda"),
        ("/hin/bgs/index.htm", "Bhagavad Gita"),

        # Buddhist
        ("/bud/sbe10/index.htm", "Dhammapada"),

        # Chinese
        ("/tao/taote.htm", "Tao Te Ching"),
        ("/cfu/conf1.htm", "Confucian Analects"),

        # Japanese
        ("/shi/kj/index.htm", "Kojiki"),

        # Zoroastrian
        ("/zor/sbe05/index.htm", "Avesta"),

        # Biblical/Apocryphal
        ("/chr/apo/jasher/index.htm", "Book of Jasher"),
        ("/chr/apo/enoch/index.htm", "Book of Enoch"),
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
        self.texts_catalog = []

    async def get_page(self, url: str) -> Optional[BeautifulSoup]:
        """Fetch and parse a page."""
        try:
            response = await self.client.get(url)
            response.raise_for_status()
            return BeautifulSoup(response.text, "html.parser")
        except Exception as e:
            print(f"  Error fetching {url}: {e}")
            return None

    async def collect_category_index(self, category: str, path: str):
        """Collect text listings from a category index page."""
        url = urljoin(self.BASE_URL, path)
        print(f"  Fetching {category} index...")

        soup = await self.get_page(url)
        if not soup:
            return []

        texts = []

        # Find all links to texts
        for link in soup.find_all("a", href=True):
            href = link.get("href", "")
            text = link.get_text(strip=True)

            # Filter for text pages
            if text and len(text) > 3:
                # Skip navigation links
                if text.lower() in ["home", "index", "next", "prev", "back"]:
                    continue

                full_url = urljoin(url, href)

                # Only include internal links
                if full_url.startswith(self.BASE_URL):
                    texts.append({
                        "title": text,
                        "url": full_url,
                        "category": category,
                        "source": "sacred-texts",
                    })

        await asyncio.sleep(0.5)  # Rate limiting
        return texts

    async def collect_important_texts_metadata(self):
        """Collect metadata for important texts."""
        print("\nCollecting metadata for important texts...")

        for path, title in self.IMPORTANT_TEXTS:
            url = urljoin(self.BASE_URL, path)
            print(f"  {title}...")

            soup = await self.get_page(url)

            entry = {
                "title": title,
                "url": url,
                "path": path,
                "source": "sacred-texts",
                "available": soup is not None,
            }

            if soup:
                # Try to get description
                meta_desc = soup.find("meta", {"name": "description"})
                if meta_desc:
                    entry["description"] = meta_desc.get("content", "")

                # Count chapters/sections
                links = soup.find_all("a", href=True)
                entry["sections_count"] = len([l for l in links if l.get("href", "").endswith(".htm")])

            self.texts_catalog.append(entry)
            await asyncio.sleep(0.5)

    async def collect_all_categories(self):
        """Collect index of all category pages."""
        print("\nCollecting category indexes...")

        all_texts = []
        for category, path in self.CATEGORIES.items():
            texts = await self.collect_category_index(category, path)
            all_texts.extend(texts)
            print(f"    {category}: {len(texts)} entries")

        # Remove duplicates
        seen_urls = set()
        unique_texts = []
        for text in all_texts:
            if text["url"] not in seen_urls:
                seen_urls.add(text["url"])
                unique_texts.append(text)

        print(f"Total unique texts found: {len(unique_texts)}")

        # Save category index
        index_file = self.output_dir / "sacred_texts_index.json"
        with open(index_file, "w", encoding="utf-8") as f:
            json.dump(unique_texts, f, indent=2, ensure_ascii=False)

        return unique_texts

    async def collect_all(self):
        """Collect all available Sacred-Texts data."""
        print("\n" + "=" * 60)
        print("Collecting from Sacred-Texts.com")
        print("=" * 60)

        # Collect category indexes
        await self.collect_all_categories()

        # Collect important texts metadata
        await self.collect_important_texts_metadata()

        # Save important texts catalog
        catalog_file = self.output_dir / "sacred_texts_important.json"
        with open(catalog_file, "w", encoding="utf-8") as f:
            json.dump(self.texts_catalog, f, indent=2, ensure_ascii=False)

        # Save metadata
        metadata = {
            "source": "sacred-texts",
            "url": self.BASE_URL,
            "description": "Internet Sacred Text Archive - religious and mythological texts",
            "categories": list(self.CATEGORIES.keys()),
            "important_texts_count": len(self.texts_catalog),
            "license": "Public domain",
        }

        metadata_file = self.output_dir / "sacred_texts_metadata.json"
        with open(metadata_file, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)

        print("\nSacred-Texts collection complete!")

    async def close(self):
        await self.client.aclose()


async def main():
    """Main entry point."""
    output_dir = Path("data/raw/sacred_texts")
    collector = SacredTextsCollector(output_dir)

    try:
        await collector.collect_all()
    finally:
        await collector.close()


if __name__ == "__main__":
    asyncio.run(main())
