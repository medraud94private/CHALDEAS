"""
Archivist Phase 2 Processing Script V2
- Uses new checkpoint system (StatusManager, PendingQueue, Phase2Decisions)
- Polls pending_queue.jsonl for new items
- Saves decisions to phase2_decisions.jsonl (append-only)
- Can run in parallel with Phase 1
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

# Fix Windows console encoding
if sys.platform == 'win32':
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True)
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace', line_buffering=True)
    except Exception:
        pass

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.checkpoint import StatusManager, PendingQueue, Phase2Decisions

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


class Phase2ProcessorV2:
    """Phase 2 processor using new checkpoint system."""

    CHECKPOINT_DIR = Path(__file__).parent.parent / "data"
    OLLAMA_URL = "http://localhost:11434"

    def __init__(self, poll_interval: int = 30, batch_size: int = 50):
        self.poll_interval = poll_interval  # seconds between polls
        self.batch_size = batch_size

        # Checkpoint components
        self.status_manager = StatusManager(self.CHECKPOINT_DIR)
        self.pending_queue = PendingQueue(self.CHECKPOINT_DIR)
        self.decisions = Phase2Decisions(self.CHECKPOINT_DIR)

        self.start_time = None
        self.processed_count = 0
        self.link_existing_count = 0
        self.create_new_count = 0

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

    async def decide_with_llm(self, item: dict) -> dict:
        """Use Qwen3 to decide on a pending item."""
        text = item.get("text", "")
        entity_type = item.get("entity_type", "")
        context = item.get("context", "")[:500]
        candidates = item.get("candidates", [])

        # If no candidates, must create new
        if not candidates:
            return {
                "decision": "CREATE_NEW",
                "linked_entity_id": None,
                "confidence": 0.9
            }

        # Build prompt
        candidates_text = "\n".join([
            f"  {i+1}. ID={c.get('id')}: {c.get('normalized')} (similarity: {c.get('similarity', 0):.2f})"
            for i, c in enumerate(candidates[:5])
        ])

        prompt = f"""You are an entity disambiguation expert. Determine if the mentioned entity refers to an existing entity or is new.

Entity: "{text}" (type: {entity_type})
Context: "{context}"

Existing candidates:
{candidates_text}

Instructions:
- If the entity clearly refers to one of the candidates, respond: LINK <ID>
- If the entity is definitely different from all candidates, respond: CREATE_NEW
- Consider context, time period, and entity type when deciding.

