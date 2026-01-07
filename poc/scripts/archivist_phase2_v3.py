"""
Archivist Phase 2 Processing Script V3
- Uses EntityRegistry from Phase 1 to find candidates
- Streaming read for memory efficiency (iter_unprocessed)
- Builds its own "decided registry" for already-processed entities
- LLM compares pending items against existing entities
"""
import asyncio
import json
import sys
import io
from pathlib import Path
from datetime import datetime
import argparse
import logging
import httpx
from typing import Dict, List, Optional

# Fix Windows console encoding
if sys.platform == 'win32':
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True)
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace', line_buffering=True)
    except Exception:
        pass

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.checkpoint import (
    StatusManager, PendingQueue, Phase2Decisions,
    Phase1Checkpoint, EntityRegistry
)

# Configure logging
LOG_DIR = Path(__file__).parent.parent / "data" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / f"phase2_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log", encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class Phase2ProcessorV3:
    """Phase 2 processor with registry-based candidate finding."""

    CHECKPOINT_DIR = Path(__file__).parent.parent / "data"
    OLLAMA_URL = "http://localhost:11434"

    def __init__(self, poll_interval: int = 30, batch_size: int = 50):
        self.poll_interval = poll_interval  # seconds between polls
        self.batch_size = batch_size

        # Checkpoint components
        self.status_manager = StatusManager(self.CHECKPOINT_DIR)
        self.pending_queue = PendingQueue(self.CHECKPOINT_DIR)
        self.decisions = Phase2Decisions(self.CHECKPOINT_DIR)
        self.phase1_checkpoint = Phase1Checkpoint(self.CHECKPOINT_DIR)

        # Registry for candidate finding
        # This is loaded from Phase 1 checkpoint and updated with Phase 2 decisions
        self.entity_registry = EntityRegistry()
        self.decided_entities: Dict[str, Dict] = {}  # entity_key -> final entity info

        self.start_time = None
        self.processed_count = 0
        self.link_existing_count = 0
        self.create_new_count = 0

    def load_registry(self):
        """Load decided entities from previous Phase 2 session (if any)."""
        # Load from Phase 2 decisions file to resume properly
        # We DON'T use Phase 1 registry - that's just for entity merging
        # Phase 2 builds its own registry of decided entities

        if self.decisions.decisions_file.exists():
            # Rebuild decided_entities from previous decisions
            pending_items = {item["id"]: item for item in self.pending_queue.iter_items()}

            for line in open(self.decisions.decisions_file, 'r', encoding='utf-8'):
                if line.strip():
                    decision = json.loads(line)
                    if decision.get("decision") == "CREATE_NEW":
                        pending_id = decision.get("pending_id")
                        if pending_id in pending_items:
                            item = pending_items[pending_id]
                            entity_key = item.get("entity_key", f"{item['entity_type']}:{item['text'].lower()}")
                            mentions = item.get("mentions", [])
                            self.decided_entities[entity_key] = {
                                "text": item["text"],
                                "entity_type": item["entity_type"],
                                "mentions": mentions,
                                "mention_count": item.get("mention_count", len(mentions))
                            }

            if self.decided_entities:
                logger.info(f"Loaded {len(self.decided_entities)} decided entities from previous session")
        else:
            logger.info("No previous Phase 2 decisions found. Starting fresh.")

    async def check_ollama(self) -> bool:
        """Check if Ollama is available."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self.OLLAMA_URL}/api/tags")
                if response.status_code == 200:
                    models = response.json().get("models", [])
                    model_names = [m.get("name", "") for m in models]
                    if any("qwen3" in n for n in model_names):
                        return True
                    logger.warning("qwen3 model not found. Available: " + ", ".join(model_names))
                    return False
        except Exception as e:
            logger.error(f"Ollama connection failed: {e}")
            return False

    async def decide_with_llm(self, item: dict, candidates: List[Dict]) -> dict:
        """Use Qwen3 to decide on a pending item with candidates from registry."""
        text = item.get("text", "")
        entity_type = item.get("entity_type", "")
        sample = item.get("sample", text)[:200]
        entity_key = item.get("entity_key", "")
        mentions = item.get("mentions", [])
        mention_count = item.get("mention_count", len(mentions))

        # If no candidates, create new
        if not candidates:
            return {
                "decision": "CREATE_NEW",
                "linked_entity_key": None,
                "confidence": 0.9,
                "reason": "No similar entities found"
            }

        # If exact match exists, link directly
        for c in candidates:
            if c.get("similarity", 0) >= 1.0:
                return {
                    "decision": "LINK_EXISTING",
                    "linked_entity_key": c.get("key"),
                    "confidence": 0.95,
                    "reason": f"Exact match: {c.get('text')}"
                }

        # Build source info for context
        source_info = ""
        if mentions:
            sources = list(set(m.get("source_path", "") for m in mentions[:3]))
            source_info = f"Found in: {', '.join(sources)}"
            if len(mentions) > 3:
                source_info += f" (+{len(mentions)-3} more)"

        # Build prompt for LLM
        candidates_text = "\n".join([
            f"  {i+1}. {c.get('text')} (similarity: {c.get('similarity', 0):.2f}, mentions: {c.get('mention_count', 1)})"
            for i, c in enumerate(candidates[:5])
        ])

        prompt = f"""You are an entity disambiguation expert for historical data. Determine if this entity refers to an existing entity or is new.

