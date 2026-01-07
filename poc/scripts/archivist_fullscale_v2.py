"""
Archivist Full-Scale Processing Script V2
- Uses new checkpoint system (StatusManager, PendingQueue, Phase1Checkpoint)
- JSONL-based append-only PENDING queue
- Real-time progress tracking via status.json
- Safe resumability
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
from app.core.checkpoint import StatusManager, PendingQueue, Phase1Checkpoint


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


class FullScaleProcessorV2:
    """Full-scale data processor with improved checkpoint system."""

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

    def __init__(self, save_interval: int = 50, status_interval: int = 1):
        self.save_interval = save_interval      # Checkpoint every N files
        self.status_interval = status_interval  # Status update every N files

        self.ner = None

        # New checkpoint components
        self.status_manager = StatusManager(self.CHECKPOINT_DIR)
        self.pending_queue = PendingQueue(self.CHECKPOINT_DIR)
        self.phase1_checkpoint = Phase1Checkpoint(self.CHECKPOINT_DIR)

        self.processed_files: set = set()
        self.start_time = None
        self.total_files_count = 0
        self.total_entities = 0
        self.total_pending = 0

    async def initialize(self):
        """Initialize NER pipeline (CPU only, no LLM)."""
        logger.info("Initializing NER pipeline (spaCy only, CPU)...")
        logger.info("Phase 1: NER extraction only → pending_queue")
        logger.info("Phase 2 (separate process): LLM processing from pending_queue")

        self.ner = HybridNERPipeline(use_llm_verification=False)

        # Load from checkpoint if exists
        await self._load_checkpoint()

    async def _load_checkpoint(self):
        """Load from Phase1Checkpoint if exists."""
        checkpoint_data = self.phase1_checkpoint.load()

        if checkpoint_data:
            self.processed_files = set(checkpoint_data.get("processed_files", []))
            logger.info(f"Loaded checkpoint: {len(self.processed_files)} files already processed")

        # Get existing pending count
        self.total_pending = self.pending_queue.count()
        self.total_entities = self.total_pending  # In new design, all entities go to pending
        logger.info(f"Existing pending queue: {self.total_pending} items")

    async def _save_checkpoint(self):
        """Save Phase1Checkpoint (processed files only, entities are in pending_queue)."""
        self.phase1_checkpoint.save(
            processed_files=list(self.processed_files),
            registry_entities=[],  # No registry in Phase 1, all entities go to pending_queue
            next_entity_id=0
        )

        logger.info(f"[Checkpoint] {len(self.processed_files)} files, {self.total_pending} entities in queue")

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
        """Count all files to process."""
        count = 0
        for _ in self._get_all_files():
            count += 1
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

    async def process_file(self, source_name: str, filepath: Path, chunk_size: int) -> int:
        """Process a single file and return entity count."""
        file_key = str(filepath.relative_to(self.DATA_DIR))

        if file_key in self.processed_files:
            return 0

        content = self._load_file_content(filepath)
        if not content or len(content) < 50:
            self.processed_files.add(file_key)
            return 0

        # Extract entities using spaCy (fast)
        entities = await self.ner.extract_entities(content[:chunk_size])

        entity_count = 0
        for entity in entities:
            if entity.entity_type in ["person", "location", "event"]:
                ctx_start = max(0, entity.start - 100)
                ctx_end = min(len(content), entity.end + 100)
                context = content[ctx_start:ctx_end]

                # Phase 1: NER 추출만! 모든 엔티티를 pending_queue로 (LLM 호출 없음)
                self.pending_queue.append(
                    text=entity.text,
                    entity_type=entity.entity_type,
                    context=context,
                    candidates=[],  # Phase 2에서 LLM이 판단
                    source=file_key
                )
                entity_count += 1
                self.total_entities += 1
                self.total_pending += 1

        self.processed_files.add(file_key)
        return entity_count

    async def run(self, limit: int = None, source_filter: str = None):
        """Run full-scale processing."""
        self.start_time = datetime.now()

        logger.info("=" * 60)
        logger.info("       ARCHIVIST FULL-SCALE PROCESSING V2")
        logger.info("=" * 60)

        await self.initialize()

        # Count files
        logger.info("Counting files...")
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
        entities_in_session = 0
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
                print(f"  [{len(self.processed_files)+1}/{self.total_files_count}] ({progress:.1f}%) {filepath.name[:50]}", end="")

                try:
                    entity_count = await self.process_file(source_name, filepath, chunk_size)
                    processed_in_session += 1
                    entities_in_session += entity_count
                    print(f" -> {entity_count} entities")

                except Exception as e:
                    logger.error(f"Error processing {filepath}: {e}")
                    self.processed_files.add(file_key)

                # Status update (every file when status_interval=1)
                if processed_in_session > 0 and processed_in_session % self.status_interval == 0:
                    self.status_manager.update_phase1(
                        processed_files=len(self.processed_files),
                        total_entities=self.total_entities,
                        total_pending=self.total_pending
                    )
                    logger.debug(f"Status updated: {len(self.processed_files)} files")

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
        self._print_final_report(processed_in_session, entities_in_session)

    def _print_final_report(self, processed_count: int, entity_count: int):
        """Print final processing report."""
        elapsed = (datetime.now() - self.start_time).total_seconds()

        logger.info("=" * 60)
        logger.info("       PHASE 1 COMPLETE")
        logger.info("=" * 60)
        logger.info(f"Session Statistics:")
        logger.info(f"  Files processed this session: {processed_count}")
        logger.info(f"  Entities processed this session: {entity_count}")
        logger.info(f"  Time elapsed: {elapsed/3600:.2f} hours")

        if elapsed > 0 and processed_count > 0:
            logger.info(f"  Rate: {processed_count/elapsed*3600:.0f} files/hour")

        logger.info(f"Total Progress:")
        logger.info(f"  Total files processed: {len(self.processed_files)}/{self.total_files_count}")
        logger.info(f"  Progress: {len(self.processed_files)/self.total_files_count*100:.1f}%")
        logger.info(f"  Total entities: {self.total_entities}")
        logger.info(f"  Total pending (for Phase 2): {self.total_pending}")

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
            "total_entities": self.total_entities,
            "total_pending": self.total_pending,
            "note": "All entities saved to pending_queue.jsonl for Phase 2 processing"
        }

        with open(results_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

        logger.info(f"Results saved to: {results_file}")


async def main():
    parser = argparse.ArgumentParser(description="Phase 1: NER Extraction (CPU only)")
    parser.add_argument("--limit", type=int, default=None,
                       help="Limit number of files to process")
    parser.add_argument("--source", type=str, default=None,
                       help="Process only specific source (e.g., 'gutenberg')")
    parser.add_argument("--save-interval", type=int, default=50,
                       help="Save checkpoint every N files")
    parser.add_argument("--status-interval", type=int, default=1,
                       help="Update status every N files")
    parser.add_argument("--reset", action="store_true",
                       help="Reset checkpoint and start fresh")
    args = parser.parse_args()

    processor = FullScaleProcessorV2(
        save_interval=args.save_interval,
        status_interval=args.status_interval
    )

    if args.reset:
        # Clear all checkpoint files
        for f in ["status.json", "pending_queue.jsonl", "phase1_checkpoint.json"]:
            fp = processor.CHECKPOINT_DIR / f
            if fp.exists():
                fp.unlink()
        logger.info("All checkpoints reset.")

    await processor.run(limit=args.limit, source_filter=args.source)


if __name__ == "__main__":
    asyncio.run(main())