Response (LINK <ID> or CREATE_NEW):"""

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.OLLAMA_URL}/api/chat",
                    json={
                        "model": "qwen3:8b",
                        "messages": [{"role": "user", "content": prompt}],
                        "stream": False,
                        "think": False  # Disable thinking mode
                    }
                )

                if response.status_code == 200:
                    result = response.json()
                    content = result.get("message", {}).get("content", "").strip()

                    # Parse response
                    if content.startswith("LINK"):
                        parts = content.split()
                        if len(parts) >= 2:
                            try:
                                linked_id = int(parts[1])
                                return {
                                    "decision": "LINK_EXISTING",
                                    "linked_entity_id": linked_id,
                                    "confidence": 0.8
                                }
                            except ValueError:
                                pass

                    # Default to CREATE_NEW
                    return {
                        "decision": "CREATE_NEW",
                        "linked_entity_id": None,
                        "confidence": 0.7
                    }

        except Exception as e:
            logger.error(f"LLM error for '{text}': {e}")
            # On error, be conservative and create new
            return {
                "decision": "CREATE_NEW",
                "linked_entity_id": None,
                "confidence": 0.5
            }

    async def process_batch(self, items: list) -> int:
        """Process a batch of pending items."""
        processed = 0

        for item in items:
            pending_id = item.get("id")

            # Skip if already processed
            if self.decisions.is_processed(pending_id):
                continue

            # Get LLM decision
            result = await self.decide_with_llm(item)

            # Save decision
            self.decisions.append(
                pending_id=pending_id,
                decision=result["decision"],
                linked_entity_id=result.get("linked_entity_id"),
                confidence=result.get("confidence", 0.0)
            )

            # Update counts
            self.processed_count += 1
            if result["decision"] == "LINK_EXISTING":
                self.link_existing_count += 1
            else:
                self.create_new_count += 1

            processed += 1

            # Log progress
            if processed % 10 == 0:
                logger.info(f"  Processed {processed}/{len(items)} in batch")

        return processed

    async def run(self, continuous: bool = True):
        """Run Phase 2 processing."""
        self.start_time = datetime.now()

        logger.info("=" * 60)
        logger.info("       ARCHIVIST PHASE 2 PROCESSING V2")
        logger.info("=" * 60)

        # Check Ollama
        logger.info("Checking Ollama connection...")
        if not await self.check_ollama():
            logger.error("Ollama with qwen3:8b not available!")
            logger.error("Run: ollama serve && ollama pull qwen3:8b")
            return

        logger.info("Ollama OK!")

        # Get initial stats
        total_pending = self.pending_queue.count()
        already_processed = len(self.decisions._processed_ids)
        logger.info(f"Total pending items: {total_pending}")
        logger.info(f"Already processed: {already_processed}")
        logger.info(f"Remaining: {total_pending - already_processed}")

        if continuous:
            logger.info(f"Continuous mode: polling every {self.poll_interval}s")
            logger.info("-" * 60)

        # Start status tracking
        unprocessed = self.decisions.get_unprocessed(self.pending_queue)
        if unprocessed:
            self.status_manager.start_phase2(total_pending=len(unprocessed))

        while True:
            # Get unprocessed items
            unprocessed = self.decisions.get_unprocessed(self.pending_queue)

            if not unprocessed:
                # Check if Phase 1 is still running
                status = self.status_manager.get_status()
                phase1_status = status.get("phase1", {}).get("status", "idle")

                if phase1_status == "completed" and not continuous:
                    logger.info("Phase 1 completed and no more pending items. Done!")
                    break
                elif phase1_status == "completed":
                    logger.info("Phase 1 completed. Waiting for any final items...")
                    await asyncio.sleep(self.poll_interval)

                    # Check one more time
                    unprocessed = self.decisions.get_unprocessed(self.pending_queue)
                    if not unprocessed:
                        logger.info("No more items. Phase 2 complete!")
                        break
                else:
                    logger.info(f"No pending items. Phase 1 status: {phase1_status}. Waiting...")
                    await asyncio.sleep(self.poll_interval)
                    continue

            # Process batch
            batch = unprocessed[:self.batch_size]
            logger.info(f"Processing batch of {len(batch)} items ({len(unprocessed)} remaining)...")

            processed = await self.process_batch(batch)

            # Update status
            self.status_manager.update_phase2(
                processed=self.processed_count,
                link_existing=self.link_existing_count,
                create_new=self.create_new_count
            )

            logger.info(f"Batch done. Total: {self.processed_count} (LINK: {self.link_existing_count}, NEW: {self.create_new_count})")

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
        logger.info(f"  LINK_EXISTING: {self.link_existing_count}")
        logger.info(f"  CREATE_NEW: {self.create_new_count}")
        logger.info(f"Time elapsed: {elapsed/3600:.2f} hours")
        if elapsed > 0 and self.processed_count > 0:
            logger.info(f"Rate: {self.processed_count/elapsed*3600:.0f} items/hour")


async def main():
    parser = argparse.ArgumentParser(description="Archivist Phase 2 Processing V2")
    parser.add_argument("--poll-interval", type=int, default=30,
                       help="Seconds between polling for new items")
    parser.add_argument("--batch-size", type=int, default=50,
                       help="Number of items to process per batch")
    parser.add_argument("--once", action="store_true",
                       help="Process once and exit (don't poll continuously)")
    args = parser.parse_args()

    processor = Phase2ProcessorV2(
        poll_interval=args.poll_interval,
        batch_size=args.batch_size
    )

    await processor.run(continuous=not args.once)


if __name__ == "__main__":
    asyncio.run(main())
