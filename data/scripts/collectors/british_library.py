"""
British Library Digitised Books Collector

Website: https://bl.iro.bl.uk/
Dataset: https://bl.iro.bl.uk/concern/datasets/888b314f-8b94-420d-8a97-f9c1e08949f5

Contains 49,455 digitised books (65,227 volumes, 25+ million pages)
from c. 1510 - c. 1900 in JSON OCR text format.

License: CC Public Domain Mark 1.0
Size: ~11 GB compressed (.bz2)
"""
import httpx
import asyncio
from pathlib import Path
import json
import bz2
import os
from typing import Optional
from datetime import datetime


def safe_print(text: str):
    """Print text safely, handling encoding issues on Windows."""
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode('ascii', 'replace').decode('ascii'))


class BritishLibraryCollector:
    """
    Collector for British Library Digitised Books dataset.

    Downloads and processes:
    - JSON OCR text from 49,455 books (1510-1900)
    - Covers history, philosophy, literature, poetry, geography
    """

    # Main dataset download URL
    DATASET_URL = "https://bl.iro.bl.uk/downloads/0623cab5-58d7-4eba-b88b-bb32b86862d8?locale=en"
    DATASET_FILENAME = "dig19cbooksjsontext.bz2"
    DATASET_SIZE_GB = 11  # Approximate size in GB

    # Metadata dataset URL
    METADATA_URL = "https://bl.iro.bl.uk/downloads/c39ec180-bd70-4f33-bd84-d0a093ab7e01"

    # Hugging Face alternative (if direct download fails)
    HUGGINGFACE_DATASET = "TheBritishLibrary/blbooks"

    # Historical subjects to filter when processing
    HISTORICAL_SUBJECTS = [
        "history", "philosophy", "classical", "ancient", "mythology",
        "greece", "rome", "egypt", "medieval", "renaissance",
        "religion", "theology", "biography", "literature", "poetry",
        "science", "mathematics", "geography", "war", "military"
    ]

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.client = httpx.AsyncClient(
            timeout=3600.0,  # 1 hour timeout for large file
            follow_redirects=True,
            headers={
                "User-Agent": "CHALDEAS/0.1 (Historical Knowledge System; research@example.com)"
            }
        )

    async def download_dataset(self, url: str, output_file: Path) -> bool:
        """
        Download a large dataset file with progress tracking.
        """
        safe_print(f"\nDownloading: {url}")
        safe_print(f"Output: {output_file}")
        safe_print(f"Expected size: ~{self.DATASET_SIZE_GB} GB")
        safe_print("This will take a while...")

        try:
            async with self.client.stream("GET", url) as response:
                response.raise_for_status()
                total = int(response.headers.get("content-length", 0))

                with open(output_file, "wb") as f:
                    downloaded = 0
                    last_percent = -1

                    async for chunk in response.aiter_bytes(chunk_size=1024*1024):  # 1MB chunks
                        f.write(chunk)
                        downloaded += len(chunk)

                        if total:
                            percent = int((downloaded / total) * 100)
                            if percent != last_percent and percent % 5 == 0:
                                downloaded_gb = downloaded / (1024**3)
                                total_gb = total / (1024**3)
                                safe_print(f"  Progress: {percent}% ({downloaded_gb:.2f} / {total_gb:.2f} GB)")
                                last_percent = percent

                safe_print(f"\nDownload complete: {output_file}")
                return True

        except Exception as e:
            safe_print(f"Error downloading: {e}")
            return False

    def extract_bz2(self, bz2_file: Path, output_dir: Path) -> bool:
        """
        Extract a .bz2 archive.

        Note: The BL dataset is a bz2-compressed tar archive or concatenated JSON files.
        """
        safe_print(f"\nExtracting: {bz2_file}")
        safe_print(f"Output: {output_dir}")

        try:
            output_dir.mkdir(parents=True, exist_ok=True)

            # For the BL dataset, it's a bz2 compressed archive
            # The actual format may be tar.bz2 or just concatenated JSON
            import tarfile

            # Try as tar.bz2 first
            try:
                with tarfile.open(bz2_file, 'r:bz2') as tar:
                    # Extract with progress
                    members = tar.getmembers()
                    total = len(members)

                    for i, member in enumerate(members):
                        if i % 1000 == 0:
                            safe_print(f"  Extracting: {i}/{total} files ({100*i//total}%)")
                        tar.extract(member, output_dir)

                    safe_print(f"\nExtracted {total} files")
                    return True

            except tarfile.ReadError:
                # Not a tar file, might be plain bz2 compressed text
                safe_print("  Not a tar archive, extracting as plain bz2...")

                output_file = output_dir / "books_text.json"
                with bz2.open(bz2_file, 'rt', encoding='utf-8', errors='ignore') as f_in:
                    with open(output_file, 'w', encoding='utf-8') as f_out:
                        chunk_size = 1024 * 1024  # 1MB
                        total_written = 0

                        while True:
                            chunk = f_in.read(chunk_size)
                            if not chunk:
                                break
                            f_out.write(chunk)
                            total_written += len(chunk)

                            if total_written % (100 * 1024 * 1024) == 0:  # Every 100MB
                                safe_print(f"  Extracted: {total_written / (1024**3):.2f} GB")

                safe_print(f"\nExtracted to: {output_file}")
                return True

        except Exception as e:
            safe_print(f"Error extracting: {e}")
            return False

    def process_books(self, extracted_dir: Path, output_file: Path, limit: int = None) -> list[dict]:
        """
        Process extracted book JSON files into a structured format.
        """
        safe_print(f"\nProcessing books from: {extracted_dir}")

        books = []
        processed = 0

        # Find all JSON files
        json_files = list(extracted_dir.rglob("*.json"))
        total_files = len(json_files)

        safe_print(f"Found {total_files} JSON files")

        for json_file in json_files:
            try:
                with open(json_file, 'r', encoding='utf-8', errors='ignore') as f:
                    data = json.load(f)

                # Extract book identifier from filename
                book_id = json_file.stem

                # Get page texts (the JSON format is {page_number: text})
                if isinstance(data, dict):
                    pages = len(data)
                    # Get first few pages as sample
                    sample_text = ""
                    for page_num in sorted(data.keys())[:5]:
                        sample_text += data[page_num] + "\n"

                    books.append({
                        "id": book_id,
                        "filename": json_file.name,
                        "pages": pages,
                        "sample_text": sample_text[:2000],  # First 2000 chars
                        "source": "british_library"
                    })

                processed += 1

                if processed % 1000 == 0:
                    safe_print(f"  Processed: {processed}/{total_files} ({100*processed//total_files}%)")

                if limit and processed >= limit:
                    break

            except Exception as e:
                # Skip problematic files
                continue

        safe_print(f"\nProcessed {len(books)} books")

        # Save processed data
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(books, f, indent=2, ensure_ascii=False)

        return books

    async def collect_all(self, download: bool = True, extract: bool = True,
                          process: bool = True, limit: int = None):
        """
        Full collection pipeline:
        1. Download the compressed dataset (~11 GB)
        2. Extract the bz2 archive
        3. Process books into structured format

        Args:
            download: Whether to download the dataset (skip if already downloaded)
            extract: Whether to extract the archive
            process: Whether to process extracted files
            limit: Max number of books to process (None = all)
        """
        print("\n" + "=" * 60)
        print("British Library Digitised Books Collection")
        print("=" * 60)
        print(f"Dataset: 49,455 books (1510-1900)")
        print(f"Size: ~11 GB compressed")
        print(f"License: CC Public Domain Mark 1.0")
        print("=" * 60)

        # Paths
        bz2_file = self.output_dir / self.DATASET_FILENAME
        extracted_dir = self.output_dir / "extracted"
        processed_file = self.output_dir / "british_library_books.json"

        # Step 1: Download
        if download:
            if bz2_file.exists():
                size_gb = bz2_file.stat().st_size / (1024**3)
                safe_print(f"\nDataset already exists: {bz2_file} ({size_gb:.2f} GB)")
                safe_print("Skipping download. Delete the file to re-download.")
            else:
                success = await self.download_dataset(self.DATASET_URL, bz2_file)
                if not success:
                    safe_print("Download failed!")
                    return

        # Step 2: Extract
        if extract and bz2_file.exists():
            if extracted_dir.exists() and any(extracted_dir.iterdir()):
                safe_print(f"\nExtracted data already exists: {extracted_dir}")
                safe_print("Skipping extraction. Delete the folder to re-extract.")
            else:
                self.extract_bz2(bz2_file, extracted_dir)

        # Step 3: Process
        if process and extracted_dir.exists():
            books = self.process_books(extracted_dir, processed_file, limit)

            # Save metadata
            metadata = {
                "source": "British Library",
                "url": "https://bl.iro.bl.uk/",
                "dataset_url": self.DATASET_URL,
                "license": "CC Public Domain Mark 1.0",
                "collection_date": datetime.now().isoformat(),
                "total_books": len(books),
                "period": "c. 1510 - c. 1900",
                "subjects": ["history", "philosophy", "literature", "poetry", "geography"]
            }

            metadata_file = self.output_dir / "british_library_metadata.json"
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2)

            safe_print(f"\nCollection complete!")
            safe_print(f"Books: {len(books)}")
            safe_print(f"Data: {processed_file}")
            safe_print(f"Metadata: {metadata_file}")

    async def collect_metadata_only(self) -> list[dict]:
        """
        Collect only the metadata (much smaller download).
        Useful for getting book information without full texts.
        """
        print("\n" + "=" * 60)
        print("British Library - Metadata Only")
        print("=" * 60)

        # The metadata is available separately
        metadata_url = "https://bl.iro.bl.uk/downloads/c39ec180-bd70-4f33-bd84-d0a093ab7e01"
        output_file = self.output_dir / "british_library_metadata_catalog.json"

        try:
            safe_print(f"Downloading metadata catalog...")
            response = await self.client.get(metadata_url)
            response.raise_for_status()

            with open(output_file, 'wb') as f:
                f.write(response.content)

            safe_print(f"Saved to: {output_file}")

            # Parse and return
            try:
                with open(output_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                return data if isinstance(data, list) else [data]
            except:
                return []

        except Exception as e:
            safe_print(f"Error: {e}")
            return []

    async def close(self):
        await self.client.aclose()


async def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="British Library Books Collector")
    parser.add_argument("--metadata-only", action="store_true",
                        help="Download only metadata (smaller)")
    parser.add_argument("--no-download", action="store_true",
                        help="Skip download (use existing file)")
    parser.add_argument("--no-extract", action="store_true",
                        help="Skip extraction")
    parser.add_argument("--limit", type=int, default=None,
                        help="Limit number of books to process")

    args = parser.parse_args()

    output_dir = Path("data/raw/british_library")
    collector = BritishLibraryCollector(output_dir)

    try:
        if args.metadata_only:
            await collector.collect_metadata_only()
        else:
            await collector.collect_all(
                download=not args.no_download,
                extract=not args.no_extract,
                limit=args.limit
            )
    finally:
        await collector.close()


if __name__ == "__main__":
    asyncio.run(main())
