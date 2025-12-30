"""
The Latin Library Collector

Website: https://www.thelatinlibrary.com/
Type: Collection of Latin texts

Contains:
- Classical Latin authors (Cicero, Vergil, Ovid, etc.)
- Medieval Latin texts
- Neo-Latin works

License: Educational use (check terms)
Note: Be respectful of server load, add delays between requests
"""
import httpx
import asyncio
from pathlib import Path
import json
from typing import Optional
from bs4 import BeautifulSoup
import re


class LatinLibraryCollector:
    """
    Collector for The Latin Library.

    Extracts Latin texts organized by author.
    """

    BASE_URL = "https://www.thelatinlibrary.com"

    # Major classical authors to prioritize
    PRIORITY_AUTHORS = [
        "cicero",
        "vergil",
        "ovid",
        "horace",
        "caesar",
        "livy",
        "tacitus",
        "sallust",
        "seneca",
        "pliny",
        "juvenal",
        "martial",
        "lucretius",
        "catullus",
        "plautus",
        "terence",
    ]

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.client = httpx.AsyncClient(
            timeout=60.0,
            follow_redirects=True,
            headers={
                "User-Agent": "CHALDEAS/0.1 (Historical Knowledge System; Educational Use)"
            }
        )
        self.collected_texts = []

    async def get_index(self) -> list[dict]:
        """Get the main index of available texts."""
        print("Fetching Latin Library index...")

        response = await self.client.get(self.BASE_URL)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        # Find author links
        authors = []
        for link in soup.find_all("a", href=True):
            href = link.get("href", "")

            # Filter for author pages (typically name.html or directories)
            if href.endswith(".html") and not href.startswith("http"):
                author_name = href.replace(".html", "")
                if author_name and "/" not in author_name:
                    authors.append({
                        "name": author_name.title(),
                        "slug": author_name.lower(),
                        "url": f"{self.BASE_URL}/{href}",
                    })

        print(f"Found {len(authors)} authors/sections")
        return authors

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

                if href.endswith(".html") and text:
                    # Build full URL
                    if href.startswith("http"):
                        work_url = href
                    elif href.startswith("/"):
                        work_url = f"{self.BASE_URL}{href}"
                    else:
                        # Relative to author page
                        base = "/".join(author_url.rsplit("/", 1)[:-1])
                        work_url = f"{base}/{href}"

                    works.append({
                        "title": text,
                        "url": work_url,
                    })

            return works

        except Exception as e:
            print(f"  Error fetching {author_url}: {e}")
            return []

    async def get_text_content(self, url: str) -> Optional[str]:
        """Get the actual text content from a page."""
        try:
            response = await self.client.get(url)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")

            # Remove navigation elements
            for nav in soup.find_all(["script", "style", "nav"]):
                nav.decompose()

            # Get main text (usually in body or a specific div)
            body = soup.find("body")
            if body:
                # Clean up and extract text
                text = body.get_text(separator="\n")

                # Remove excessive whitespace
                text = re.sub(r"\n{3,}", "\n\n", text)
                text = text.strip()

                return text

        except Exception as e:
            print(f"  Error fetching text from {url}: {e}")

        return None

    async def collect_priority_authors(self, limit_per_author: int = 5):
        """Collect texts from priority authors only."""
        print("\n" + "=" * 60)
        print("Collecting from The Latin Library (Priority Authors)")
        print("=" * 60)

        authors_index = await self.get_index()

        for author in authors_index:
            slug = author["slug"]

            if slug not in self.PRIORITY_AUTHORS:
                continue

            print(f"\nCollecting {author['name']}...")

            works = await self.get_author_works(author["url"])
            collected = 0

            for work in works[:limit_per_author]:
                print(f"  - {work['title'][:50]}...")

                text = await self.get_text_content(work["url"])

                if text and len(text) > 100:
                    self.collected_texts.append({
                        "author": author["name"],
                        "author_slug": slug,
                        "title": work["title"],
                        "url": work["url"],
                        "text": text,
                        "language": "latin",
                        "source": "latin_library",
                    })
                    collected += 1

                # Rate limiting - be respectful
                await asyncio.sleep(2)

            print(f"  Collected {collected} texts from {author['name']}")

        # Save collected texts
        await self._save_texts()

    async def collect_metadata_only(self):
        """Collect only metadata (authors and work titles), not full texts."""
        print("\n" + "=" * 60)
        print("Collecting Latin Library Metadata")
        print("=" * 60)

        authors_index = await self.get_index()
        metadata = []

        for author in authors_index[:50]:  # Limit for initial run
            print(f"  {author['name']}...")

            works = await self.get_author_works(author["url"])

            for work in works:
                metadata.append({
                    "author": author["name"],
                    "author_slug": author["slug"],
                    "title": work["title"],
                    "url": work["url"],
                    "language": "latin",
                    "source": "latin_library",
                })

            await asyncio.sleep(1)

        # Save metadata
        output_file = self.output_dir / "latin_library_metadata.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        print(f"\nSaved {len(metadata)} work entries to {output_file}")

    async def _save_texts(self):
        """Save collected texts."""
        # Save as JSON index
        index_file = self.output_dir / "latin_library_index.json"
        index_data = [
            {k: v for k, v in text.items() if k != "text"}
            for text in self.collected_texts
        ]
        with open(index_file, "w", encoding="utf-8") as f:
            json.dump(index_data, f, indent=2, ensure_ascii=False)

        # Save individual text files
        texts_dir = self.output_dir / "texts"
        texts_dir.mkdir(exist_ok=True)

        for text in self.collected_texts:
            filename = f"{text['author_slug']}_{self._slugify(text['title'])}.txt"
            filepath = texts_dir / filename
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(f"# {text['title']}\n")
                f.write(f"# Author: {text['author']}\n")
                f.write(f"# Source: {text['url']}\n")
                f.write(f"# Language: Latin\n\n")
                f.write(text["text"])

        print(f"\nSaved {len(self.collected_texts)} texts")

    def _slugify(self, text: str) -> str:
        """Create a safe filename from text."""
        slug = text.lower()
        slug = re.sub(r"[^a-z0-9]+", "_", slug)
        slug = slug.strip("_")[:50]
        return slug or "untitled"

    async def close(self):
        await self.client.aclose()


# Important Latin texts to prioritize
IMPORTANT_WORKS = {
    "cicero": ["de_officiis", "de_republica", "orationes", "letters"],
    "vergil": ["aeneid", "georgics", "eclogues"],
    "caesar": ["gallic_war", "civil_war"],
    "livy": ["ab_urbe_condita"],
    "tacitus": ["annals", "histories", "germania"],
    "ovid": ["metamorphoses", "fasti"],
    "horace": ["odes", "satires", "ars_poetica"],
}


async def main():
    """Main entry point."""
    output_dir = Path("data/raw/latin_library")
    collector = LatinLibraryCollector(output_dir)

    try:
        # Start with metadata only (faster, less load)
        await collector.collect_metadata_only()

        # Then collect priority authors
        # await collector.collect_priority_authors(limit_per_author=3)
    finally:
        await collector.close()


if __name__ == "__main__":
    asyncio.run(main())
