"""
Wikidata matching - Continue from checkpoint (SAFE version)

Saves new results to separate file, then merges at the end.
This prevents overwriting existing results.

Usage:
    python poc/scripts/wikidata_continue.py --workers 8 --limit 10000 --skip-llm
"""

import sys
import io
import json
import time
import argparse
import threading
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add paths
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))

from wikidata_match_parallel import (
    WikidataFetcher, MatchingWorker, MatchResult,
    load_persons, safe_print, GlobalRateLimiter
)

DATA_DIR = Path(__file__).parent.parent / "data"
STATE_FILE = DATA_DIR / "wikidata_state.json"
NEW_RESULTS_FILE = DATA_DIR / "wikidata_results_new.json"
CHUNK_SIZE = 50000


def load_state():
    """Load just state (fast)"""
    if STATE_FILE.exists():
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def save_new_results(results, stats, offset):
    """Save NEW results only to separate file"""
    result_dicts = [
        {
            "person_id": r.person_id,
            "person_name": r.person_name,
            "wikidata_qid": r.wikidata_qid,
            "match_type": r.match_type,
            "confidence": r.confidence,
            "aliases": r.aliases
        }
        for r in results
    ]

    data = {
        "last_offset": offset,
        "stats": stats,
        "count": len(result_dicts),
        "results": result_dicts
    }

    with open(NEW_RESULTS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)

    safe_print(f"  [New results saved: {len(results):,} to {NEW_RESULTS_FILE.name}]")


def merge_results():
    """Merge new results with existing chunks"""
    state = load_state()
    if not state:
        print("No state file found")
        return

    # Load existing results
    existing = []
    for i in range(state.get("result_chunks", 0)):
        chunk_path = DATA_DIR / f"wikidata_results_chunk_{i}.json"
        if chunk_path.exists():
            with open(chunk_path, "r", encoding="utf-8") as f:
                existing.extend(json.load(f))

    print(f"Existing results: {len(existing):,}")

    # Load new results
    if not NEW_RESULTS_FILE.exists():
        print("No new results file found")
        return

    with open(NEW_RESULTS_FILE, "r", encoding="utf-8") as f:
        new_data = json.load(f)

    new_results = new_data.get("results", [])
    new_offset = new_data.get("last_offset", state["last_offset"])
    new_stats = new_data.get("stats", {})

    print(f"New results: {len(new_results):,}")

    # Merge
    all_results = existing + new_results
    print(f"Total after merge: {len(all_results):,}")

    # Merge stats
    merged_stats = state["stats"].copy()
    for k, v in new_stats.items():
        if k in merged_stats and k != "total":
            merged_stats[k] += v

    # Save merged chunks
    num_chunks = 0
    for i in range(0, len(all_results), CHUNK_SIZE):
        chunk = all_results[i:i+CHUNK_SIZE]
        chunk_path = DATA_DIR / f"wikidata_results_chunk_{num_chunks}.json"
        with open(chunk_path, "w", encoding="utf-8") as f:
            json.dump(chunk, f, ensure_ascii=False)
        print(f"  Saved chunk {num_chunks}: {len(chunk):,}")
        num_chunks += 1

    # Update state
    state["last_offset"] = new_offset
    state["stats"] = merged_stats
    state["result_chunks"] = num_chunks
    state["total_results"] = len(all_results)

    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

    print(f"\nMerge complete!")
    print(f"  Offset: {new_offset:,}")
    print(f"  Total results: {len(all_results):,}")

    # Backup new results file
    backup = DATA_DIR / f"wikidata_results_new_{int(time.time())}.json.bak"
    NEW_RESULTS_FILE.rename(backup)
    print(f"  New results backed up to: {backup.name}")


def categorize_match_type(match_type: str) -> str:
    """Categorize detailed match type into stats bucket"""
    if match_type == "none" or not match_type:
        return "no_match"
    if "lifespan_mismatch" in match_type:
        return "lifespan_rejected"
    if match_type.startswith("low_confidence"):
        return "low_confidence"
    if "exact_lifespan_confirmed" in match_type:
        return "exact_lifespan_confirmed"
    if "alias_lifespan_confirmed" in match_type:
        return "alias_lifespan_confirmed"
    if "fuzzy_lifespan_boosted" in match_type:
        return "fuzzy_lifespan_boosted"
    if match_type.startswith("exact") or "exact" in match_type:
        return "exact"
    if match_type.startswith("alias") or "alias" in match_type:
        return "alias"
    if match_type.startswith("fuzzy") or "fuzzy" in match_type:
        return "fuzzy"
    return "no_match"


