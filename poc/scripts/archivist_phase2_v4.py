"""
Archivist Phase 2 Processing Script V4
- Supports both Ollama (local) and OpenAI (gpt-5-nano)
- Batch API support for OpenAI
- Uses EntityRegistry from Phase 1 to find candidates
"""
import asyncio
import json
import sys
import io
import os
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
        logging.FileHandler(LOG_DIR / f"phase2_v4_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log", encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class Phase2ProcessorV4:
    """Phase 2 processor with multi-provider LLM support."""

    CHECKPOINT_DIR = Path(__file__).parent.parent / "data"
    OLLAMA_URL = "http://localhost:11434"
    OPENAI_URL = "https://api.openai.com/v1"

    def __init__(self, provider: str = "openai", batch_size: int = 50, poll_interval: int = 30, parallel: int = 30):
        self.provider = provider  # "ollama" or "openai"
        self.batch_size = batch_size
        self.poll_interval = poll_interval
        self.parallel = parallel  # Number of parallel LLM calls (OpenAI only)

        # OpenAI settings
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.openai_model = "gpt-5-nano"

        # Checkpoint components
        self.status_manager = StatusManager(self.CHECKPOINT_DIR)
        self.pending_queue = PendingQueue(self.CHECKPOINT_DIR)
        self.decisions = Phase2Decisions(self.CHECKPOINT_DIR)

        # Build registry of decided entities (from previous Phase 2 runs)
        self.decided_entities: Dict[str, dict] = {}

        # Statistics
        self.processed_count = 0
        self.link_existing_count = 0
        self.create_new_count = 0
        self.start_time = None

    def load_decided_entities(self):
        """Load already-decided entities from previous Phase 2 decisions."""
        if self.decisions.decisions_file.exists():
            pending_items = {}
            for item in self.pending_queue.get_all():
                pending_items[item["id"]] = item

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

    async def check_provider(self) -> bool:
        """Check if LLM provider is available."""
        if self.provider == "ollama":
            return await self._check_ollama()
        else:
            return await self._check_openai()

    async def _check_ollama(self) -> bool:
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

    async def _check_openai(self) -> bool:
        """Check if OpenAI API key is available."""
        if not self.openai_api_key:
            logger.error("OPENAI_API_KEY not set in environment")
            return False

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.OPENAI_URL}/models",
                    headers={"Authorization": f"Bearer {self.openai_api_key}"}
                )
                if response.status_code == 200:
                    logger.info(f"OpenAI API OK! Using model: {self.openai_model}")
                    return True
                else:
                    logger.error(f"OpenAI API error: {response.status_code}")
                    return False
        except Exception as e:
            logger.error(f"OpenAI connection failed: {e}")
            return False

    async def decide_with_llm(self, item: dict, candidates: List[Dict]) -> dict:
        """Use LLM to decide on a pending item."""
        text = item.get("text", "")
        entity_type = item.get("entity_type", "")
        entity_key = item.get("entity_key", "")
        mentions = item.get("mentions", [])
        mention_count = item.get("mention_count", len(mentions))

        # If no candidates, create new (no LLM needed)
        if not candidates:
            return {
                "decision": "CREATE_NEW",
                "linked_entity_key": None,
                "confidence": 0.9,
                "reason": "No similar entities found"
            }

        # If exact match exists, link directly (no LLM needed)
        for c in candidates:
            if c.get("similarity", 0) >= 1.0:
                return {
                    "decision": "LINK_EXISTING",
                    "linked_entity_key": c.get("key"),
                    "confidence": 1.0,
                    "reason": f"Exact match: {c.get('text')}"
                }

        # Build prompt
        candidates_text = "\n".join([
            f"  {i+1}. {c.get('text')} (similarity: {c.get('similarity', 0):.2f})"
            for i, c in enumerate(candidates[:5])
        ])

        prompt = f"""Entity: "{text}" (type: {entity_type}, mentioned {mention_count} times)

Similar existing entities:
{candidates_text}

If this entity refers to one of the candidates (same person/place/event), respond: LINK <number>
If it's different from all candidates, respond: CREATE_NEW

Important: "Charles VII" and "Charles VIII" are DIFFERENT people. Numbers matter!

Response (LINK <number> or CREATE_NEW):"""

        if self.provider == "ollama":
            return await self._call_ollama(prompt, candidates)
        else:
            return await self._call_openai(prompt, candidates)

    async def _call_ollama(self, prompt: str, candidates: List[Dict]) -> dict:
        """Call Ollama LLM."""
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    f"{self.OLLAMA_URL}/api/chat",
                    json={
                        "model": "qwen3:8b",
                        "messages": [{"role": "user", "content": prompt}],
                        "stream": False,
                        "options": {"temperature": 0.1}
                    }
                )

                if response.status_code == 200:
                    content = response.json().get("message", {}).get("content", "").strip()
                    return self._parse_response(content, candidates)

        except Exception as e:
            logger.error(f"Ollama error: {e}")

        return {"decision": "CREATE_NEW", "linked_entity_key": None, "confidence": 0.5, "reason": "LLM error"}

    async def _call_openai(self, prompt: str, candidates: List[Dict]) -> dict:
        """Call OpenAI API."""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.OPENAI_URL}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.openai_api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": self.openai_model,
                        "messages": [{"role": "user", "content": prompt}],
                        "max_completion_tokens": 50
                    }
                )

                if response.status_code == 200:
                    content = response.json()["choices"][0]["message"]["content"].strip()
                    return self._parse_response(content, candidates)
                else:
                    logger.error(f"OpenAI error: {response.status_code} - {response.text[:200]}")

        except Exception as e:
            logger.error(f"OpenAI error: {e}")

        return {"decision": "CREATE_NEW", "linked_entity_key": None, "confidence": 0.5, "reason": "LLM error"}

    def _parse_response(self, content: str, candidates: List[Dict]) -> dict:
        """Parse LLM response."""
        # Remove thinking tags if present
        if "<think>" in content:
            content = content.split("</think>")[-1].strip()

        content_upper = content.upper()

        if "LINK" in content_upper:
            # Extract number
            import re
            match = re.search(r'LINK\s*(\d+)', content_upper)
            if match:
                idx = int(match.group(1)) - 1
                if 0 <= idx < len(candidates):
                    return {
                        "decision": "LINK_EXISTING",
                        "linked_entity_key": candidates[idx].get("key"),
                        "confidence": 0.8,
                        "reason": f"LLM linked to: {candidates[idx].get('text')}"
                    }

        # Default to CREATE_NEW
        return {
            "decision": "CREATE_NEW",
            "linked_entity_key": None,
            "confidence": 0.7,
            "reason": "LLM decided to create new entity"
        }

    async def process_item(self, item: dict) -> bool:
        """Process a single pending item."""
        text = item.get("text", "")
        entity_type = item.get("entity_type", "")
        entity_key = item.get("entity_key", "")
        mentions = item.get("mentions", [])
        mention_count = item.get("mention_count", len(mentions))

        # Skip if already processed
        if self.decisions.is_processed(item["id"]):
            return False

        # Find candidates from decided entities
        candidates = []
        normalized_text = EntityRegistry.normalize(text)

        for key, entity in self.decided_entities.items():
            if not key.startswith(f"{entity_type}:"):
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

        candidates.sort(key=lambda x: (-x["similarity"], -x["mention_count"]))

        # Get LLM decision
        result = await self.decide_with_llm(item, candidates)

        # Save decision
        self.decisions.append(
            pending_id=item["id"],
            decision=result["decision"],
            linked_entity_key=result.get("linked_entity_key"),
            confidence=result.get("confidence", 0.5)
        )

        # Update statistics
        self.processed_count += 1
        if result["decision"] == "LINK_EXISTING":
            self.link_existing_count += 1
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

    async def process_batch(self, items: List[dict]) -> int:
        """Process a batch of items with parallel execution for OpenAI."""
        if self.provider == "openai" and self.parallel > 1:
            return await self._process_batch_parallel(items)
        else:
            return await self._process_batch_sequential(items)

    async def _process_batch_sequential(self, items: List[dict]) -> int:
        """Process items sequentially (for Ollama)."""
        processed = 0
        for i, item in enumerate(items):
            try:
                if await self.process_item(item):
                    processed += 1
                if (i + 1) % 10 == 0:
                    logger.info(f"  Batch progress: {i+1}/{len(items)}")
            except Exception as e:
                logger.error(f"Error processing item {item.get('id')}: {e}")
        return processed

    async def _process_batch_parallel(self, items: List[dict]) -> int:
        """Process items in parallel chunks (for OpenAI)."""
        processed = 0
        total = len(items)

        # Process in parallel chunks
        for chunk_start in range(0, total, self.parallel):
            chunk_end = min(chunk_start + self.parallel, total)
            chunk = items[chunk_start:chunk_end]

            # Process chunk in parallel
            tasks = [self.process_item(item) for item in chunk]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Count successes
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(f"Error: {result}")
                elif result:
                    processed += 1

            logger.info(f"  Progress: {chunk_end}/{total} ({processed} processed)")

        return processed

    async def run(self, continuous: bool = True, limit: int = None):
        """Run Phase 2 processing."""
        self.start_time = datetime.now()

        logger.info("=" * 60)
        logger.info("       ARCHIVIST PHASE 2 PROCESSING V4")
        logger.info(f"       Provider: {self.provider.upper()}")
        if self.provider == "openai":
            logger.info(f"       Parallel: {self.parallel} concurrent calls")
        logger.info("=" * 60)

        # Check provider
        logger.info(f"Checking {self.provider} connection...")
        if not await self.check_provider():
            logger.error(f"{self.provider} not available. Exiting.")
            return

        logger.info(f"{self.provider.upper()} OK!")

        # Load existing decisions
        self.load_decided_entities()

        # Get pending count
        total_pending = self.pending_queue.count()
        processed_count = self.decisions.get_processed_count()
        remaining = total_pending - processed_count

        logger.info(f"Total pending items: {total_pending}")
        logger.info(f"Already processed: {processed_count}")
        logger.info(f"Remaining: {remaining}")

        if continuous:
            logger.info(f"Continuous mode: polling every {self.poll_interval}s")

        # Start status tracking
        self.status_manager.start_phase2(total_pending=remaining)

        logger.info("-" * 60)

        while True:
            # Get batch of unprocessed items
            batch = []

            for item in self.pending_queue.get_all():
                if not self.decisions.is_processed(item["id"]):
                    batch.append(item)
                    if len(batch) >= self.batch_size:
                        break

            if not batch:
                if continuous:
                    logger.info(f"No items to process. Waiting {self.poll_interval}s...")
                    await asyncio.sleep(self.poll_interval)
                    continue
                else:
                    break

            logger.info(f"Processing batch of {len(batch)} items...")
            processed = await self.process_batch(batch)

            logger.info(f"Batch done. Total: {self.processed_count} (LINK: {self.link_existing_count}, NEW: {self.create_new_count})")

            # Update status
            self.status_manager.update_phase2(
                processed=self.processed_count,
                link_existing=self.link_existing_count,
                create_new=self.create_new_count
            )

            # Limit check
            if limit and self.processed_count >= limit:
                logger.info(f"Limit reached: {limit}")
                break

        # Final report
        self._print_final_report()

    def _print_final_report(self):
        """Print final processing report."""
        elapsed = (datetime.now() - self.start_time).total_seconds()

        logger.info("=" * 60)
        logger.info("       PHASE 2 COMPLETE")
        logger.info("=" * 60)
        logger.info(f"Provider: {self.provider}")
        logger.info(f"Total processed: {self.processed_count}")
        logger.info(f"  LINK_EXISTING: {self.link_existing_count}")
        logger.info(f"  CREATE_NEW: {self.create_new_count}")
        logger.info(f"Time elapsed: {elapsed/3600:.2f} hours")
        if elapsed > 0 and self.processed_count > 0:
            rate = self.processed_count / elapsed * 3600
            logger.info(f"Rate: {rate:.0f} items/hour")


async def main():
    parser = argparse.ArgumentParser(description="Phase 2: LLM Entity Disambiguation V4")
    parser.add_argument("--provider", type=str, default="openai", choices=["ollama", "openai"],
                        help="LLM provider (ollama or openai)")
    parser.add_argument("--batch-size", type=int, default=50,
                        help="Batch size for processing")
    parser.add_argument("--poll-interval", type=int, default=30,
                        help="Seconds between polls in continuous mode")
    parser.add_argument("--limit", type=int, default=None,
                        help="Limit number of items to process")
    parser.add_argument("--no-continuous", action="store_true",
                        help="Don't run in continuous mode")
    parser.add_argument("--parallel", type=int, default=30,
                        help="Number of parallel LLM calls (OpenAI only, default: 30)")
    args = parser.parse_args()

    processor = Phase2ProcessorV4(
        provider=args.provider,
        batch_size=args.batch_size,
        poll_interval=args.poll_interval,
        parallel=args.parallel
    )

    await processor.run(
        continuous=not args.no_continuous,
        limit=args.limit
    )


if __name__ == "__main__":
    asyncio.run(main())
