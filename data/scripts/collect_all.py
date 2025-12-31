#!/usr/bin/env python3
"""
Master data collection script for CHALDEAS.

Collects data from all supported open source knowledge bases:
- Perseus Digital Library (Greek/Roman classics)
- Chinese Text Project (Chinese classics)
- Project Gutenberg (Public domain books)
- The Latin Library (Latin texts)
- BIBLIOTHECA AUGUSTANA (Classical texts)
- ToposText (Ancient world gazetteer)
- Theoi Project (Greek mythology)
- Sacred-Texts (Religious/mythological texts)

Usage:
    python collect_all.py --source all
    python collect_all.py --source perseus
    python collect_all.py --source ctext --api-key YOUR_KEY
    python collect_all.py --source gutenberg --limit 100
    python collect_all.py --source topostext
    python collect_all.py --source theoi
    python collect_all.py --source sacred_texts
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
from collectors.topostext import ToposTextCollector
from collectors.theoi import TheoiCollector
from collectors.sacred_texts import SacredTextsCollector
from collectors.atlas_academy import AtlasAcademyCollector
from collectors.fgo_gamepress import FGOGamepressCollector
from collectors.pantheon import PantheonCollector
from collectors.wikipedia import WikipediaCollector
from collectors.avalon import AvalonCollector
from collectors.fordham import FordhamCollector
from collectors.worldhistory import WorldHistoryCollector
from collectors.stanford_encyclopedia import StanfordEncyclopediaCollector
from collectors.britannica_1911 import Britannica1911Collector
from collectors.arthurian import ArthurianCollector
from collectors.russian_history import RussianHistoryCollector
from collectors.mesoamerican import MesoamericanCollector
from collectors.indian_mythology import IndianMythologyCollector


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


async def collect_topostext(output_dir: Path):
    """Collect from ToposText (ancient world gazetteer)."""
    print("\n" + "=" * 60)
    print("Collecting from ToposText")
    print("=" * 60)

    collector = ToposTextCollector(output_dir / "topostext")
    try:
        await collector.collect_all()
    finally:
        await collector.close()


async def collect_theoi(output_dir: Path):
    """Collect from Theoi Project (Greek mythology)."""
    print("\n" + "=" * 60)
    print("Collecting from Theoi Project")
    print("=" * 60)

    collector = TheoiCollector(output_dir / "theoi")
    try:
        await collector.collect_all()
    finally:
        await collector.close()


async def collect_sacred_texts(output_dir: Path):
    """Collect from Sacred-Texts.com (religious/mythological texts)."""
    print("\n" + "=" * 60)
    print("Collecting from Sacred-Texts.com")
    print("=" * 60)

    collector = SacredTextsCollector(output_dir / "sacred_texts")
    try:
        await collector.collect_all()
    finally:
        await collector.close()


async def collect_atlas_academy(output_dir: Path):
    """Collect from Atlas Academy (FGO game data)."""
    print("\n" + "=" * 60)
    print("Collecting from Atlas Academy (FGO)")
    print("=" * 60)

    collector = AtlasAcademyCollector(output_dir / "atlas_academy")
    try:
        await collector.collect_all()
    finally:
        await collector.close()


async def collect_gamepress(output_dir: Path):
    """Collect from FGO Gamepress (servant lore)."""
    print("\n" + "=" * 60)
    print("Collecting from FGO Gamepress")
    print("=" * 60)

    collector = FGOGamepressCollector(output_dir / "gamepress")
    try:
        await collector.collect_all()
    finally:
        await collector.close()


async def collect_pantheon(output_dir: Path):
    """Collect from MIT Pantheon (historical figures)."""
    print("\n" + "=" * 60)
    print("Collecting from MIT Pantheon")
    print("=" * 60)

    collector = PantheonCollector(output_dir / "pantheon")
    try:
        await collector.collect_all()
    finally:
        await collector.close()


async def collect_wikipedia(output_dir: Path):
    """Collect from Wikipedia (servant articles)."""
    print("\n" + "=" * 60)
    print("Collecting from Wikipedia")
    print("=" * 60)

    collector = WikipediaCollector(output_dir / "wikipedia")
    try:
        await collector.collect_all()
    finally:
        await collector.close()


async def collect_avalon(output_dir: Path):
    """Collect from Yale Avalon Project (primary historical documents)."""
    print("\n" + "=" * 60)
    print("Collecting from Yale Avalon Project")
    print("=" * 60)

    collector = AvalonCollector(output_dir / "avalon")
    try:
        await collector.collect_all()
    finally:
        await collector.close()


async def collect_fordham(output_dir: Path):
    """Collect from Fordham Internet History Sourcebooks."""
    print("\n" + "=" * 60)
    print("Collecting from Fordham Sourcebooks")
    print("=" * 60)

    collector = FordhamCollector(output_dir / "fordham")
    try:
        await collector.collect_all()
    finally:
        await collector.close()


async def collect_worldhistory(output_dir: Path):
    """Collect from World History Encyclopedia."""
    print("\n" + "=" * 60)
    print("Collecting from World History Encyclopedia")
    print("=" * 60)

    collector = WorldHistoryCollector(output_dir / "worldhistory")
    try:
        await collector.collect_all()
    finally:
        await collector.close()


async def collect_stanford_encyclopedia(output_dir: Path):
    """Collect from Stanford Encyclopedia of Philosophy."""
    print("\n" + "=" * 60)
    print("Collecting from Stanford Encyclopedia of Philosophy")
    print("=" * 60)

    collector = StanfordEncyclopediaCollector(output_dir / "stanford_encyclopedia")
    try:
        await collector.collect_all()
    finally:
        await collector.close()


async def collect_britannica_1911(output_dir: Path):
    """Collect from 1911 Encyclopedia Britannica (Wikisource)."""
    print("\n" + "=" * 60)
    print("Collecting from 1911 Encyclopedia Britannica")
    print("=" * 60)

    collector = Britannica1911Collector(output_dir / "britannica_1911")
    try:
        await collector.collect_all(max_articles=500)
    finally:
        await collector.close()


async def collect_arthurian(output_dir: Path):
    """Collect Arthurian legends (Wikipedia + Gutenberg)."""
    print("\n" + "=" * 60)
    print("Collecting Arthurian Legends")
    print("=" * 60)

    collector = ArthurianCollector(output_dir / "arthurian")
    try:
        await collector.collect_all()
    finally:
        await collector.close()


async def collect_russian_history(output_dir: Path):
    """Collect Russian/Eastern European history (Wikipedia)."""
    print("\n" + "=" * 60)
    print("Collecting Russian/Eastern European History")
    print("=" * 60)

    collector = RussianHistoryCollector(output_dir / "russian_history")
    try:
        await collector.collect_all()
    finally:
        await collector.close()


async def collect_mesoamerican(output_dir: Path):
    """Collect Mesoamerican mythology (Aztec, Maya, Inca)."""
    print("\n" + "=" * 60)
    print("Collecting Mesoamerican Mythology")
    print("=" * 60)

    collector = MesoamericanCollector(output_dir / "mesoamerican")
    try:
        await collector.collect_all()
    finally:
        await collector.close()


async def collect_indian_mythology(output_dir: Path):
    """Collect Indian mythology and history (Wikipedia)."""
    print("\n" + "=" * 60)
    print("Collecting Indian Mythology & History")
    print("=" * 60)

    collector = IndianMythologyCollector(output_dir / "indian_mythology")
    try:
        await collector.collect_all()
    finally:
        await collector.close()


async def collect_all(output_dir: Path, **kwargs):
    """Collect from all sources."""
    # Priority 1: Location data (needed for everything else)
    await collect_pleiades(output_dir)
    await collect_wikidata(output_dir)
    await collect_topostext(output_dir)

    # Priority 2: Text sources
    await collect_perseus(output_dir)
    await collect_ctext(output_dir, kwargs.get("api_key"))
    await collect_gutenberg(output_dir, kwargs.get("limit", 1000))

    # Priority 3: Additional classical text sources
    await collect_latin_library(output_dir)
    await collect_augustana(output_dir)

    # Priority 4: Mythology and religious texts
    await collect_theoi(output_dir)
    await collect_sacred_texts(output_dir)

    # Priority 5: FGO-specific data
    await collect_atlas_academy(output_dir)
    await collect_gamepress(output_dir)

    # Priority 6: Historical figures and Wikipedia
    await collect_pantheon(output_dir)
    await collect_wikipedia(output_dir)

    # Priority 7: Primary source collections
    await collect_avalon(output_dir)
    await collect_fordham(output_dir)

    # Priority 8: Reference encyclopedias
    await collect_worldhistory(output_dir)
    await collect_stanford_encyclopedia(output_dir)


async def main():
    parser = argparse.ArgumentParser(description="CHALDEAS Data Collector")
    parser.add_argument(
        "--source",
        choices=[
            "all", "perseus", "ctext", "gutenberg",
            "pleiades", "wikidata", "latin_library", "augustana",
            "topostext", "theoi", "sacred_texts",
            "atlas_academy", "gamepress", "pantheon", "wikipedia",
            "avalon", "fordham", "worldhistory", "stanford_encyclopedia",
            "britannica_1911",
            # Phase 3.5: FGO Coverage Expansion
            "arthurian", "russian_history", "mesoamerican", "indian_mythology"
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
    elif args.source == "topostext":
        await collect_topostext(args.output)
    elif args.source == "theoi":
        await collect_theoi(args.output)
    elif args.source == "sacred_texts":
        await collect_sacred_texts(args.output)
    elif args.source == "atlas_academy":
        await collect_atlas_academy(args.output)
    elif args.source == "gamepress":
        await collect_gamepress(args.output)
    elif args.source == "pantheon":
        await collect_pantheon(args.output)
    elif args.source == "wikipedia":
        await collect_wikipedia(args.output)
    elif args.source == "avalon":
        await collect_avalon(args.output)
    elif args.source == "fordham":
        await collect_fordham(args.output)
    elif args.source == "worldhistory":
        await collect_worldhistory(args.output)
    elif args.source == "stanford_encyclopedia":
        await collect_stanford_encyclopedia(args.output)
    elif args.source == "britannica_1911":
        await collect_britannica_1911(args.output)
    # Phase 3.5: FGO Coverage Expansion
    elif args.source == "arthurian":
        await collect_arthurian(args.output)
    elif args.source == "russian_history":
        await collect_russian_history(args.output)
    elif args.source == "mesoamerican":
        await collect_mesoamerican(args.output)
    elif args.source == "indian_mythology":
        await collect_indian_mythology(args.output)

    print("\n" + "=" * 60)
    print("Collection complete!")
    print("=" * 60)
    print(f"\nNext steps:")
    print("1. Run: python data/scripts/transform_data.py")
    print("2. Run: python data/scripts/import_to_db.py")


if __name__ == "__main__":
    asyncio.run(main())