Entity: "{text}" (type: {entity_type})
Mentioned {mention_count} times. {source_info}

Similar existing entities:
{candidates_text}

Instructions:
- If the entity clearly refers to one of the candidates (same person/place/event), respond: LINK <number>
- If the entity is definitely different from all candidates, respond: CREATE_NEW
- Consider the entity type and typical naming conventions.
- Be careful: "Alexander" could be Alexander the Great, Alexander Hamilton, Pope Alexander VI, etc.

Response (LINK <number> or CREATE_NEW):"""

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.OLLAMA_URL}/api/chat",
                    json={
                        "model": "qwen3:8b",
                        "messages": [{"role": "user", "content": prompt}],
                        "stream": False,
                        "options": {"temperature": 0.1}  # Low temperature for consistency
                    }
                )

                if response.status_code == 200:
                    result = response.json()
                    content = result.get("message", {}).get("content", "").strip()

                    # Remove thinking tags if present
                    if "<think>" in content:
                        content = content.split("</think>")[-1].strip()

                    # Parse response
                    if content.upper().startswith("LINK"):
                        parts = content.split()
                        if len(parts) >= 2:
                            try:
                                idx = int(parts[1]) - 1  # 1-indexed to 0-indexed
                                if 0 <= idx < len(candidates):
                                    return {
                                        "decision": "LINK_EXISTING",
                                        "linked_entity_key": candidates[idx].get("key"),
                                        "confidence": 0.8,
                                        "reason": f"LLM linked to: {candidates[idx].get('text')}"
                                    }
                            except ValueError:
                                pass

                    # Default to CREATE_NEW
                    return {
                        "decision": "CREATE_NEW",
                        "linked_entity_key": None,
                        "confidence": 0.7,
                        "reason": "LLM decided to create new entity"
                    }

        except Exception as e:
            logger.error(f"LLM error for '{text}': {e}")
            # On error, be conservative and create new
            return {
                "decision": "CREATE_NEW",
                "linked_entity_key": None,
                "confidence": 0.5,
                "reason": f"LLM error: {str(e)[:50]}"
            }

    async def process_item(self, item: dict) -> bool:
        """Process a single pending item."""
        pending_id = item.get("id")
        text = item.get("text", "")
        entity_type = item.get("entity_type", "")
        entity_key = item.get("entity_key", "")
        mentions = item.get("mentions", [])
        mention_count = item.get("mention_count", len(mentions))

        # Skip if already processed
        if self.decisions.is_processed(pending_id):
            return False

        # Find candidates ONLY from decided entities (not Phase 1 registry!)
        # The first entity of each unique type/name will always be CREATE_NEW
        # Subsequent similar entities will be compared against decided ones
        candidates = []
        normalized_text = EntityRegistry.normalize(text)

        for key, entity in self.decided_entities.items():
            if entity["entity_type"] != entity_type:
                continue

            entity_norm = EntityRegistry.normalize(entity["text"])

            # Calculate similarity
            if normalized_text == entity_norm:
                similarity = 1.0
            elif normalized_text in entity_norm or entity_norm in normalized_text:
                similarity = 0.8
            elif len(set(normalized_text.split()) & set(entity_norm.split())) > 0:
                similarity = 0.5
            else:
                continue

            candidates.append({
                "key": key,
                "text": entity["text"],
                "normalized": entity_norm,
                "entity_type": entity_type,
                "similarity": similarity,
                "mention_count": entity.get("mention_count", 1)
            })

        # Sort by similarity
        candidates.sort(key=lambda x: (-x["similarity"], -x["mention_count"]))

        # Get LLM decision
        result = await self.decide_with_llm(item, candidates)

        # Save decision
        self.decisions.append(
            pending_id=pending_id,
            decision=result["decision"],
            linked_entity_key=result.get("linked_entity_key"),
            confidence=result.get("confidence", 0.0)
        )

        # Update counts and decided entities
        self.processed_count += 1
        if result["decision"] == "LINK_EXISTING":
            self.link_existing_count += 1
            # Update mention count for linked entity
            linked_key = result.get("linked_entity_key")
            if linked_key and linked_key in self.decided_entities:
                self.decided_entities[linked_key]["mention_count"] += mention_count
        else:
            self.create_new_count += 1
            # Add to decided entities for future comparisons
            self.decided_entities[entity_key] = {
                "text": text,
                "entity_type": entity_type,
                "mentions": mentions,
                "mention_count": mention_count
            }

        return True

    async def process_batch(self, items: list) -> int:
        """Process a batch of pending items."""
        processed = 0

        for item in items:
            success = await self.process_item(item)
            if success:
                processed += 1

                # Log progress
                if processed % 10 == 0:
                    logger.info(f"  Batch progress: {processed}/{len(items)}")

        return processed

    async def run(self, continuous: bool = True):
        """Run Phase 2 processing."""
        self.start_time = datetime.now()

        logger.info("=" * 60)
        logger.info("       ARCHIVIST PHASE 2 PROCESSING V3")
        logger.info("       (Registry-based Candidate Finding)")
        logger.info("=" * 60)

        # Check Ollama
        logger.info("Checking Ollama connection...")
        if not await self.check_ollama():
            logger.error("Ollama with qwen3:8b not available!")
            logger.error("Run: ollama serve && ollama pull qwen3:8b")
            return

        logger.info("Ollama OK!")

        # Load entity registry from Phase 1
        self.load_registry()

        # Get initial stats
        total_pending = self.pending_queue.file_count()
        already_processed = self.decisions.get_processed_count()
        logger.info(f"Total pending items: {total_pending}")
        logger.info(f"Already processed: {already_processed}")
        logger.info(f"Remaining: {total_pending - already_processed}")

        if continuous:
            logger.info(f"Continuous mode: polling every {self.poll_interval}s")
            logger.info("-" * 60)

        # Start status tracking
        remaining = total_pending - already_processed
        if remaining > 0:
            self.status_manager.start_phase2(total_pending=remaining)

        while True:
            # Use streaming iterator for memory efficiency
            batch_processed = 0

            for batch in self.decisions.iter_unprocessed(self.pending_queue, batch_size=self.batch_size):
                if not batch:
                    break

                logger.info(f"Processing batch of {len(batch)} items...")
                processed = await self.process_batch(batch)
                batch_processed += processed

                # Update status
                self.status_manager.update_phase2(
                    processed=self.processed_count,
                    link_existing=self.link_existing_count,
                    create_new=self.create_new_count
                )

                logger.info(f"Batch done. Total: {self.processed_count} (LINK: {self.link_existing_count}, NEW: {self.create_new_count})")

            # No more items to process
            if batch_processed == 0:
                # Check if Phase 1 is still running
                status = self.status_manager.get_status()
                phase1_status = status.get("phase1", {}).get("status", "idle")

                if phase1_status == "completed" and not continuous:
                    logger.info("Phase 1 completed and no more pending items. Done!")
                    break
                elif phase1_status == "completed":
                    logger.info("Phase 1 completed. Checking for final items...")
                    await asyncio.sleep(self.poll_interval)

                    # Reload pending queue to check for new items
                    self.pending_queue = PendingQueue(self.CHECKPOINT_DIR)
                    if self.decisions.get_unprocessed_count(self.pending_queue) == 0:
                        logger.info("No more items. Phase 2 complete!")
                        break
                else:
                    logger.info(f"No pending items. Phase 1 status: {phase1_status}. Waiting...")
                    await asyncio.sleep(self.poll_interval)
                    # Reload pending queue
                    self.pending_queue = PendingQueue(self.CHECKPOINT_DIR)
                    continue

            if not continuous:
                break

            # Small delay between batches
            await asyncio.sleep(1)

        # Mark complete
        self.status_manager.complete_phase2()

        # Final report
        self._print_final_report()

    def _print_final_report(self):
        """Print final report."""
        elapsed = (datetime.now() - self.start_time).total_seconds()

        logger.info("=" * 60)
        logger.info("       PHASE 2 COMPLETE")
        logger.info("=" * 60)
        logger.info(f"Total processed: {self.processed_count}")
        logger.info(f"  LINK_EXISTING: {self.link_existing_count} ({self.link_existing_count/self.processed_count*100:.1f}%)" if self.processed_count > 0 else "  LINK_EXISTING: 0")
        logger.info(f"  CREATE_NEW: {self.create_new_count} ({self.create_new_count/self.processed_count*100:.1f}%)" if self.processed_count > 0 else "  CREATE_NEW: 0")
        logger.info(f"Time elapsed: {elapsed/3600:.2f} hours")
        if elapsed > 0 and self.processed_count > 0:
            logger.info(f"Rate: {self.processed_count/elapsed*3600:.0f} items/hour")

        # Save summary
        self._save_summary()

    def _save_summary(self):
        """Save Phase 2 summary."""
        summary_file = self.CHECKPOINT_DIR / "phase2_summary.json"

        summary = {
            "timestamp": datetime.now().isoformat(),
            "total_processed": self.processed_count,
            "link_existing": self.link_existing_count,
            "create_new": self.create_new_count,
            "link_ratio": f"{self.link_existing_count/self.processed_count*100:.1f}%" if self.processed_count > 0 else "N/A"
        }

        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)

        logger.info(f"Summary saved to: {summary_file}")


async def main():
    parser = argparse.ArgumentParser(description="Archivist Phase 2 Processing V3")
    parser.add_argument("--poll-interval", type=int, default=30,
                       help="Seconds between polling for new items")
    parser.add_argument("--batch-size", type=int, default=50,
                       help="Number of items to process per batch")
    parser.add_argument("--once", action="store_true",
                       help="Process once and exit (don't poll continuously)")
    args = parser.parse_args()

    processor = Phase2ProcessorV3(
        poll_interval=args.poll_interval,
        batch_size=args.batch_size
    )

    await processor.run(continuous=not args.once)


if __name__ == "__main__":
    asyncio.run(main())
