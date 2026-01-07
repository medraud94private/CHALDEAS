"""
Archivist Full-Scale Processing Script V4
- Uses EntityRegistry for deduplication (same entity from 100 files = 1 pending item)
- Uses buffer-based pending queue (sync with checkpoint)
- FileCountCache for fast file counting
- Safe resumability
- V4: MentionStore로 mentions 분리 (checkpoint 경량화)
"""
import asyncio
import json
import os
import sys
import io
from pathlib import Path
from datetime import datetime
from typing import Generator
import argparse
import logging

# Fix Windows console encoding
if sys.platform == 'win32':
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True)
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace', line_buffering=True)
    except Exception:
        pass

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.extraction.ner_pipeline import HybridNERPipeline
from app.core.checkpoint import (
    StatusManager, PendingQueue, Phase1Checkpoint,
    EntityRegistry, FileCountCache, MentionStore
)


# Configure logging
LOG_DIR = Path(__file__).parent.parent / "data" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / f"phase1_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log", encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class FullScaleProcessorV3:
    """Full-scale data processor with entity deduplication."""

    DATA_DIR = Path(__file__).parent.parent.parent / "data" / "raw"
    CHECKPOINT_DIR = Path(__file__).parent.parent / "data"
    RESULTS_DIR = Path(__file__).parent.parent / "data" / "archivist_results"

    # All data sources with their configurations
    SOURCES = {
        "british_library": {
            "dir": "british_library/extracted",
            "patterns": ["*.json"],
            "priority": 1,
            "chunk_size": 3000,
        },
        "gutenberg": {
            "dir": "gutenberg",
            "patterns": ["pg*.txt"],
            "priority": 2,
            "chunk_size": 5000,
        },
        "perseus": {"dir": "perseus", "patterns": ["*.json"], "priority": 3, "chunk_size": 5000},
        "britannica_1911": {"dir": "britannica_1911", "patterns": ["*.json"], "priority": 4, "chunk_size": 5000},
        "open_library": {"dir": "open_library", "patterns": ["*.json"], "priority": 5, "chunk_size": 5000},
        "theoi": {"dir": "theoi", "patterns": ["*.json"], "priority": 6, "chunk_size": 5000},
        "ctext": {"dir": "ctext", "patterns": ["*.json"], "priority": 7, "chunk_size": 5000},
        "arthurian": {"dir": "arthurian", "patterns": ["*.txt"], "priority": 8, "chunk_size": 5000},
        "stanford_encyclopedia": {"dir": "stanford_encyclopedia", "patterns": ["*.json"], "priority": 9, "chunk_size": 5000},
        "worldhistory": {"dir": "worldhistory", "patterns": ["*.json"], "priority": 10, "chunk_size": 5000},
        "pantheon": {"dir": "pantheon", "patterns": ["*.json"], "priority": 11, "chunk_size": 5000},
        "sacred_texts": {"dir": "sacred_texts", "patterns": ["*.json", "*.txt"], "priority": 12, "chunk_size": 5000},
        "avalon": {"dir": "avalon", "patterns": ["*.json", "*.txt"], "priority": 13, "chunk_size": 5000},
        "fordham": {"dir": "fordham", "patterns": ["*.json", "*.txt"], "priority": 14, "chunk_size": 5000},
        "topostext": {"dir": "topostext", "patterns": ["*.json"], "priority": 15, "chunk_size": 5000},
        "pleiades": {"dir": "pleiades", "patterns": ["*.json"], "priority": 16, "chunk_size": 5000},
        "indian_mythology": {"dir": "indian_mythology", "patterns": ["*.json", "*.txt"], "priority": 17, "chunk_size": 5000},
        "mesoamerican": {"dir": "mesoamerican", "patterns": ["*.json", "*.txt"], "priority": 18, "chunk_size": 5000},
        "russian_history": {"dir": "russian_history", "patterns": ["*.json", "*.txt"], "priority": 19, "chunk_size": 5000},
    }

    def __init__(self, save_interval: int = 50, status_interval: int = 10):
        self.save_interval = save_interval      # Checkpoint every N files
        self.status_interval = status_interval  # Status update every N files

        self.ner = None

        # Checkpoint components
        self.status_manager = StatusManager(self.CHECKPOINT_DIR)
        self.pending_queue = PendingQueue(self.CHECKPOINT_DIR)
        self.phase1_checkpoint = Phase1Checkpoint(self.CHECKPOINT_DIR)
        self.file_count_cache = FileCountCache(self.CHECKPOINT_DIR)

        # V4: MentionStore for separate mention storage
        self.mention_store = MentionStore(self.CHECKPOINT_DIR)

        # Entity merging registry (V4: connected to MentionStore)
        self.entity_registry = EntityRegistry(mention_store=self.mention_store)

        self.processed_files: set = set()
        self.exported_entities: set = set()  # Entities already exported to pending_queue
        self.start_time = None
        self.total_files_count = 0
        self.total_entities_raw = 0  # Total mentions
        self.total_entities_unique = 0  # Unique entities

    async def initialize(self):
        """Initialize NER pipeline (CPU only, no LLM)."""
        logger.info("Initializing NER pipeline (spaCy only, CPU)...")
        logger.info("Phase 1: NER extraction + deduplication -> pending_queue")
        logger.info("Phase 2 (separate process): LLM processing from pending_queue")

        self.ner = HybridNERPipeline(use_llm_verification=False)

        # Load from checkpoint if exists
        await self._load_checkpoint()

    async def _load_checkpoint(self):
        """Load from Phase1Checkpoint if exists."""
        checkpoint_data = self.phase1_checkpoint.load()

        if checkpoint_data:
            self.processed_files = set(checkpoint_data.get("processed_files", []))
            self.exported_entities = set(checkpoint_data.get("exported_entities", []))
            logger.info(f"Loaded checkpoint: {len(self.processed_files)} files already processed")

            # Load entity registry from checkpoint
            registry_data = checkpoint_data.get("registry", {})
            registry_entities = registry_data.get("entities", [])
            if registry_entities:
                self.entity_registry.load_from_data(registry_entities)
                self.total_entities_unique = self.entity_registry.get_unique_count()
                self.total_entities_raw = self.entity_registry.get_total_mentions()
                logger.info(f"Loaded entity registry: {self.total_entities_unique} unique entities, {self.total_entities_raw} mentions")

        # Get existing pending count
        pending_count = self.pending_queue.file_count()
        logger.info(f"Existing pending queue: {pending_count} items")
        logger.info(f"Already exported to pending: {len(self.exported_entities)} entities")

    async def _save_checkpoint(self):
        """Save Phase1Checkpoint and export new entities to pending_queue (V4)."""

        # Export new entities (not yet exported) to pending_queue
        new_exports = 0
        for entity in self.entity_registry.get_all_entities():
            entity_key = entity["key"]
            if entity_key not in self.exported_entities:
                # Export this entity to pending_queue (V4: mention_count instead of mentions list)
                self.pending_queue.buffer_append(
                    text=entity["text"],
                    entity_type=entity["entity_type"],
                    entity_key=entity_key,
                    mention_count=entity.get("mention_count", 1),
                    sample=entity.get("sample_text", entity["text"])
                )
                self.exported_entities.add(entity_key)
                new_exports += 1

        # Save checkpoint - V4: also flushes mention_store buffer
        self.phase1_checkpoint.save(
            processed_files=list(self.processed_files),
            registry_entities=self.entity_registry.get_all_entities(),
            next_entity_id=self.entity_registry.get_unique_count(),
            pending_queue=self.pending_queue,
            mention_store=self.mention_store,
            exported_entities=list(self.exported_entities)
        )

        logger.info(f"[Checkpoint] {len(self.processed_files)} files, {self.entity_registry.get_unique_count()} entities, {new_exports} new exports")

    def _get_all_files(self) -> Generator[tuple, None, None]:
        """Get all files from all sources, sorted by priority."""
        sorted_sources = sorted(self.SOURCES.items(), key=lambda x: x[1]["priority"])

        for source_name, config in sorted_sources:
            source_dir = self.DATA_DIR / config["dir"]
            if not source_dir.exists():
                continue

            for pattern in config["patterns"]:
                for filepath in source_dir.rglob(pattern):
                    if filepath.is_file():
                        yield (source_name, filepath, config["chunk_size"])

    def _count_all_files(self) -> int:
        """Count all files to process (with caching)."""
        # Check cache first
        cached = self.file_count_cache.get_cached_count()
        if cached is not None:
            logger.info(f"Using cached file count: {cached}")
            return cached

        # Count and cache
        logger.info("Counting files (this will be cached)...")
        count = 0
        source_counts = {}

        sorted_sources = sorted(self.SOURCES.items(), key=lambda x: x[1]["priority"])
        for source_name, config in sorted_sources:
            source_dir = self.DATA_DIR / config["dir"]
            if not source_dir.exists():
                continue

            source_count = 0
            for pattern in config["patterns"]:
                for filepath in source_dir.rglob(pattern):
                    if filepath.is_file():
                        count += 1
                        source_count += 1

            source_counts[source_name] = source_count
            logger.info(f"  {source_name}: {source_count} files")

        # Save to cache
        self.file_count_cache.save_count(count, source_counts)
        return count

    def _load_file_content(self, filepath: Path) -> str:
        """Load content from file."""
        try:
            suffix = filepath.suffix.lower()

            if suffix == ".json":
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                    data = json.load(f)

                if isinstance(data, dict):
                    content = data.get("content") or data.get("text") or data.get("body") or ""
                    if not content and "fulltext" in data:
                        content = data["fulltext"]
                    if not content:
                        content = " ".join(str(v) for v in data.values() if isinstance(v, str))
                elif isinstance(data, list):
                    content = " ".join(
                        item.get("text", str(item)) if isinstance(item, dict) else str(item)
                        for item in data[:20]
                    )
                else:
                    content = str(data)

                return content

            else:  # Text files
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                    return f.read()

        except Exception as e:
            logger.error(f"Error loading {filepath}: {e}")
            return ""

    async def process_file(self, source_name: str, filepath: Path, chunk_size: int) -> tuple:
        """
        Process a single file and return (raw_count, new_count).
        Processes ALL chunks in file (not just first chunk).
        Uses EntityRegistry for entity merging with proper mention tracking.
        """
        # Full relative path (e.g., "british_library/extracted/000037.json")
        source_path = str(filepath.relative_to(self.DATA_DIR))

        if source_path in self.processed_files:
            return (0, 0)

        content = self._load_file_content(filepath)
        if not content or len(content) < 50:
            self.processed_files.add(source_path)
            return (0, 0)

        raw_count = 0
        new_count = 0

        # Process ALL chunks in the file
        for chunk_start in range(0, len(content), chunk_size):
            chunk_end = min(chunk_start + chunk_size, len(content))
            chunk = content[chunk_start:chunk_end]

            # Skip tiny chunks at end
            if len(chunk) < 50:
                continue

            # Extract entities using spaCy (fast)
            entities = await self.ner.extract_entities(chunk)

            for entity in entities:
                if entity.entity_type in ["person", "location", "event"]:
                    raw_count += 1
                    self.total_entities_raw += 1

                    # Convert entity position to absolute (file-level) position
                    absolute_start = chunk_start + entity.start
                    absolute_end = chunk_start + entity.end

                    # Add mention with full tracking info
                    is_new, entity_key = self.entity_registry.add_mention(
                        text=entity.text,
                        entity_type=entity.entity_type,
                        source_path=source_path,
                        start=absolute_start,
                        end=absolute_end,
                        chunk_start=chunk_start,
                        chunk_end=chunk_end
                    )

                    if is_new:
                        new_count += 1
                        self.total_entities_unique += 1

        self.processed_files.add(source_path)
        return (raw_count, new_count)

    async def run(self, limit: int = None, source_filter: str = None):
        """Run full-scale processing."""
        self.start_time = datetime.now()

        logger.info("=" * 60)
        logger.info("       ARCHIVIST FULL-SCALE PROCESSING V3")
        logger.info("       (with Entity Deduplication)")
        logger.info("=" * 60)

        await self.initialize()

        # Count files
        self.total_files_count = self._count_all_files()
        logger.info(f"Total files to process: {self.total_files_count}")
        logger.info(f"Already processed: {len(self.processed_files)}")
        remaining = self.total_files_count - len(self.processed_files)
        logger.info(f"Remaining: {remaining}")

        if limit:
            logger.info(f"Limit set to: {limit} files")

        # Start Phase 1 in status manager
        self.status_manager.start_phase1(total_files=self.total_files_count)

        logger.info("-" * 60)
        logger.info("Starting processing...")
        logger.info("-" * 60)

        processed_in_session = 0
        raw_entities_in_session = 0
        new_entities_in_session = 0
        current_source = ""

        try:
            for source_name, filepath, chunk_size in self._get_all_files():
                # Source filter
                if source_filter and source_name != source_filter:
                    continue

                # Limit check
                if limit and processed_in_session >= limit:
                    logger.info(f"Limit reached: {limit} files")
                    break

                # Track source changes
                if source_name != current_source:
                    current_source = source_name
                    logger.info(f"[Source: {source_name}]")

                file_key = str(filepath.relative_to(self.DATA_DIR))

                if file_key in self.processed_files:
                    continue

                # Progress indicator
                progress = len(self.processed_files) / self.total_files_count * 100
                print(f"  [{len(self.processed_files)+1}/{self.total_files_count}] ({progress:.1f}%) {filepath.name[:40]}", end="")

                try:
                    raw_count, new_count = await self.process_file(source_name, filepath, chunk_size)
                    processed_in_session += 1
                    raw_entities_in_session += raw_count
                    new_entities_in_session += new_count
                    print(f" -> {raw_count} raw, {new_count} new")

                except Exception as e:
                    logger.error(f"Error processing {filepath}: {e}")
                    self.processed_files.add(file_key)

                # Status update
                if processed_in_session > 0 and processed_in_session % self.status_interval == 0:
                    self.status_manager.update_phase1(
                        processed_files=len(self.processed_files),
                        total_entities=self.total_entities_raw,
                        total_pending=self.pending_queue.count(),
                        unique_entities=self.entity_registry.get_unique_count()
                    )

                # Checkpoint (less frequent)
                if processed_in_session % self.save_interval == 0:
                    await self._save_checkpoint()

        except KeyboardInterrupt:
            logger.warning("Interrupted by user. Saving checkpoint...")
            await self._save_checkpoint()
            self.status_manager.error_phase1("Interrupted by user")
            return

        except Exception as e:
            logger.error(f"Fatal error: {e}")
            await self._save_checkpoint()
            self.status_manager.error_phase1(str(e))
            raise

        # Final checkpoint
        await self._save_checkpoint()

        # Mark Phase 1 as completed
        self.status_manager.complete_phase1()

        # Final report
        self._print_final_report(processed_in_session, raw_entities_in_session, new_entities_in_session)

    def _print_final_report(self, processed_count: int, raw_count: int, new_count: int):
        """Print final processing report."""
        elapsed = (datetime.now() - self.start_time).total_seconds()

        logger.info("=" * 60)
        logger.info("       PHASE 1 COMPLETE")
        logger.info("=" * 60)
        logger.info(f"Session Statistics:")
        logger.info(f"  Files processed this session: {processed_count}")
        logger.info(f"  Raw entities extracted: {raw_count}")
        logger.info(f"  New unique entities: {new_count}")
        logger.info(f"  Deduplication ratio: {(1 - new_count/raw_count)*100:.1f}% reduced" if raw_count > 0 else "  No entities")
        logger.info(f"  Time elapsed: {elapsed/3600:.2f} hours")

        if elapsed > 0 and processed_count > 0:
            logger.info(f"  Rate: {processed_count/elapsed*3600:.0f} files/hour")

        logger.info(f"Total Progress:")
        logger.info(f"  Total files processed: {len(self.processed_files)}/{self.total_files_count}")
        logger.info(f"  Progress: {len(self.processed_files)/self.total_files_count*100:.1f}%")
        logger.info(f"  Total raw entities: {self.total_entities_raw}")
        logger.info(f"  Total unique entities: {self.entity_registry.get_unique_count()}")
        logger.info(f"  Pending queue size: {self.pending_queue.count()}")

        # Save final results
        self._save_results()

    def _save_results(self):
        """Save final results to JSON."""
        self.RESULTS_DIR.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_file = self.RESULTS_DIR / f"phase1_results_{timestamp}.json"

        results = {
            "timestamp": timestamp,
            "total_files": self.total_files_count,
            "processed_files": len(self.processed_files),
            "total_raw_entities": self.total_entities_raw,
            "total_unique_entities": self.entity_registry.get_unique_count(),
            "pending_queue_size": self.pending_queue.count(),
            "deduplication_ratio": f"{(1 - self.entity_registry.get_unique_count()/self.total_entities_raw)*100:.1f}%" if self.total_entities_raw > 0 else "N/A",
            "note": "Unique entities saved to pending_queue.jsonl for Phase 2 processing"
        }

        with open(results_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

        logger.info(f"Results saved to: {results_file}")


async def main():
    parser = argparse.ArgumentParser(description="Phase 1: NER Extraction with Deduplication (CPU only)")
    parser.add_argument("--limit", type=int, default=None,
                       help="Limit number of files to process")
    parser.add_argument("--source", type=str, default=None,
                       help="Process only specific source (e.g., 'gutenberg')")
    parser.add_argument("--save-interval", type=int, default=50,
                       help="Save checkpoint every N files")
    parser.add_argument("--status-interval", type=int, default=10,
                       help="Update status every N files")
    parser.add_argument("--reset", action="store_true",
                       help="Reset checkpoint and start fresh")
    args = parser.parse_args()

    processor = FullScaleProcessorV3(
        save_interval=args.save_interval,
        status_interval=args.status_interval
    )

    if args.reset:
        # Clear all checkpoint files (V4: include mentions.jsonl)
        for f in ["status.json", "pending_queue.jsonl", "phase1_checkpoint.json", "file_count_cache.json", "mentions.jsonl"]:
            fp = processor.CHECKPOINT_DIR / f
            if fp.exists():
                fp.unlink()
        logger.info("All checkpoints reset.")

    await processor.run(limit=args.limit, source_filter=args.source)


if __name__ == "__main__":
    asyncio.run(main())