def main():
    parser = argparse.ArgumentParser(description="Continue Wikidata matching (safe)")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--limit", type=int, default=10000)
    parser.add_argument("--delay", type=float, default=0.2)
    parser.add_argument("--skip-llm", action="store_true", default=True)
    parser.add_argument("--checkpoint-interval", type=int, default=1000)
    parser.add_argument("--merge", action="store_true", help="Merge new results with existing")
    args = parser.parse_args()

    # Merge mode
    if args.merge:
        merge_results()
        return

    # Load state
    state = load_state()
    if not state:
        print("No checkpoint found. Run wikidata_match_parallel.py first.")
        return

    offset = state["last_offset"]
    total = state["stats"]["total"]
    remaining = total - offset

    print(f"=== Continue Wikidata Matching (Safe Mode) ===")
    print(f"Progress: {offset:,} / {total:,} ({100*offset/total:.1f}%)")
    print(f"Remaining: {remaining:,}")
    print(f"This run: {min(args.limit, remaining):,}")
    print(f"Workers: {args.workers}, Delay: {args.delay}s")
    print()

    if remaining <= 0:
        print("All done!")
        return

    # Load persons
    print("Loading persons...")
    tasks = load_persons(args.limit, offset)
    print(f"Loaded {len(tasks)} persons")

    if not tasks:
        print("No persons to process")
        return

    # Initialize
    fetcher = WikidataFetcher(delay=args.delay)
    worker = MatchingWorker(fetcher)

    # Results (NEW only)
    results = []
    stats = {
        "exact": 0,
        "exact_lifespan_confirmed": 0,
        "alias": 0,
        "alias_lifespan_confirmed": 0,
        "fuzzy": 0,
        "fuzzy_lifespan_boosted": 0,
        "lifespan_rejected": 0,
        "low_confidence": 0,
        "llm_skipped": 0,
        "no_match": 0,
        "errors": 0
    }

    start_time = time.time()

    # Process
    print(f"\nProcessing with {args.workers} workers...")

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(worker.process, task): task for task in tasks}

        completed = 0
        for future in as_completed(futures):
            completed += 1
            task = futures[future]

            try:
                result, llm_task = future.result()

                if llm_task:
                    # Skip LLM
                    result.match_type = "llm_skipped"
                    stats["llm_skipped"] += 1
                else:
                    stat_key = categorize_match_type(result.match_type)
                    if stat_key in stats:
                        stats[stat_key] += 1

                results.append(result)

                # Log
                if result.wikidata_qid:
                    status = f"{result.match_type} ({result.confidence:.2f})"
                else:
                    status = "no match"

                lifespan = f" [{task.lifespan}]" if task.lifespan else ""
                safe_print(f"[{completed}/{len(tasks)}] {task.person_name}{lifespan} -> {status}")

            except Exception as e:
                safe_print(f"[{completed}/{len(tasks)}] {task.person_name} -> ERROR: {e}")
                stats["errors"] += 1
                results.append(MatchResult(
                    person_id=task.person_id,
                    person_name=task.person_name,
                    match_type="error"
                ))

            # Periodic save
            if completed % args.checkpoint_interval == 0:
                save_new_results(results, stats, offset + completed)

    elapsed = time.time() - start_time

    # Final save
    final_offset = offset + len(tasks)
    save_new_results(results, stats, final_offset)

    # Summary
    print(f"\n=== Results ===")
    print(f"Time: {elapsed:.1f}s ({elapsed/len(tasks):.2f}s per person)")
    print(f"Processed: {len(tasks):,}")

    matched = sum(stats[k] for k in ['exact', 'exact_lifespan_confirmed', 'alias',
                                      'alias_lifespan_confirmed', 'fuzzy', 'fuzzy_lifespan_boosted'])
    print(f"Matched: {matched:,}")
    print(f"No match: {stats['no_match']:,}")

    print(f"\nNew results saved to: {NEW_RESULTS_FILE}")
    print(f"\nTo merge with existing results, run:")
    print(f"  python poc/scripts/wikidata_continue.py --merge")


if __name__ == "__main__":
    main()
