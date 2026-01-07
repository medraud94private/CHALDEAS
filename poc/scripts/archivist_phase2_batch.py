"""
Archivist Phase 2 - OpenAI Batch API
- 50% cost savings
- Processes up to 50,000 requests per batch
- Completes within 24 hours

Usage:
  1. Prepare: python archivist_phase2_batch.py --prepare --limit 10000
  2. Submit:  python archivist_phase2_batch.py --submit
  3. Check:   python archivist_phase2_batch.py --status
  4. Process: python archivist_phase2_batch.py --process-results
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
        logging.FileHandler(LOG_DIR / f"phase2_batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log", encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class BatchProcessor:
    """OpenAI Batch API processor for Phase 2."""

    CHECKPOINT_DIR = Path(__file__).parent.parent / "data"
    BATCH_DIR = Path(__file__).parent.parent / "data" / "batch"
    OPENAI_URL = "https://api.openai.com/v1"

    def __init__(self):
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.openai_model = "gpt-5-nano"

        # Ensure batch directory exists
        self.BATCH_DIR.mkdir(parents=True, exist_ok=True)

        # Checkpoint components
        self.pending_queue = PendingQueue(self.CHECKPOINT_DIR)
        self.decisions = Phase2Decisions(self.CHECKPOINT_DIR)

        # Batch state file
        self.batch_state_file = self.BATCH_DIR / "batch_state.json"

        # Build decided entities registry
        self.decided_entities: Dict[str, dict] = {}

    def load_decided_entities(self):
        """Load already-decided entities."""
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
                            self.decided_entities[entity_key] = {
                                "text": item["text"],
                                "entity_type": item["entity_type"],
                                "mention_count": item.get("mention_count", 1)
                            }

            logger.info(f"Loaded {len(self.decided_entities)} decided entities")

    def find_candidates(self, item: dict) -> List[Dict]:
        """Find candidate entities for comparison."""
        text = item.get("text", "")
        entity_type = item.get("entity_type", "")
        normalized_text = EntityRegistry.normalize(text)

        candidates = []
        for key, entity in self.decided_entities.items():
            if not key.startswith(f"{entity_type}:"):
                continue

            entity_norm = EntityRegistry.normalize(entity["text"])

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
                "similarity": similarity
            })

        candidates.sort(key=lambda x: -x["similarity"])
        return candidates[:5]

    def build_prompt(self, item: dict, candidates: List[Dict]) -> str:
        """Build prompt for LLM."""
        text = item.get("text", "")
        entity_type = item.get("entity_type", "")
        mention_count = item.get("mention_count", 1)

        candidates_text = "\n".join([
            f"  {i+1}. {c.get('text')} (similarity: {c.get('similarity', 0):.2f})"
            for i, c in enumerate(candidates)
        ])

        return f"""Entity: "{text}" (type: {entity_type}, mentioned {mention_count} times)

Similar existing entities:
{candidates_text}

If this entity refers to one of the candidates (same person/place/event), respond: LINK <number>
If it's different from all candidates, respond: CREATE_NEW

Important: "Charles VII" and "Charles VIII" are DIFFERENT people. Numbers matter!

