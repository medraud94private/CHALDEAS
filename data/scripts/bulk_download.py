#!/usr/bin/env python3
"""
CHALDEAS Bulk Download Master Script

Downloads large datasets from copyright-free sources for the CHALDEAS storage.

Sources included:
- Project Gutenberg (60,000+ public domain books)
- Open Library (book metadata and texts)
- Perseus Digital Library (Greek/Roman classics)
- Wikidata (structured historical data)
- DBpedia (Wikipedia structured data)
- Sacred Texts Archive (religious/mythological texts)
- All existing collectors

Usage:
    python bulk_download.py --all                    # Download everything
    python bulk_download.py --source gutenberg       # Specific source
    python bulk_download.py --source gutenberg --limit 5000
    python bulk_download.py --quick                  # Quick mode (smaller limits)
    python bulk_download.py --full                   # Full mode (maximum data)

Progress is logged to: docs/logs/BULK_DOWNLOAD_LOG.md
"""
import argparse
import asyncio
from pathlib import Path
import sys
import json
from datetime import datetime

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent))

# Import collectors
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
from collectors.dbpedia import DBpediaCollector
from collectors.open_library import OpenLibraryCollector


class BulkDownloadManager:
    """Manages bulk downloads from all sources."""

    def __init__(self, output_dir: Path, log_file: Path = None):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = log_file or Path("docs/logs/BULK_DOWNLOAD_LOG.md")
        self.stats = {
            "start_time": datetime.now().isoformat(),
            "sources": {},
            "total_items": 0,
            "errors": []
        }

    def log(self, message: str):
        """Print and optionally log a message."""
        print(message)

    def update_log_file(self, source: str, status: str, count: int = 0, error: str = None):
        """Update the progress in the log file."""
        self.stats["sources"][source] = {
            "status": status,
            "count": count,
            "timestamp": datetime.now().isoformat(),
            "error": error
        }
        self.stats["total_items"] += count

        # Save stats to JSON
        stats_file = self.output_dir / "bulk_download_stats.json"
        with open(stats_file, "w", encoding="utf-8") as f:
            json.dump(self.stats, f, indent=2)

    async def download_gutenberg(self, limit: int = 5000):
        """Download from Project Gutenberg with extended limits."""
        self.log("\n" + "=" * 60)
        self.log("BULK DOWNLOAD: Project Gutenberg")
        self.log("=" * 60)

        collector = GutenbergCollector(self.output_dir / "gutenberg")
        try:
            await collector.collect_historical_texts(limit=limit)
            self.update_log_file("gutenberg", "completed", limit)
        except Exception as e:
            self.update_log_file("gutenberg", "error", error=str(e))
            self.log(f"Error: {e}")
        finally:
            await collector.close()

    async def download_open_library(self, limit_per_subject: int = 500):
        """Download from Open Library."""
        self.log("\n" + "=" * 60)
        self.log("BULK DOWNLOAD: Open Library")
        self.log("=" * 60)

        collector = OpenLibraryCollector(self.output_dir / "open_library")
        try:
            await collector.collect_all(use_api=True, limit_per_subject=limit_per_subject)
            self.update_log_file("open_library", "completed", limit_per_subject * 20)
        except Exception as e:
            self.update_log_file("open_library", "error", error=str(e))
            self.log(f"Error: {e}")
        finally:
            await collector.close()

    async def download_perseus(self):
        """Download from Perseus Digital Library."""
        self.log("\n" + "=" * 60)
        self.log("BULK DOWNLOAD: Perseus Digital Library")
        self.log("=" * 60)

        collector = PerseusCollector(self.output_dir / "perseus")
        try:
            await collector.collect_all()
            self.update_log_file("perseus", "completed", len(collector.works_metadata))
        except Exception as e:
            self.update_log_file("perseus", "error", error=str(e))
            self.log(f"Error: {e}")
        finally:
            await collector.close()

    async def download_wikidata(self):
        """Download from Wikidata."""
        self.log("\n" + "=" * 60)
        self.log("BULK DOWNLOAD: Wikidata")
        self.log("=" * 60)

        collector = WikidataCollector(self.output_dir / "wikidata")
        try:
            await collector.collect_all()
            self.update_log_file("wikidata", "completed")
        except Exception as e:
            self.update_log_file("wikidata", "error", error=str(e))
            self.log(f"Error: {e}")
        finally:
            await collector.close()

    async def download_dbpedia(self):
        """Download from DBpedia."""
        self.log("\n" + "=" * 60)
        self.log("BULK DOWNLOAD: DBpedia")
        self.log("=" * 60)

        collector = DBpediaCollector(self.output_dir / "dbpedia")
        try:
            await collector.collect_all()
            self.update_log_file("dbpedia", "completed")
        except Exception as e:
            self.update_log_file("dbpedia", "error", error=str(e))
            self.log(f"Error: {e}")
        finally:
            await collector.close()

    async def download_sacred_texts(self):
        """Download from Sacred Texts Archive."""
        self.log("\n" + "=" * 60)
        self.log("BULK DOWNLOAD: Sacred Texts Archive")
        self.log("=" * 60)

        collector = SacredTextsCollector(self.output_dir / "sacred_texts")
        try:
            await collector.collect_all()
            self.update_log_file("sacred_texts", "completed")
        except Exception as e:
            self.update_log_file("sacred_texts", "error", error=str(e))
            self.log(f"Error: {e}")
        finally:
            await collector.close()

    async def download_theoi(self):
        """Download from Theoi Project."""
        self.log("\n" + "=" * 60)
        self.log("BULK DOWNLOAD: Theoi Project")
        self.log("=" * 60)

        collector = TheoiCollector(self.output_dir / "theoi")
        try:
            await collector.collect_all()
            self.update_log_file("theoi", "completed")
        except Exception as e:
            self.update_log_file("theoi", "error", error=str(e))
            self.log(f"Error: {e}")
        finally:
            await collector.close()

    async def download_pantheon(self):
        """Download from MIT Pantheon."""
        self.log("\n" + "=" * 60)
        self.log("BULK DOWNLOAD: MIT Pantheon")
        self.log("=" * 60)

        collector = PantheonCollector(self.output_dir / "pantheon")
        try:
            await collector.collect_all()
            self.update_log_file("pantheon", "completed")
        except Exception as e:
            self.update_log_file("pantheon", "error", error=str(e))
            self.log(f"Error: {e}")
        finally:
            await collector.close()

    async def download_pleiades(self):
        """Download from Pleiades Gazetteer."""
        self.log("\n" + "=" * 60)
        self.log("BULK DOWNLOAD: Pleiades Gazetteer")
        self.log("=" * 60)

        collector = PleiadesCollector(self.output_dir / "pleiades")
        try:
            await collector.collect_all()
            self.update_log_file("pleiades", "completed")
        except Exception as e:
            self.update_log_file("pleiades", "error", error=str(e))
            self.log(f"Error: {e}")
        finally:
            await collector.close()

    async def download_topostext(self):
        """Download from ToposText."""
        self.log("\n" + "=" * 60)
        self.log("BULK DOWNLOAD: ToposText")
        self.log("=" * 60)

        collector = ToposTextCollector(self.output_dir / "topostext")
        try:
            await collector.collect_all()
            self.update_log_file("topostext", "completed")
        except Exception as e:
            self.update_log_file("topostext", "error", error=str(e))
            self.log(f"Error: {e}")
        finally:
            await collector.close()

    async def download_ctext(self, api_key: str = None):
        """Download from Chinese Text Project."""
        self.log("\n" + "=" * 60)
        self.log("BULK DOWNLOAD: Chinese Text Project")
        self.log("=" * 60)

        collector = CTextCollector(self.output_dir / "ctext", api_key)
        try:
            await collector.collect_important_texts()
            self.update_log_file("ctext", "completed")
        except Exception as e:
            self.update_log_file("ctext", "error", error=str(e))
            self.log(f"Error: {e}")
        finally:
            await collector.close()

    async def download_avalon(self):
        """Download from Yale Avalon Project."""
        self.log("\n" + "=" * 60)
        self.log("BULK DOWNLOAD: Yale Avalon Project")
        self.log("=" * 60)

        collector = AvalonCollector(self.output_dir / "avalon")
        try:
            await collector.collect_all()
            self.update_log_file("avalon", "completed")
        except Exception as e:
            self.update_log_file("avalon", "error", error=str(e))
            self.log(f"Error: {e}")
        finally:
            await collector.close()

    async def download_fordham(self):
        """Download from Fordham Internet History Sourcebooks."""
        self.log("\n" + "=" * 60)
        self.log("BULK DOWNLOAD: Fordham Sourcebooks")
        self.log("=" * 60)

        collector = FordhamCollector(self.output_dir / "fordham")
        try:
            await collector.collect_all()
            self.update_log_file("fordham", "completed")
        except Exception as e:
            self.update_log_file("fordham", "error", error=str(e))
            self.log(f"Error: {e}")
        finally:
            await collector.close()

    async def download_britannica_1911(self, max_articles: int = 1000):
        """Download from 1911 Encyclopedia Britannica."""
        self.log("\n" + "=" * 60)
        self.log("BULK DOWNLOAD: 1911 Encyclopedia Britannica")
        self.log("=" * 60)

        collector = Britannica1911Collector(self.output_dir / "britannica_1911")
        try:
            await collector.collect_all(max_articles=max_articles)
            self.update_log_file("britannica_1911", "completed", max_articles)
        except Exception as e:
            self.update_log_file("britannica_1911", "error", error=str(e))
            self.log(f"Error: {e}")
        finally:
            await collector.close()

    async def download_worldhistory(self):
        """Download from World History Encyclopedia."""
        self.log("\n" + "=" * 60)
        self.log("BULK DOWNLOAD: World History Encyclopedia")
        self.log("=" * 60)

        collector = WorldHistoryCollector(self.output_dir / "worldhistory")
        try:
            await collector.collect_all()
            self.update_log_file("worldhistory", "completed")
        except Exception as e:
            self.update_log_file("worldhistory", "error", error=str(e))
            self.log(f"Error: {e}")
        finally:
            await collector.close()

    async def download_fgo_sources(self):
        """Download FGO-related sources."""
        self.log("\n" + "=" * 60)
        self.log("BULK DOWNLOAD: FGO Sources (Atlas Academy, Gamepress, Wikipedia)")
        self.log("=" * 60)

        # Atlas Academy
        collector = AtlasAcademyCollector(self.output_dir / "atlas_academy")
        try:
            await collector.collect_all()
            self.update_log_file("atlas_academy", "completed")
        except Exception as e:
            self.update_log_file("atlas_academy", "error", error=str(e))
        finally:
            await collector.close()

        # FGO Gamepress
        collector = FGOGamepressCollector(self.output_dir / "gamepress")
        try:
            await collector.collect_all()
            self.update_log_file("gamepress", "completed")
        except Exception as e:
            self.update_log_file("gamepress", "error", error=str(e))
        finally:
            await collector.close()

        # Wikipedia Servants
        collector = WikipediaCollector(self.output_dir / "wikipedia")
        try:
            await collector.collect_all()
            self.update_log_file("wikipedia", "completed")
        except Exception as e:
            self.update_log_file("wikipedia", "error", error=str(e))
        finally:
            await collector.close()

    async def download_regional_sources(self):
        """Download regional/cultural sources."""
        self.log("\n" + "=" * 60)
        self.log("BULK DOWNLOAD: Regional Sources")
        self.log("=" * 60)

        # Arthurian
        collector = ArthurianCollector(self.output_dir / "arthurian")
        try:
            await collector.collect_all()
            self.update_log_file("arthurian", "completed")
        except Exception as e:
            self.update_log_file("arthurian", "error", error=str(e))
        finally:
            await collector.close()

        # Russian History
        collector = RussianHistoryCollector(self.output_dir / "russian_history")
        try:
            await collector.collect_all()
            self.update_log_file("russian_history", "completed")
        except Exception as e:
            self.update_log_file("russian_history", "error", error=str(e))
        finally:
            await collector.close()

        # Mesoamerican
        collector = MesoamericanCollector(self.output_dir / "mesoamerican")
        try:
            await collector.collect_all()
            self.update_log_file("mesoamerican", "completed")
        except Exception as e:
            self.update_log_file("mesoamerican", "error", error=str(e))
        finally:
            await collector.close()

        # Indian Mythology
        collector = IndianMythologyCollector(self.output_dir / "indian_mythology")
        try:
            await collector.collect_all()
            self.update_log_file("indian_mythology", "completed")
        except Exception as e:
            self.update_log_file("indian_mythology", "error", error=str(e))
        finally:
            await collector.close()

    async def download_all(self, mode: str = "normal"):
        """
        Download from all sources.

        Args:
            mode: "quick" (small samples), "normal" (default), "full" (maximum data)
        """
        limits = {
            "quick": {"gutenberg": 500, "britannica": 200, "open_library": 100},
            "normal": {"gutenberg": 2000, "britannica": 500, "open_library": 300},
            "full": {"gutenberg": 10000, "britannica": 2000, "open_library": 500}
        }

        l = limits.get(mode, limits["normal"])

        self.log("\n" + "#" * 60)
        self.log(f"# CHALDEAS BULK DOWNLOAD - Mode: {mode.upper()}")
        self.log("#" * 60)
        self.log(f"\nStart time: {datetime.now().isoformat()}")
        self.log(f"Output directory: {self.output_dir}")

        # Priority 1: Structured data (fastest, most useful)
        await self.download_wikidata()
        await self.download_dbpedia()
        await self.download_pleiades()
        await self.download_topostext()
        await self.download_pantheon()

        # Priority 2: Text archives (public domain)
        await self.download_gutenberg(l["gutenberg"])
        await self.download_open_library(l["open_library"])
        await self.download_perseus()
        await self.download_sacred_texts()
        await self.download_theoi()
        await self.download_ctext()

        # Priority 3: Primary sources
        await self.download_avalon()
        await self.download_fordham()
        await self.download_britannica_1911(l["britannica"])

        # Priority 4: Encyclopedia references
        await self.download_worldhistory()

        # Priority 5: FGO-specific
        await self.download_fgo_sources()

        # Priority 6: Regional/Cultural
        await self.download_regional_sources()

        # Final summary
        self.log("\n" + "#" * 60)
        self.log("# BULK DOWNLOAD COMPLETE")
        self.log("#" * 60)
        self.log(f"\nEnd time: {datetime.now().isoformat()}")
        self.log(f"\nSummary:")
        for source, data in self.stats["sources"].items():
            status = data.get("status", "unknown")
            count = data.get("count", "?")
            self.log(f"  {source}: {status} ({count} items)")

        self.log(f"\nTotal items collected: {self.stats['total_items']}")
        self.log(f"Stats saved to: {self.output_dir / 'bulk_download_stats.json'}")


