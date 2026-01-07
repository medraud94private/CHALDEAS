"""
Archivist Phase 2: Review PENDING items with LLM
Processes PENDING decisions from fast mode using Qwen for accurate disambiguation.
"""
import asyncio
import json
import os
import sys
import io
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

# Fix Windows console encoding
if sys.platform == 'win32':
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True)
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace', line_buffering=True)
    except Exception:
        pass

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.extraction.ner_pipeline import test_ollama_connection
from app.core.archivist import Archivist, EntityRegistry, EntityRecord, Decision


class PendingReviewer:
    """Reviews PENDING items from fast mode using LLM."""

    CHECKPOINT_FILE = Path(__file__).parent.parent / "data" / "archivist_checkpoint.json"
    RESULTS_DIR = Path(__file__).parent.parent / "data" / "archivist_results"
    REVIEW_CHECKPOINT = Path(__file__).parent.parent / "data" / "pending_review_checkpoint.json"

    def __init__(self):
        self.archivist = None
        self.pending_items = []
        self.reviewed_count = 0
        self.resolved_count = 0

    async def initialize(self):
        """Initialize with checkpoint data."""
        print("Checking Ollama connection...")
        if not await test_ollama_connection():
            raise RuntimeError("Ollama not available for Phase 2. Run: ollama serve && ollama pull qwen3:8b")
        print("Ollama OK!")

        # Load Phase 1 checkpoint
        if not self.CHECKPOINT_FILE.exists():
            raise RuntimeError("No checkpoint found. Run Phase 1 first.")

        with open(self.CHECKPOINT_FILE, 'r', encoding='utf-8') as f:
            checkpoint = json.load(f)

        # Rebuild registry from checkpoint
        print("Rebuilding entity registry from checkpoint...")
        self.archivist = Archivist(fast_mode=False)  # Use LLM mode

        registry_data = checkpoint.get("registry_snapshot", {})
        for entity_data in registry_data.get("entities", []):
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

        print(f"Loaded {len(self.archivist.registry.entities)} entities from checkpoint")

        # Find all PENDING items from results files
        await self._load_pending_items()

        # Load review checkpoint if exists
        await self._load_review_checkpoint()

    async def _load_pending_items(self):
        """Load PENDING items from checkpoint."""
        self.pending_items = []

        # Load from checkpoint (primary source)
        if self.CHECKPOINT_FILE.exists():
            with open(self.CHECKPOINT_FILE, 'r', encoding='utf-8') as f:
                checkpoint = json.load(f)

            pending_items = checkpoint.get("pending_items", [])
            pending_count = checkpoint.get("pending_count", 0)

            if pending_items:
                self.pending_items = pending_items
                print(f"Loaded {len(pending_items)} pending items from checkpoint")
                print(f"Total pending in Phase 1: {pending_count}")
            else:
                print(f"No pending items in checkpoint (total was: {pending_count})")

        # Also check result files for additional pending items
        if self.RESULTS_DIR.exists():
            for result_file in sorted(self.RESULTS_DIR.glob("fullscale_results_*.json")):
                try:
                    with open(result_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)

                    stats = data.get("stats", {}).get("decisions", {})
                    pending_count = stats.get("pending_count", 0)

                    if pending_count > 0:
                        print(f"Found {pending_count} pending in {result_file.name}")

                except Exception as e:
                    print(f"Error reading {result_file}: {e}")

        print(f"Total pending items for review: {len(self.pending_items)}")

    async def _load_review_checkpoint(self):
        """Load review progress checkpoint."""
        if self.REVIEW_CHECKPOINT.exists():
            try:
                with open(self.REVIEW_CHECKPOINT, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self.reviewed_count = data.get("reviewed_count", 0)
                self.resolved_count = data.get("resolved_count", 0)
                print(f"Resuming from review checkpoint: {self.reviewed_count} already reviewed")
            except Exception:
                pass

    async def _save_review_checkpoint(self):
        """Save review progress."""
        checkpoint = {
            "timestamp": datetime.now().isoformat(),
            "reviewed_count": self.reviewed_count,
            "resolved_count": self.resolved_count,
            "registry_size": len(self.archivist.registry.entities)
        }

        with open(self.REVIEW_CHECKPOINT, 'w', encoding='utf-8') as f:
            json.dump(checkpoint, f, indent=2)

    async def run(self):
        """Run LLM review of PENDING items."""
        print("\n" + "="*60)
        print("       PHASE 2: LLM REVIEW OF PENDING ITEMS")
        print("="*60 + "\n")

        await self.initialize()

        if not self.pending_items:
            print("No PENDING items to review. Phase 2 complete!")
            return

        print(f"\nReviewing {len(self.pending_items)} pending items...")
        print("-"*60 + "\n")

        start_time = datetime.now()

        for i, item in enumerate(self.pending_items[self.reviewed_count:], self.reviewed_count + 1):
            text = item.get("text", "")
            entity_type = item.get("entity_type", "")
            context = item.get("context", "")[:500]

            print(f"[{i}/{len(self.pending_items)}] Reviewing: {text} ({entity_type})")

            try:
                decision, entity = await self.archivist.process_entity(
                    text=text,
                    entity_type=entity_type,
                    context=context,
                    source=item.get("source", "review")
                )

                if decision.decision != Decision.PENDING:
                    self.resolved_count += 1
                    print(f"  -> {decision.decision.value} (confidence: {decision.confidence:.2f})")
                else:
                    print(f"  -> Still PENDING")

                self.reviewed_count += 1

            except Exception as e:
                print(f"  -> Error: {e}")
                self.reviewed_count += 1

            # Save checkpoint periodically
            if i % 50 == 0:
                await self._save_review_checkpoint()
                elapsed = (datetime.now() - start_time).total_seconds()
                rate = i / elapsed * 3600 if elapsed > 0 else 0
                remaining = len(self.pending_items) - i
                eta = remaining / (rate / 3600) if rate > 0 else 0
                print(f"\n  === Progress: {i}/{len(self.pending_items)}, "
                      f"Rate: {rate:.0f}/hour, ETA: {eta/3600:.1f}h ===\n")

        # Final save
        await self._save_review_checkpoint()

        # Report
        elapsed = (datetime.now() - start_time).total_seconds()
        print("\n" + "="*60)
        print("       PHASE 2 COMPLETE")
        print("="*60)
        print(f"\nReviewed: {self.reviewed_count}")
        print(f"Resolved: {self.resolved_count} ({self.resolved_count/max(self.reviewed_count,1)*100:.1f}%)")
        print(f"Time: {elapsed/3600:.2f} hours")
        print(f"Final registry size: {len(self.archivist.registry.entities)}")

        # Save final results
        self._save_final_results()

    def _save_final_results(self):
        """Save final Phase 2 results."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_file = self.RESULTS_DIR / f"phase2_results_{timestamp}.json"

        results = {
            "timestamp": timestamp,
            "reviewed_count": self.reviewed_count,
            "resolved_count": self.resolved_count,
            "final_registry_size": len(self.archivist.registry.entities),
            "stats": self.archivist.get_stats()
        }

        with open(results_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

        print(f"Results saved to: {results_file}")


async def main():
    reviewer = PendingReviewer()
    await reviewer.run()


if __name__ == "__main__":
    asyncio.run(main())
