"""
Project Gutenberg Collector

Website: https://www.gutenberg.org/
Data: https://www.gutenberg.org/cache/epub/feeds/

Data includes:
- 60,000+ public domain ebooks
- Literature from all periods and regions

License: Public Domain (mostly)
"""
import httpx
import asyncio
from pathlib import Path
from typing import Optional
import json
import csv
from io import StringIO


class GutenbergCollector:
    """
    Collector for Project Gutenberg.

    Uses the Gutenberg catalog and direct file downloads.
    """

    CATALOG_URL = "https://www.gutenberg.org/cache/epub/feeds/pg_catalog.csv"
    BOOK_URL_TEMPLATE = "https://www.gutenberg.org/cache/epub/{book_id}/pg{book_id}.txt"

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.client = httpx.AsyncClient(timeout=60.0, follow_redirects=True)

    async def download_catalog(self) -> list[dict]:
        """Download the full Gutenberg catalog."""
        print("Downloading Gutenberg catalog...")
        response = await self.client.get(self.CATALOG_URL)
        response.raise_for_status()

        # Parse CSV
        reader = csv.DictReader(StringIO(response.text))
        catalog = list(reader)

        # Save catalog
        catalog_path = self.output_dir / "gutenberg_catalog.json"
        with open(catalog_path, "w", encoding="utf-8") as f:
            json.dump(catalog, f, indent=2)

        print(f"Catalog saved: {len(catalog)} books")
        return catalog

    async def get_book(self, book_id: int) -> Optional[str]:
        """Download a book's text."""
        url = self.BOOK_URL_TEMPLATE.format(book_id=book_id)
        try:
            response = await self.client.get(url)
            response.raise_for_status()
            return response.text
        except Exception as e:
            print(f"Error fetching book {book_id}: {e}")
            return None

    async def collect_historical_texts(self, limit: int = 1000):
        """
        Collect historically significant texts.

        Filters for history, philosophy, and classical literature.
        """
        catalog = await self.download_catalog()

        # Filter for relevant subjects
        relevant_subjects = [
            "history",
            "philosophy",
            "ancient",
            "classical",
            "mythology",
            "greece",
            "rome",
            "china",
            "egypt",
        ]

        filtered = []
        for book in catalog:
            subjects = book.get("Subjects", "").lower()
            if any(s in subjects for s in relevant_subjects):
                filtered.append(book)

        print(f"Found {len(filtered)} relevant books")

        # Collect limited number
        downloaded = 0
        skipped = 0
        for book in filtered[:limit]:
            book_id = book.get("Text#")
            title = book.get("Title", "Unknown")

            if not book_id:
                continue

            output_file = self.output_dir / f"pg{book_id}.txt"

            # Skip if already downloaded
            if output_file.exists():
                skipped += 1
                continue

            # Safe print (handle unicode issues on Windows)
            safe_title = title[:50].encode('ascii', 'replace').decode('ascii')
            print(f"[{downloaded+skipped+1}/{min(limit, len(filtered))}] Downloading: {safe_title}...")

            text = await self.get_book(int(book_id))

            if text:
                with open(output_file, "w", encoding="utf-8") as f:
                    f.write(text)
                downloaded += 1

            # Rate limiting
            await asyncio.sleep(0.5)

        print(f"Downloaded: {downloaded}, Skipped (existing): {skipped}")

    async def close(self):
        await self.client.aclose()


# Important historical texts on Gutenberg
IMPORTANT_BOOKS = [
    (28, "The Republic by Plato"),
    (1497, "The Republic by Plato (Jowett)"),
    (1656, "Apology by Plato"),
    (1727, "The Odyssey by Homer"),
    (6130, "The Iliad by Homer"),
    (2680, "Meditations by Marcus Aurelius"),
    (10615, "The Art of War by Sun Tzu"),
    (1232, "The Prince by Machiavelli"),
    (46, "A Christmas Carol by Dickens"),  # Popular reference
    (1342, "Pride and Prejudice"),  # Popular reference
    (2600, "War and Peace"),
]


async def main():
    """Main entry point for Gutenberg collection."""
    output_dir = Path("data/raw/gutenberg")
    collector = GutenbergCollector(output_dir)

    try:
        await collector.collect_historical_texts(limit=100)
    finally:
        await collector.close()


if __name__ == "__main__":
    asyncio.run(main())
