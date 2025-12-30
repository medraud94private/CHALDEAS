"""
BIBLIOTHECA AUGUSTANA Collector

Website: https://www.hs-augsburg.de/~harsch/augustana.html
Type: Digital library of classical and medieval texts

Contains:
- Latin texts (Encyclopaedia Encyclopaedia Encyclopaedia Encyclopaedia Encyclopaedia Encyclopaedia Encyclopaedia Encyclopaedia Latina)
- Greek texts (Encyclopaedia Encyclopaedia Encyclopaedia Encyclopaedia Encyclopaedia Encyclopaedia Encyclopaedia Encyclopaedia Encyclopaedia Graeca)
- Germanic texts
- Romance texts
- And more

License: Academic/educational use
Note: University of Augsburg project, be respectful of server load
"""
import httpx
import asyncio
from pathlib import Path
import json
from typing import Optional
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin


class BibliothecaAugustanaCollector:
    """
    Collector for BIBLIOTHECA AUGUSTANA.

    Focuses on Greek and Latin classical texts.
    """

    BASE_URL = "https://www.hs-augsburg.de/~harsch/augustana.html"
    GRAECA_URL = "https://www.hs-augsburg.de/~harsch/graeca/g_alpha.html"
    LATINA_URL = "https://www.hs-augsburg.de/~harsch/latina/l_alpha.html"

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
        self.metadata = {
            "graeca": [],
            "latina": [],
        }

    async def get_authors_list(self, index_url: str, language: str) -> list[dict]:
        """Get list of authors from an alphabetical index."""
        print(f"Fetching {language} authors index...")

        try:
            response = await self.client.get(index_url)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")

            authors = []
            for link in soup.find_all("a", href=True):
                href = link.get("href", "")
                text = link.get_text(strip=True)

                # Filter for author pages
                if text and href.endswith(".html") and not href.startswith("http"):
                    full_url = urljoin(index_url, href)

                    # Extract author name and dates if present
                    name, dates = self._parse_author_name(text)

                    authors.append({
                        "name": name,
                        "dates": dates,
                        "url": full_url,
                        "language": language,
                    })

            print(f"Found {len(authors)} {language} authors")
            return authors

        except Exception as e:
            print(f"Error fetching {language} index: {e}")
            return []

    def _parse_author_name(self, text: str) -> tuple[str, Optional[str]]:
        """Parse author name and dates from text like 'Cicero (106-43 a.C.)'."""
        # Match pattern: Name (dates)
        match = re.match(r"^(.+?)\s*\(([^)]+)\)\s*$", text)
        if match:
            return match.group(1).strip(), match.group(2).strip()
        return text.strip(), None

    async def get_author_works(self, author_url: str) -> list[dict]:
        """Get list of works for an author."""
        try:
            response = await self.client.get(author_url)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")

            works = []
            for link in soup.find_all("a", href=True):
                href = link.get("href", "")
                text = link.get_text(strip=True)

                if text and href.endswith(".html"):
                    full_url = urljoin(author_url, href)

                    works.append({
                        "title": text,
                        "url": full_url,
                    })

            return works

        except Exception as e:
            print(f"  Error fetching author works: {e}")
            return []

    async def collect_graeca_metadata(self):
        """Collect metadata for Greek texts."""
        authors = await self.get_authors_list(self.GRAECA_URL, "greek")

        for author in authors[:30]:  # Limit initial collection
            print(f"  {author['name']}...")

            works = await self.get_author_works(author["url"])

            for work in works:
                self.metadata["graeca"].append({
                    "author": author["name"],
                    "author_dates": author["dates"],
                    "title": work["title"],
                    "url": work["url"],
                    "language": "greek",
                    "source": "bibliotheca_augustana",
                })

            await asyncio.sleep(1)  # Rate limiting

        print(f"Collected {len(self.metadata['graeca'])} Greek work entries")

    async def collect_latina_metadata(self):
        """Collect metadata for Latin texts."""
        authors = await self.get_authors_list(self.LATINA_URL, "latin")

        for author in authors[:30]:  # Limit initial collection
            print(f"  {author['name']}...")

            works = await self.get_author_works(author["url"])

            for work in works:
                self.metadata["latina"].append({
                    "author": author["name"],
                    "author_dates": author["dates"],
                    "title": work["title"],
                    "url": work["url"],
                    "language": "latin",
                    "source": "bibliotheca_augustana",
                })

            await asyncio.sleep(1)

        print(f"Collected {len(self.metadata['latina'])} Latin work entries")

    async def collect_all_metadata(self):
        """Collect metadata from all language sections."""
        print("\n" + "=" * 60)
        print("Collecting from BIBLIOTHECA AUGUSTANA")
        print("=" * 60)

        print("\nCollecting Greek texts...")
        await self.collect_graeca_metadata()

        print("\nCollecting Latin texts...")
        await self.collect_latina_metadata()

        # Save metadata
        await self._save_metadata()

    async def _save_metadata(self):
        """Save collected metadata."""
        # Save Greek metadata
        graeca_file = self.output_dir / "augustana_graeca.json"
        with open(graeca_file, "w", encoding="utf-8") as f:
            json.dump(self.metadata["graeca"], f, indent=2, ensure_ascii=False)

        # Save Latin metadata
        latina_file = self.output_dir / "augustana_latina.json"
        with open(latina_file, "w", encoding="utf-8") as f:
            json.dump(self.metadata["latina"], f, indent=2, ensure_ascii=False)

        # Save combined
        combined_file = self.output_dir / "augustana_all.json"
        all_texts = self.metadata["graeca"] + self.metadata["latina"]
        with open(combined_file, "w", encoding="utf-8") as f:
            json.dump(all_texts, f, indent=2, ensure_ascii=False)

        print(f"\nSaved metadata:")
        print(f"  Greek: {len(self.metadata['graeca'])} entries → {graeca_file.name}")
        print(f"  Latin: {len(self.metadata['latina'])} entries → {latina_file.name}")
        print(f"  Combined: {len(all_texts)} entries → {combined_file.name}")

    async def get_text_content(self, url: str) -> Optional[str]:
        """Get actual text content from a work page."""
        try:
            response = await self.client.get(url)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")

            # Remove scripts and styles
            for element in soup.find_all(["script", "style"]):
                element.decompose()

            # Get body text
            body = soup.find("body")
            if body:
                text = body.get_text(separator="\n")
                text = re.sub(r"\n{3,}", "\n\n", text)
                return text.strip()

        except Exception as e:
            print(f"Error fetching {url}: {e}")

        return None

    async def close(self):
        await self.client.aclose()


# Priority Greek authors (pre-Socratic to Hellenistic)
PRIORITY_GREEK_AUTHORS = [
    "homer",
    "hesiod",
    "herodotus",
    "thucydides",
    "plato",
    "aristotle",
    "xenophon",
    "plutarch",
    "sophocles",
    "euripides",
    "aeschylus",
    "aristophanes",
]

# Priority Latin authors
PRIORITY_LATIN_AUTHORS = [
    "cicero",
    "vergil",
    "caesar",
    "livy",
    "tacitus",
    "seneca",
    "ovid",
    "horace",
]


async def main():
    """Main entry point."""
    output_dir = Path("data/raw/augustana")
    collector = BibliothecaAugustanaCollector(output_dir)

    try:
        await collector.collect_all_metadata()
    finally:
        await collector.close()


if __name__ == "__main__":
    asyncio.run(main())
