"""
Archivist Full-Scale Processing Script
Processes all 76,000+ files with checkpointing and resumability.
"""
import asyncio
import json
import os
import sys
import io
import hashlib
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional, Generator
from dataclasses import dataclass, asdict
import argparse

# Fix Windows console encoding
if sys.platform == 'win32':
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True)
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace', line_buffering=True)
    except Exception:
        pass

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.extraction.ner_pipeline import HybridNERPipeline, test_ollama_connection
from app.core.archivist import Archivist, EntityRegistry, Decision


@dataclass
class ProcessingCheckpoint:
    """Checkpoint for resumable processing."""
    timestamp: str
    processed_files: List[str]
    total_files: int
    total_entities: int
    total_decisions: int
    current_source: str
    registry_snapshot: Dict[str, Any]


class FullScaleProcessor:
    """Full-scale data processor with checkpointing."""

    DATA_DIR = Path(__file__).parent.parent.parent / "data" / "raw"
    RESULTS_DIR = Path(__file__).parent.parent / "data" / "archivist_results"
    CHECKPOINT_FILE = Path(__file__).parent.parent / "data" / "archivist_checkpoint.json"

    # All data sources with their configurations
    SOURCES = {
        "british_library": {
            "dir": "british_library/extracted",
            "patterns": ["*.json"],
            "priority": 1,  # Process first (largest)
            "chunk_size": 3000,  # Smaller chunks for large files
        },
        "gutenberg": {
            "dir": "gutenberg",
            "patterns": ["pg*.txt"],
            "priority": 2,
            "chunk_size": 5000,
        },
        "perseus": {
            "dir": "perseus",
            "patterns": ["*.json"],
            "priority": 3,
            "chunk_size": 5000,
        },
        "britannica_1911": {
            "dir": "britannica_1911",
            "patterns": ["*.json"],
            "priority": 4,
            "chunk_size": 5000,
        },
        "open_library": {
            "dir": "open_library",
            "patterns": ["*.json"],
            "priority": 5,
            "chunk_size": 5000,
        },
        "theoi": {
            "dir": "theoi",
            "patterns": ["*.json"],
            "priority": 6,
            "chunk_size": 5000,
        },
        "ctext": {
            "dir": "ctext",
            "patterns": ["*.json"],
            "priority": 7,
            "chunk_size": 5000,
        },
        "arthurian": {
            "dir": "arthurian",
            "patterns": ["*.txt"],
            "priority": 8,
            "chunk_size": 5000,
        },
        "stanford_encyclopedia": {
            "dir": "stanford_encyclopedia",
            "patterns": ["*.json"],
            "priority": 9,
            "chunk_size": 5000,
        },
        "worldhistory": {
            "dir": "worldhistory",
            "patterns": ["*.json"],
            "priority": 10,
            "chunk_size": 5000,
        },
        "pantheon": {
            "dir": "pantheon",
            "patterns": ["*.json"],
            "priority": 11,
            "chunk_size": 5000,
        },
        "sacred_texts": {
            "dir": "sacred_texts",
            "patterns": ["*.json", "*.txt"],
            "priority": 12,
            "chunk_size": 5000,
        },
        "avalon": {
            "dir": "avalon",
            "patterns": ["*.json", "*.txt"],
            "priority": 13,
            "chunk_size": 5000,
        },
        "fordham": {
            "dir": "fordham",
            "patterns": ["*.json", "*.txt"],
            "priority": 14,
            "chunk_size": 5000,
        },
        "topostext": {
            "dir": "topostext",
            "patterns": ["*.json"],
            "priority": 15,
            "chunk_size": 5000,
        },
        "pleiades": {
            "dir": "pleiades",
            "patterns": ["*.json"],
            "priority": 16,
            "chunk_size": 5000,
        },
        "indian_mythology": {
            "dir": "indian_mythology",
            "patterns": ["*.json", "*.txt"],
            "priority": 17,
            "chunk_size": 5000,
        },
        "mesoamerican": {
            "dir": "mesoamerican",
            "patterns": ["*.json", "*.txt"],
            "priority": 18,
            "chunk_size": 5000,
        },
        "russian_history": {
            "dir": "russian_history",
            "patterns": ["*.json", "*.txt"],
            "priority": 19,
            "chunk_size": 5000,
        },
    }

    def __init__(self, batch_size: int = 100, save_interval: int = 50, fast_mode: bool = True):
        self.batch_size = batch_size
        self.save_interval = save_interval
        self.fast_mode = fast_mode  # Use rule-based matching (no LLM)
        self.ner = None
        self.archivist = None
        self.processed_files: set = set()
        self.start_time = None
        self.total_files_count = 0
        self.current_file_index = 0

    async def initialize(self):
        """Initialize NER and Archivist."""
        if not self.fast_mode:
            print("Checking Ollama connection...")
            if not await test_ollama_connection():
                raise RuntimeError("Ollama not available. Run: ollama serve && ollama pull qwen3:8b")
            print("Ollama OK!")
        else:
            print("Fast mode enabled - skipping Ollama check")

        mode_str = "FAST (rule-based)" if self.fast_mode else "NORMAL (LLM)"
        print(f"Initializing NER pipeline (spaCy only) and Archivist ({mode_str})...")
        self.ner = HybridNERPipeline(use_llm_verification=False)
        self.archivist = Archivist(fast_mode=self.fast_mode)

        # Load checkpoint if exists
        await self._load_checkpoint()

    async def _load_checkpoint(self):
        """Load checkpoint if exists."""
        if self.CHECKPOINT_FILE.exists():
            try:
                with open(self.CHECKPOINT_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self.processed_files = set(data.get("processed_files", []))
                print(f"Loaded checkpoint: {len(self.processed_files)} files already processed")

                # Restore registry if available
                registry_data = data.get("registry_snapshot", {})
                if registry_data.get("entities"):
                    print(f"Restoring {len(registry_data['entities'])} entities from checkpoint...")
                    for entity_data in registry_data["entities"]:
                        from app.core.archivist import EntityRecord
                        entity = EntityRecord(
                            id=entity_data["id"],
                            text=entity_data["text"],
                            normalized=entity_data["normalized"],
                            entity_type=entity_data["entity_type"],
                            context_snippet=entity_data.get("context_snippet", ""),
                            aliases=entity_data.get("aliases", []),
                            sources=entity_data.get("sources", [])
                        )
                        self.archivist.registry.entities[entity.id] = entity
                        self.archivist.registry.next_id = max(self.archivist.registry.next_id, entity.id + 1)

                        # Rebuild indexes
                        norm_name = entity.normalized.lower()
                        if norm_name not in self.archivist.registry._name_index:
                            self.archivist.registry._name_index[norm_name] = []
                        self.archivist.registry._name_index[norm_name].append(entity.id)

                        if entity.entity_type not in self.archivist.registry._type_index:
                            self.archivist.registry._type_index[entity.entity_type] = []
                        self.archivist.registry._type_index[entity.entity_type].append(entity.id)

            except Exception as e:
                print(f"Error loading checkpoint: {e}")
                self.processed_files = set()

    async def _save_checkpoint(self, current_source: str):
        """Save checkpoint for resumability."""
        self.RESULTS_DIR.mkdir(parents=True, exist_ok=True)

        # Serialize registry entities
        entities_data = []
        for entity in self.archivist.registry.entities.values():
            entities_data.append({
                "id": entity.id,
                "text": entity.text,
                "normalized": entity.normalized,
                "entity_type": entity.entity_type,
                "context_snippet": entity.context_snippet,
                "aliases": entity.aliases,
                "sources": entity.sources[:10]  # Limit sources for file size
            })

        # Save pending items for Phase 2 review (including candidates!)
        pending_items = []
        for item in self.archivist.pending_queue[-1000:]:  # Last 1000 pending items
            pending_items.append({
                "text": item.get("text", ""),
                "entity_type": item.get("entity_type", ""),
                "context": item.get("context", "")[:500],
                "candidates": item.get("candidates", []),  # Critical for Phase 2!
                "source": "pending_queue"
            })

        checkpoint = {
            "timestamp": datetime.now().isoformat(),
            "processed_files": list(self.processed_files),
            "total_files": self.total_files_count,
            "total_entities": len(self.archivist.registry.entities),
            "total_decisions": self.archivist._stats.total_decisions,
            "current_source": current_source,
            "registry_snapshot": {
                "entities": entities_data
            },
            "pending_items": pending_items,
            "pending_count": len(self.archivist.pending_queue),
            "stats": self.archivist.get_stats()
        }

        with open(self.CHECKPOINT_FILE, 'w', encoding='utf-8') as f:
            json.dump(checkpoint, f, ensure_ascii=False, indent=2)

        print(f"  [Checkpoint saved: {len(self.processed_files)} files, {len(entities_data)} entities]")

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

                # Extract text from various JSON formats
                if isinstance(data, dict):
                    content = data.get("content") or data.get("text") or data.get("body") or ""
                    if not content and "fulltext" in data:
                        content = data["fulltext"]
                    if not content:
                        # Try to concatenate all string values
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
            print(f"  Error loading {filepath}: {e}")
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
                # Get surrounding context
                ctx_start = max(0, entity.start - 100)
                ctx_end = min(len(content), entity.end + 100)
                context = content[ctx_start:ctx_end]

                try:
                    decision, record = await self.archivist.process_entity(
                        text=entity.text,
                        entity_type=entity.entity_type,
                        context=context,
                        source=file_key
                    )
                    entity_count += 1
                except Exception as e:
                    print(f"    Error processing entity '{entity.text}': {e}")

        self.processed_files.add(file_key)
        return entity_count

    async def run(self, limit: int = None, source_filter: str = None):
        """Run full-scale processing."""
        self.start_time = datetime.now()

        print("\n" + "="*60)
        print("       ARCHIVIST FULL-SCALE PROCESSING")
        print("="*60 + "\n")

        await self.initialize()

        # Count files
        print("Counting files...")
        self.total_files_count = self._count_all_files()
        print(f"Total files to process: {self.total_files_count}")
        print(f"Already processed: {len(self.processed_files)}")
        remaining = self.total_files_count - len(self.processed_files)
        print(f"Remaining: {remaining}")

        if limit:
            print(f"Limit set to: {limit} files")

        print("\n" + "-"*60)
        print("Starting processing...")
        print("-"*60 + "\n")

        processed_in_session = 0
        entities_in_session = 0
        current_source = ""

        for source_name, filepath, chunk_size in self._get_all_files():
            # Source filter
            if source_filter and source_name != source_filter:
                continue

            # Limit check
            if limit and processed_in_session >= limit:
                print(f"\nLimit reached: {limit} files")
                break

            # Track source changes
            if source_name != current_source:
                current_source = source_name
                print(f"\n[Source: {source_name}]")

            self.current_file_index += 1
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
                print(f" -> ERROR: {e}")
                self.processed_files.add(file_key)  # Mark as processed to skip on retry

            # Periodic checkpoint
            if processed_in_session % self.save_interval == 0:
                await self._save_checkpoint(current_source)

            # Periodic stats
            if processed_in_session % 100 == 0:
                self._print_progress_stats()

        # Final checkpoint
        await self._save_checkpoint(current_source)

        # Final report
        self._print_final_report(processed_in_session, entities_in_session)

    def _print_progress_stats(self):
        """Print progress statistics."""
        elapsed = (datetime.now() - self.start_time).total_seconds()
        processed = len(self.processed_files)
        remaining = self.total_files_count - processed

        if elapsed > 0 and processed > 0:
            rate = processed / elapsed * 3600  # files per hour
            eta_hours = remaining / rate if rate > 0 else 0

            print(f"\n  === Progress: {processed}/{self.total_files_count} " +
                  f"({processed/self.total_files_count*100:.1f}%) ===")
            print(f"  Rate: {rate:.0f} files/hour, ETA: {eta_hours:.1f} hours")
            print(f"  Entities: {len(self.archivist.registry.entities)}")
            print()

    def _print_final_report(self, processed_count: int, entity_count: int):
        """Print final processing report."""
        elapsed = (datetime.now() - self.start_time).total_seconds()

        print("\n" + "="*60)
        print("       PROCESSING COMPLETE")
        print("="*60)
        print(f"\nSession Statistics:")
        print(f"  Files processed this session: {processed_count}")
        print(f"  Entities processed this session: {entity_count}")
        print(f"  Time elapsed: {elapsed/3600:.2f} hours")

        if elapsed > 0 and processed_count > 0:
            print(f"  Rate: {processed_count/elapsed*3600:.0f} files/hour")

        print(f"\nTotal Progress:")
        print(f"  Total files processed: {len(self.processed_files)}/{self.total_files_count}")
        print(f"  Progress: {len(self.processed_files)/self.total_files_count*100:.1f}%")

        print("\n" + self.archivist.get_report())

        # Save final results
        self._save_results()

    def _save_results(self):
        """Save final results to JSON."""
        self.RESULTS_DIR.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_file = self.RESULTS_DIR / f"fullscale_results_{timestamp}.json"

        results = {
            "timestamp": timestamp,
            "total_files": self.total_files_count,
            "processed_files": len(self.processed_files),
            "stats": self.archivist.get_stats(),
            "entities": [
                {
                    "id": e.id,
                    "text": e.text,
                    "normalized": e.normalized,
                    "type": e.entity_type,
                    "aliases": e.aliases[:10],
                    "sources": e.sources[:10]
                }
                for e in list(self.archivist.registry.entities.values())[:1000]
            ]
        }

        with open(results_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

        print(f"\nResults saved to: {results_file}")


async def main():
    parser = argparse.ArgumentParser(description="Archivist Full-Scale Processing")
    parser.add_argument("--limit", type=int, default=None,
                       help="Limit number of files to process")
    parser.add_argument("--source", type=str, default=None,
                       help="Process only specific source (e.g., 'gutenberg')")
    parser.add_argument("--batch-size", type=int, default=100,
                       help="Batch size for processing")
    parser.add_argument("--save-interval", type=int, default=50,
                       help="Save checkpoint every N files")
    parser.add_argument("--reset", action="store_true",
                       help="Reset checkpoint and start fresh")
    parser.add_argument("--slow", action="store_true",
                       help="Use LLM (Qwen) for decisions (default: fast rule-based mode)")
    args = parser.parse_args()

    processor = FullScaleProcessor(
        batch_size=args.batch_size,
        save_interval=args.save_interval,
        fast_mode=not args.slow  # Default is fast mode
    )

    if args.reset:
        if processor.CHECKPOINT_FILE.exists():
            processor.CHECKPOINT_FILE.unlink()
            print("Checkpoint reset.")

    await processor.run(limit=args.limit, source_filter=args.source)


if __name__ == "__main__":
    asyncio.run(main())