Response (LINK <number> or CREATE_NEW):"""

    async def prepare_batch(self, limit: int = None):
        """Prepare batch requests JSONL file."""
        logger.info("Preparing batch requests...")

        self.load_decided_entities()

        # Get unprocessed items
        items = []
        for item in self.pending_queue.get_all():
            if not self.decisions.is_processed(item["id"]):
                items.append(item)
                if limit and len(items) >= limit:
                    break

        logger.info(f"Found {len(items)} unprocessed items")

        if not items:
            logger.info("No items to process")
            return

        # Build batch requests
        batch_file = self.BATCH_DIR / f"batch_requests_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl"
        item_mapping = {}  # custom_id -> item

        with open(batch_file, 'w', encoding='utf-8') as f:
            for item in items:
                candidates = self.find_candidates(item)

                # Skip if no candidates (auto CREATE_NEW)
                if not candidates:
                    # Auto-decide without LLM
                    self.decisions.append(
                        pending_id=item["id"],
                        decision="CREATE_NEW",
                        confidence=0.9
                    )
                    entity_key = item.get("entity_key", f"{item['entity_type']}:{item['text'].lower()}")
                    self.decided_entities[entity_key] = {
                        "text": item["text"],
                        "entity_type": item["entity_type"],
                        "mention_count": item.get("mention_count", 1)
                    }
                    continue

                # Skip if exact match (auto LINK)
                if candidates[0].get("similarity", 0) >= 1.0:
                    self.decisions.append(
                        pending_id=item["id"],
                        decision="LINK_EXISTING",
                        linked_entity_key=candidates[0].get("key"),
                        confidence=1.0
                    )
                    continue

                # Build request for LLM
                prompt = self.build_prompt(item, candidates)
                custom_id = f"item_{item['id']}"

                request = {
                    "custom_id": custom_id,
                    "method": "POST",
                    "url": "/v1/chat/completions",
                    "body": {
                        "model": self.openai_model,
                        "messages": [{"role": "user", "content": prompt}],
                        "max_completion_tokens": 50
                    }
                }

                f.write(json.dumps(request, ensure_ascii=False) + "\n")
                item_mapping[custom_id] = {
                    "item": item,
                    "candidates": candidates
                }

        # Save item mapping for later processing
        mapping_file = self.BATCH_DIR / "item_mapping.json"
        with open(mapping_file, 'w', encoding='utf-8') as f:
            json.dump(item_mapping, f, ensure_ascii=False, indent=2)

        logger.info(f"Batch file: {batch_file}")
        logger.info(f"Total requests: {len(item_mapping)}")
        logger.info(f"Auto-decided (no candidates/exact match): {len(items) - len(item_mapping)}")

        # Save batch state
        self._save_batch_state({
            "batch_file": str(batch_file),
            "mapping_file": str(mapping_file),
            "request_count": len(item_mapping),
            "prepared_at": datetime.now().isoformat()
        })

    async def submit_batch(self):
        """Submit batch to OpenAI."""
        state = self._load_batch_state()
        if not state or "batch_file" not in state:
            logger.error("No batch prepared. Run --prepare first.")
            return

        batch_file = Path(state["batch_file"])
        if not batch_file.exists():
            logger.error(f"Batch file not found: {batch_file}")
            return

        logger.info(f"Uploading batch file: {batch_file}")

        async with httpx.AsyncClient(timeout=120.0) as client:
            # Upload file
            with open(batch_file, 'rb') as f:
                response = await client.post(
                    f"{self.OPENAI_URL}/files",
                    headers={"Authorization": f"Bearer {self.openai_api_key}"},
                    files={"file": (batch_file.name, f, "application/jsonl")},
                    data={"purpose": "batch"}
                )

            if response.status_code != 200:
                logger.error(f"Upload failed: {response.text}")
                return

            file_id = response.json()["id"]
            logger.info(f"File uploaded: {file_id}")

            # Create batch
            response = await client.post(
                f"{self.OPENAI_URL}/batches",
                headers={
                    "Authorization": f"Bearer {self.openai_api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "input_file_id": file_id,
                    "endpoint": "/v1/chat/completions",
                    "completion_window": "24h"
                }
            )

            if response.status_code != 200:
                logger.error(f"Batch creation failed: {response.text}")
                return

            batch_info = response.json()
            batch_id = batch_info["id"]

            logger.info(f"Batch created: {batch_id}")
            logger.info(f"Status: {batch_info['status']}")

            # Update state
            state["batch_id"] = batch_id
            state["file_id"] = file_id
            state["submitted_at"] = datetime.now().isoformat()
            self._save_batch_state(state)

    async def check_status(self):
        """Check batch status."""
        state = self._load_batch_state()
        if not state or "batch_id" not in state:
            logger.error("No batch submitted. Run --submit first.")
            return

        batch_id = state["batch_id"]

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self.OPENAI_URL}/batches/{batch_id}",
                headers={"Authorization": f"Bearer {self.openai_api_key}"}
            )

            if response.status_code != 200:
                logger.error(f"Status check failed: {response.text}")
                return

            batch_info = response.json()

            logger.info(f"Batch ID: {batch_id}")
            logger.info(f"Status: {batch_info['status']}")
            logger.info(f"Request counts: {batch_info.get('request_counts', {})}")

            if batch_info['status'] == 'completed':
                output_file_id = batch_info.get('output_file_id')
                if output_file_id:
                    state["output_file_id"] = output_file_id
                    self._save_batch_state(state)
                    logger.info(f"Output file: {output_file_id}")
                    logger.info("Run --process-results to download and process")

    async def process_results(self):
        """Download and process batch results."""
        state = self._load_batch_state()
        if not state or "output_file_id" not in state:
            logger.error("No completed batch. Run --status first.")
            return

        output_file_id = state["output_file_id"]
        mapping_file = Path(state["mapping_file"])

        if not mapping_file.exists():
            logger.error(f"Mapping file not found: {mapping_file}")
            return

        with open(mapping_file, 'r', encoding='utf-8') as f:
            item_mapping = json.load(f)

        logger.info(f"Downloading results: {output_file_id}")

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.get(
                f"{self.OPENAI_URL}/files/{output_file_id}/content",
                headers={"Authorization": f"Bearer {self.openai_api_key}"}
            )

            if response.status_code != 200:
                logger.error(f"Download failed: {response.text}")
                return

            results_file = self.BATCH_DIR / f"batch_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl"
            with open(results_file, 'wb') as f:
                f.write(response.content)

            logger.info(f"Results saved: {results_file}")

        # Process results
        processed = 0
        link_count = 0
        create_count = 0

        with open(results_file, 'r', encoding='utf-8') as f:
            for line in f:
                if not line.strip():
                    continue

                result = json.loads(line)
                custom_id = result.get("custom_id")

                if custom_id not in item_mapping:
                    continue

                mapping = item_mapping[custom_id]
                item = mapping["item"]
                candidates = mapping["candidates"]

                # Parse response
                response_body = result.get("response", {}).get("body", {})
                content = ""
                if "choices" in response_body:
                    content = response_body["choices"][0]["message"]["content"].strip()

                decision = self._parse_response(content, candidates)

                # Save decision
                self.decisions.append(
                    pending_id=item["id"],
                    decision=decision["decision"],
                    linked_entity_key=decision.get("linked_entity_key"),
                    confidence=decision.get("confidence", 0.7)
                )

                processed += 1
                if decision["decision"] == "LINK_EXISTING":
                    link_count += 1
                else:
                    create_count += 1

        logger.info(f"Processed: {processed}")
        logger.info(f"  LINK_EXISTING: {link_count}")
        logger.info(f"  CREATE_NEW: {create_count}")

        # Clear batch state
        self._save_batch_state({})

    def _parse_response(self, content: str, candidates: List[Dict]) -> dict:
        """Parse LLM response."""
        if "<think>" in content:
            content = content.split("</think>")[-1].strip()

        content_upper = content.upper()

        if "LINK" in content_upper:
            import re
            match = re.search(r'LINK\s*(\d+)', content_upper)
            if match:
                idx = int(match.group(1)) - 1
                if 0 <= idx < len(candidates):
                    return {
                        "decision": "LINK_EXISTING",
                        "linked_entity_key": candidates[idx].get("key"),
                        "confidence": 0.8
                    }

        return {
            "decision": "CREATE_NEW",
            "linked_entity_key": None,
            "confidence": 0.7
        }

    def _load_batch_state(self) -> dict:
        """Load batch state."""
        if self.batch_state_file.exists():
            with open(self.batch_state_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    def _save_batch_state(self, state: dict):
        """Save batch state."""
        with open(self.batch_state_file, 'w', encoding='utf-8') as f:
            json.dump(state, f, ensure_ascii=False, indent=2)


async def main():
    parser = argparse.ArgumentParser(description="Phase 2: OpenAI Batch API")
    parser.add_argument("--prepare", action="store_true", help="Prepare batch JSONL file")
    parser.add_argument("--submit", action="store_true", help="Submit batch to OpenAI")
    parser.add_argument("--status", action="store_true", help="Check batch status")
    parser.add_argument("--process-results", action="store_true", help="Download and process results")
    parser.add_argument("--limit", type=int, default=None, help="Limit items for --prepare")
    args = parser.parse_args()

    processor = BatchProcessor()

    if args.prepare:
        await processor.prepare_batch(limit=args.limit)
    elif args.submit:
        await processor.submit_batch()
    elif args.status:
        await processor.check_status()
    elif args.process_results:
        await processor.process_results()
    else:
        parser.print_help()


if __name__ == "__main__":
    asyncio.run(main())
