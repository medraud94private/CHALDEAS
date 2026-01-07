"""
Archivist Phase 2 Parallel: Review PENDING items with LLM
Runs alongside Phase 1, processing PENDING items as they appear.
Uses GPU (Ollama/Qwen) while Phase 1 uses CPU (spaCy).
"""
import asyncio
import json
import sys
import io
import re
import httpx
from pathlib import Path
from datetime import datetime
from typing import Set, Dict, Any

# Fix Windows console encoding
if sys.platform == 'win32':
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True)
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace', line_buffering=True)
    except Exception:
        pass

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import settings
from app.core.extraction.ner_pipeline import test_ollama_connection


class ParallelPhase2:
    """Runs Phase 2 in parallel with Phase 1."""

    CHECKPOINT_FILE = Path(__file__).parent.parent / "data" / "archivist_checkpoint.json"
    RESULTS_DIR = Path(__file__).parent.parent / "data" / "archivist_results"
    PHASE2_OUTPUT = Path(__file__).parent.parent / "data" / "phase2_parallel_results.json"

    def __init__(self, poll_interval: int = 30):
        self.poll_interval = poll_interval  # seconds between checkpoint reads
        self.processed_keys: Set[str] = set()  # track what we've processed
        self.results: Dict[str, Any] = {
            "decisions": [],
            "stats": {
                "total_reviewed": 0,
                "link_existing": 0,
                "create_new": 0,
                "still_pending": 0
            }
        }
        self.start_time = None

    def _make_key(self, item: dict) -> str:
        """Create unique key for pending item."""
        return f"{item.get('text', '')}|{item.get('entity_type', '')}|{item.get('source', '')}"

    async def _call_qwen(self, text: str, entity_type: str, candidates: list) -> dict:
        """Call Qwen for decision."""
        cand_list = [f"ID:{c['id']} \"{c['normalized']}\"" for c in candidates[:5]]

        prompt = f"""Entity: "{text}" ({entity_type})
Candidates: {', '.join(cand_list)}

Same entity? Reply JSON: {{"decision":"LINK_EXISTING","id":N}} or {{"decision":"CREATE_NEW"}}"""

        for attempt in range(3):
            try:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    response = await client.post(
                        f"{settings.ollama_base_url}/api/chat",
                        json={
                            "model": settings.ollama_model,
                            "messages": [{"role": "user", "content": prompt}],
                            "stream": False,
                            "think": False,
                            "options": {"temperature": 0.1, "num_predict": 100}
                        }
                    )

                    if response.status_code == 200:
                        result = response.json()
                        response_text = result.get("message", {}).get("content", "")

                        json_match = re.search(r'\{[^{}]*\}', response_text, re.DOTALL)
                        if json_match:
                            data = json.loads(json_match.group())
                            return {
                                "decision": data.get("decision", "PENDING"),
                                "id": data.get("id"),
                                "confidence": 0.8
                            }

            except Exception as e:
                await asyncio.sleep(2 ** attempt)
                continue

        return {"decision": "PENDING", "confidence": 0.3}

    async def _process_pending_item(self, item: dict) -> dict:
        """Process a single pending item with Qwen."""
        text = item.get("text", "")
        entity_type = item.get("entity_type", "")
        candidates = item.get("candidates", [])

        if not candidates:
            return {"decision": "CREATE_NEW", "confidence": 0.9}

        result = await self._call_qwen(text, entity_type, candidates)
        return result

    def _save_results(self):
        """Save current results to file."""
        self.RESULTS_DIR.mkdir(parents=True, exist_ok=True)

        output = {
            "timestamp": datetime.now().isoformat(),
            "processed_count": len(self.processed_keys),
            "stats": self.results["stats"],
            "decisions": self.results["decisions"][-100:]  # Last 100 for file size
        }

        with open(self.PHASE2_OUTPUT, 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)

    async def run(self):
        """Main loop - poll checkpoint and process PENDING items."""
        print("="*60)
        print("   PHASE 2 PARALLEL - LLM Review (GPU)")
        print("="*60)
        print()

        # Check Ollama
        print("Checking Ollama connection...")
        if not await test_ollama_connection():
            print("ERROR: Ollama not available. Run: ollama serve")
            return
        print("Ollama OK!")
        print()

        print(f"Polling checkpoint every {self.poll_interval} seconds...")
        print("Waiting for Phase 1 to generate PENDING items...")
        print("-"*60)

        self.start_time = datetime.now()
        last_checkpoint_time = None

        while True:
            try:
                # Check if checkpoint exists and has been updated
                if not self.CHECKPOINT_FILE.exists():
                    await asyncio.sleep(self.poll_interval)
                    continue

                checkpoint_mtime = self.CHECKPOINT_FILE.stat().st_mtime

                # Skip if checkpoint hasn't changed
                if last_checkpoint_time and checkpoint_mtime <= last_checkpoint_time:
                    await asyncio.sleep(self.poll_interval)
                    continue

                last_checkpoint_time = checkpoint_mtime

                # Load checkpoint
                with open(self.CHECKPOINT_FILE, 'r', encoding='utf-8') as f:
                    checkpoint = json.load(f)

                pending_items = checkpoint.get("pending_items", [])
                phase1_progress = len(checkpoint.get("processed_files", []))
                total_files = checkpoint.get("total_files", 76090)

                # Find new pending items
                new_items = []
                for item in pending_items:
                    key = self._make_key(item)
                    if key not in self.processed_keys:
                        new_items.append((key, item))

                if new_items:
                    print(f"\n[Phase 1: {phase1_progress}/{total_files}] Found {len(new_items)} new PENDING items")

                    for key, item in new_items:
                        text = item.get("text", "")[:30]
                        entity_type = item.get("entity_type", "")

                        print(f"  Reviewing: {text}... ({entity_type})", end=" ")

                        result = await self._process_pending_item(item)
                        decision = result.get("decision", "PENDING")

                        print(f"-> {decision}")

                        # Record result
                        self.processed_keys.add(key)
                        self.results["stats"]["total_reviewed"] += 1

                        if decision == "LINK_EXISTING":
                            self.results["stats"]["link_existing"] += 1
                        elif decision == "CREATE_NEW":
                            self.results["stats"]["create_new"] += 1
                        else:
                            self.results["stats"]["still_pending"] += 1

                        self.results["decisions"].append({
                            "text": item.get("text", ""),
                            "entity_type": entity_type,
                            "decision": decision,
                            "linked_id": result.get("id")
                        })

                    # Save after processing batch
                    self._save_results()

                    # Print stats
                    stats = self.results["stats"]
                    elapsed = (datetime.now() - self.start_time).total_seconds() / 3600
                    rate = stats["total_reviewed"] / elapsed if elapsed > 0 else 0

                    print(f"\n  [Phase 2 Stats] Reviewed: {stats['total_reviewed']}, "
                          f"Resolved: {stats['link_existing'] + stats['create_new']}, "
                          f"Rate: {rate:.0f}/hour")

                # Check if Phase 1 is done
                if phase1_progress >= total_files:
                    print("\n" + "="*60)
                    print("Phase 1 complete! Processing remaining PENDING items...")
                    # Process any remaining items one more time
                    await asyncio.sleep(5)
                    # Final check already done above
                    break

                await asyncio.sleep(self.poll_interval)

            except json.JSONDecodeError:
                # Checkpoint being written, wait and retry
                await asyncio.sleep(2)
            except Exception as e:
                print(f"Error: {e}")
                await asyncio.sleep(self.poll_interval)

        # Final report
        self._print_final_report()

    def _print_final_report(self):
        """Print final statistics."""
        stats = self.results["stats"]
        elapsed = (datetime.now() - self.start_time).total_seconds() / 3600

        print("\n" + "="*60)
        print("   PHASE 2 PARALLEL COMPLETE")
        print("="*60)
        print(f"\nTotal Reviewed: {stats['total_reviewed']}")
        print(f"  - LINK_EXISTING: {stats['link_existing']}")
        print(f"  - CREATE_NEW: {stats['create_new']}")
        print(f"  - Still PENDING: {stats['still_pending']}")
        print(f"\nTime: {elapsed:.2f} hours")
        print(f"Rate: {stats['total_reviewed']/elapsed:.0f} items/hour" if elapsed > 0 else "")
        print(f"\nResults saved to: {self.PHASE2_OUTPUT}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Phase 2 Parallel Processing")
    parser.add_argument("--poll", type=int, default=30, help="Poll interval in seconds")
    args = parser.parse_args()

    processor = ParallelPhase2(poll_interval=args.poll)
    asyncio.run(processor.run())
