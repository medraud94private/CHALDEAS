#!/usr/bin/env python3
"""
Master data collection script for CHALDEAS.

Collects data from all supported open source knowledge bases:
- Perseus Digital Library (Greek/Roman classics)
- Chinese Text Project (Chinese classics)
- Project Gutenberg (Public domain books)
- The Latin Library (Latin texts)
- BIBLIOTHECA AUGUSTANA (Classical texts)

Usage:
    python collect_all.py --source all
    python collect_all.py --source perseus
    python collect_all.py --source ctext --api-key YOUR_KEY
    python collect_all.py --source gutenberg --limit 100
"""
import argparse
import asyncio
from pathlib import Path
import sys

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent))

from collectors.perseus import PerseusCollector
from collectors.ctext import CTextCollector
from collectors.gutenberg import GutenbergCollector
from collectors.pleiades import PleiadesCollector
from collectors.wikidata import WikidataCollector
from collectors.latin_library import LatinLibraryCollector
from collectors.bibliotheca_augustana import BibliothecaAugustanaCollector


async def collect_perseus(output_dir: Path):
    """Collect from Perseus Digital Library."""
    print("\n" + "=" * 60)
    print("Collecting from Perseus Digital Library")
    print("=" * 60)

    collector = PerseusCollector(output_dir / "perseus")
    try:
        await collector.collect_all()
    finally:
        await collector.close()


async def collect_ctext(output_dir: Path, api_key: str = None):
    """Collect from Chinese Text Project."""
    print("\n" + "=" * 60)
    print("Collecting from Chinese Text Project")
    print("=" * 60)

    collector = CTextCollector(output_dir / "ctext", api_key)
    try:
        await collector.collect_important_texts()
    finally:
        await collector.close()


async def collect_gutenberg(output_dir: Path, limit: int = 1000):
    """Collect from Project Gutenberg."""
    print("\n" + "=" * 60)
    print("Collecting from Project Gutenberg")
    print("=" * 60)

    collector = GutenbergCollector(output_dir / "gutenberg")
    try:
        await collector.collect_historical_texts(limit=limit)
    finally:
        await collector.close()


async def collect_pleiades(output_dir: Path):
    """Collect from Pleiades Gazetteer (ancient places)."""
    print("\n" + "=" * 60)
    print("Collecting from Pleiades Gazetteer")
    print("=" * 60)

    collector = PleiadesCollector(output_dir / "pleiades")
    try:
        await collector.collect_all()
    finally:
        await collector.close()


async def collect_wikidata(output_dir: Path):
    """Collect from Wikidata (events, persons, cities)."""
    print("\n" + "=" * 60)
    print("Collecting from Wikidata")
    print("=" * 60)

    collector = WikidataCollector(output_dir / "wikidata")
    try:
        await collector.collect_all()
    finally:
        await collector.close()


async def collect_latin_library(output_dir: Path):
    """Collect from The Latin Library."""
    print("\n" + "=" * 60)
    print("Collecting from The Latin Library")
    print("=" * 60)

    collector = LatinLibraryCollector(output_dir / "latin_library")
    try:
        await collector.collect_metadata_only()
    finally:
        await collector.close()


async def collect_augustana(output_dir: Path):
    """Collect from BIBLIOTHECA AUGUSTANA."""
    print("\n" + "=" * 60)
    print("Collecting from BIBLIOTHECA AUGUSTANA")
    print("=" * 60)

    collector = BibliothecaAugustanaCollector(output_dir / "augustana")
    try:
        await collector.collect_all_metadata()
    finally:
        await collector.close()


async def collect_all(output_dir: Path, **kwargs):
    """Collect from all sources."""
    # Priority 1: Location data (needed for everything else)
    await collect_pleiades(output_dir)
    await collect_wikidata(output_dir)

    # Priority 2: Text sources
    await collect_perseus(output_dir)
    await collect_ctext(output_dir, kwargs.get("api_key"))
    await collect_gutenberg(output_dir, kwargs.get("limit", 1000))

    # Priority 3: Additional classical text sources
    await collect_latin_library(output_dir)
    await collect_augustana(output_dir)


async def main():
    parser = argparse.ArgumentParser(description="CHALDEAS Data Collector")
    parser.add_argument(
        "--source",
        choices=[
            "all", "perseus", "ctext", "gutenberg",
            "pleiades", "wikidata", "latin_library", "augustana"
        ],
        default="all",
        help="Source to collect from",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/raw"),
        help="Output directory",
    )
    parser.add_argument(
        "--api-key",
        help="API key for sources that require it",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=1000,
        help="Limit number of items to collect",
    )

    args = parser.parse_args()

    print("CHALDEAS Data Collector")
    print(f"Output directory: {args.output}")
    print(f"Source: {args.source}")

    if args.source == "all":
        await collect_all(args.output, api_key=args.api_key, limit=args.limit)
    elif args.source == "perseus":
        await collect_perseus(args.output)
    elif args.source == "ctext":
        await collect_ctext(args.output, args.api_key)
    elif args.source == "gutenberg":
        await collect_gutenberg(args.output, args.limit)
    elif args.source == "pleiades":
        await collect_pleiades(args.output)
    elif args.source == "wikidata":
        await collect_wikidata(args.output)
    elif args.source == "latin_library":
        await collect_latin_library(args.output)
    elif args.source == "augustana":
        await collect_augustana(args.output)

    print("\n" + "=" * 60)
    print("Collection complete!")
    print("=" * 60)
    print(f"\nNext steps:")
    print("1. Run: python data/scripts/transform_data.py")
    print("2. Run: python data/scripts/import_to_db.py")


if __name__ == "__main__":
    asyncio.run(main())
