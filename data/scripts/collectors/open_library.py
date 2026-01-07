"""
Open Library Bulk Collector

Website: https://openlibrary.org/
Bulk Data: https://openlibrary.org/data
API: https://openlibrary.org/developers/api

Open Library is part of Internet Archive, providing:
- Millions of book metadata records
- Full text access for public domain books
- Structured bibliographic data

License: Public Domain / CC0
"""
import httpx
import asyncio
from pathlib import Path
import json
import gzip
from typing import Optional, Iterator
from datetime import datetime


def safe_print(text: str):
    """Print text safely, handling encoding issues on Windows."""
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode('ascii', 'replace').decode('ascii'))


class OpenLibraryCollector:
    """
    Collector for Open Library bulk data.

    Downloads and processes:
    - Works dump (book metadata)
    - Authors dump (author information)
    - Editions dump (specific editions)
    """

    # Bulk data URLs
    DUMPS_URL = "https://openlibrary.org/data"
    WORKS_DUMP_URL = "https://openlibrary.org/data/ol_dump_works_latest.txt.gz"
    AUTHORS_DUMP_URL = "https://openlibrary.org/data/ol_dump_authors_latest.txt.gz"
    EDITIONS_DUMP_URL = "https://openlibrary.org/data/ol_dump_editions_latest.txt.gz"

    # API endpoints
    SEARCH_API = "https://openlibrary.org/search.json"
    WORKS_API = "https://openlibrary.org/works/{olid}.json"
    AUTHORS_API = "https://openlibrary.org/authors/{olid}.json"

    # Historical subjects to filter
    HISTORICAL_SUBJECTS = [
        "history", "philosophy", "classical", "ancient", "mythology",
        "greece", "rome", "egypt", "mesopotamia", "persia",
        "medieval", "renaissance", "enlightenment",
        "religion", "theology", "ethics", "metaphysics",
        "biography", "autobiography",
        "science history", "mathematics history",
        "literature", "poetry", "drama", "epic",
        "war", "military history", "political history",
        "archaeology", "anthropology"
    ]

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.client = httpx.AsyncClient(
            timeout=300.0,
            follow_redirects=True,
            headers={
                "User-Agent": "CHALDEAS/0.1 (Historical Knowledge System; contact@example.com)"
            }
        )

    async def search_historical_books(self, subject: str, limit: int = 100) -> list[dict]:
        """Search for books by historical subject."""
        try:
            response = await self.client.get(
                self.SEARCH_API,
                params={
                    "subject": subject,
                    "limit": limit,
                    "fields": "key,title,author_name,first_publish_year,subject,language"
                }
            )
            response.raise_for_status()
            data = response.json()
            return data.get("docs", [])
        except Exception as e:
            print(f"  Error searching {subject}: {e}")
            return []

    async def get_work_details(self, olid: str) -> Optional[dict]:
        """Get detailed work information."""
        try:
            response = await self.client.get(
                self.WORKS_API.format(olid=olid)
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"  Error getting work {olid}: {e}")
            return None

    async def collect_by_subjects(self, limit_per_subject: int = 500) -> list[dict]:
        """
        Collect historical books by searching subjects.

        This uses the API rather than bulk dumps for targeted collection.
        """
        all_books = []
        seen_keys = set()

        for subject in self.HISTORICAL_SUBJECTS:
            safe_print(f"  Searching: {subject}...")
            books = await self.search_historical_books(subject, limit_per_subject)

            for book in books:
                key = book.get("key", "")
                if key and key not in seen_keys:
                    seen_keys.add(key)
                    all_books.append({
                        "olid": key.replace("/works/", ""),
                        "title": book.get("title"),
                        "authors": book.get("author_name", []),
                        "first_publish_year": book.get("first_publish_year"),
                        "subjects": book.get("subject", [])[:10],
                        "languages": book.get("language", []),
                        "source": "open_library"
                    })

            safe_print(f"    Found {len(books)} books")
            await asyncio.sleep(1)  # Rate limiting

        return all_books

    async def download_bulk_dump(self, url: str, output_file: Path) -> bool:
        """
        Download a compressed bulk dump file.

        Note: These files are very large (GBs). Use with caution.
        """
        print(f"Downloading: {url}")
        print(f"  This may take a long time for large files...")

        try:
            async with self.client.stream("GET", url) as response:
                response.raise_for_status()
                total = int(response.headers.get("content-length", 0))

                with open(output_file, "wb") as f:
                    downloaded = 0
                    async for chunk in response.aiter_bytes(chunk_size=8192):
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total:
                            pct = (downloaded / total) * 100
                            print(f"\r  Progress: {pct:.1f}% ({downloaded:,} / {total:,} bytes)", end="")

                print(f"\n  Saved to: {output_file}")
                return True
        except Exception as e:
            print(f"  Error downloading: {e}")
            return False

    def parse_dump_line(self, line: str) -> Optional[dict]:
        """Parse a line from OpenLibrary dump file."""
        try:
            parts = line.strip().split("\t")
            if len(parts) >= 5:
                # Format: type, key, revision, last_modified, json_data
                return json.loads(parts[4])
        except:
            pass
        return None

    def filter_historical_work(self, work: dict) -> bool:
        """Check if a work is historically relevant."""
        subjects = work.get("subjects", [])
        if isinstance(subjects, list):
            subjects_str = " ".join(
                s.get("name", s) if isinstance(s, dict) else str(s)
                for s in subjects
            ).lower()
        else:
            subjects_str = str(subjects).lower()

        return any(hs in subjects_str for hs in self.HISTORICAL_SUBJECTS)

    async def process_works_dump(self, dump_file: Path, output_file: Path, max_items: int = 100000):
        """
        Process a downloaded works dump to extract historical works.

        This filters the massive dump file to keep only relevant works.
        """
        print(f"Processing works dump: {dump_file}")
        historical_works = []
        processed = 0

        opener = gzip.open if str(dump_file).endswith('.gz') else open

        with opener(dump_file, 'rt', encoding='utf-8', errors='ignore') as f:
            for line in f:
                work = self.parse_dump_line(line)
                if work and self.filter_historical_work(work):
                    historical_works.append({
                        "olid": work.get("key", "").replace("/works/", ""),
                        "title": work.get("title"),
                        "subjects": work.get("subjects", [])[:10],
                        "description": work.get("description", {}).get("value") if isinstance(work.get("description"), dict) else work.get("description"),
                        "first_publish_date": work.get("first_publish_date"),
                        "source": "open_library_dump"
                    })

                    if len(historical_works) >= max_items:
                        break

                processed += 1
                if processed % 100000 == 0:
                    print(f"  Processed {processed:,} records, found {len(historical_works):,} historical works")

        print(f"  Total historical works found: {len(historical_works):,}")

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(historical_works, f, indent=2, ensure_ascii=False)

        return historical_works

    async def collect_all(self, use_api: bool = True, limit_per_subject: int = 500):
        """
        Collect historical books from Open Library.

        Args:
            use_api: If True, use Search API (faster, targeted)
                    If False, download and process bulk dumps (complete but slow)
            limit_per_subject: Max books per subject when using API
        """
        print("\n" + "=" * 60)
        print("Collecting from Open Library")
        print("=" * 60)

        if use_api:
            # Use API for targeted collection
            print("Using Search API for targeted collection...")
            books = await self.collect_by_subjects(limit_per_subject)

            output_file = self.output_dir / "open_library_historical.json"
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(books, f, indent=2, ensure_ascii=False)

            # Save metadata
            metadata = {
                "source": "Open Library",
                "url": "https://openlibrary.org/",
                "license": "Public Domain / CC0",
                "collection_date": datetime.now().isoformat(),
                "method": "Search API",
                "subjects_searched": self.HISTORICAL_SUBJECTS,
                "total_books": len(books)
            }

            metadata_file = self.output_dir / "open_library_metadata.json"
            with open(metadata_file, "w", encoding="utf-8") as f:
                json.dump(metadata, f, indent=2)

            print(f"\nCollected {len(books)} historical books")
            print(f"Saved to: {output_file}")
        else:
            # Download bulk dumps (warning: very large files)
            print("Downloading bulk dumps (this will take a long time)...")

            works_file = self.output_dir / "ol_dump_works.txt.gz"
            if await self.download_bulk_dump(self.WORKS_DUMP_URL, works_file):
                output_file = self.output_dir / "open_library_works_historical.json"
                await self.process_works_dump(works_file, output_file)

    async def close(self):
        await self.client.aclose()


async def main():
    """Main entry point."""
    output_dir = Path("data/raw/open_library")
    collector = OpenLibraryCollector(output_dir)

    try:
        # Use API by default (faster and more targeted)
        await collector.collect_all(use_api=True, limit_per_subject=500)
    finally:
        await collector.close()


if __name__ == "__main__":
    asyncio.run(main())