async def main():
    parser = argparse.ArgumentParser(
        description="CHALDEAS Bulk Download Manager",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python bulk_download.py --all                    # All sources, normal mode
    python bulk_download.py --all --quick            # All sources, quick mode
    python bulk_download.py --all --full             # All sources, full mode
    python bulk_download.py --source gutenberg       # Gutenberg only
    python bulk_download.py --source gutenberg --limit 10000
        """
    )

    parser.add_argument(
        "--all",
        action="store_true",
        help="Download from all sources"
    )
    parser.add_argument(
        "--source",
        choices=[
            "gutenberg", "open_library", "perseus", "wikidata", "dbpedia",
            "sacred_texts", "theoi", "pantheon", "pleiades", "topostext",
            "ctext", "avalon", "fordham", "britannica_1911", "worldhistory",
            "fgo", "regional"
        ],
        help="Download from a specific source"
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Quick mode (smaller samples)"
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Full mode (maximum data)"
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Limit for specific source"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/raw"),
        help="Output directory (default: data/raw)"
    )

    args = parser.parse_args()

    # Determine mode
    if args.full:
        mode = "full"
    elif args.quick:
        mode = "quick"
    else:
        mode = "normal"

    manager = BulkDownloadManager(args.output)

    if args.all:
        await manager.download_all(mode)
    elif args.source:
        limit = args.limit or {"quick": 500, "normal": 2000, "full": 10000}[mode]

        if args.source == "gutenberg":
            await manager.download_gutenberg(limit)
        elif args.source == "open_library":
            await manager.download_open_library(limit // 10)
        elif args.source == "perseus":
            await manager.download_perseus()
        elif args.source == "wikidata":
            await manager.download_wikidata()
        elif args.source == "dbpedia":
            await manager.download_dbpedia()
        elif args.source == "sacred_texts":
            await manager.download_sacred_texts()
        elif args.source == "theoi":
            await manager.download_theoi()
        elif args.source == "pantheon":
            await manager.download_pantheon()
        elif args.source == "pleiades":
            await manager.download_pleiades()
        elif args.source == "topostext":
            await manager.download_topostext()
        elif args.source == "ctext":
            await manager.download_ctext()
        elif args.source == "avalon":
            await manager.download_avalon()
        elif args.source == "fordham":
            await manager.download_fordham()
        elif args.source == "britannica_1911":
            await manager.download_britannica_1911(limit)
        elif args.source == "worldhistory":
            await manager.download_worldhistory()
        elif args.source == "fgo":
            await manager.download_fgo_sources()
        elif args.source == "regional":
            await manager.download_regional_sources()
    else:
        parser.print_help()
        print("\nUse --all to download everything, or --source to pick a specific source.")


if __name__ == "__main__":
    asyncio.run(main())
