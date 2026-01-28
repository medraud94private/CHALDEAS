"""
Wikidata matching with split checkpoint support.

Usage:
    python poc/scripts/wikidata_resume.py --workers 4 --limit 10000
    python poc/scripts/wikidata_resume.py --workers 8 --skip-llm

Features:
- Uses split checkpoint format (fast loading)
- Auto-resumes from last offset
- Merges new results with existing chunks
"""

import sys
import json
import argparse
from pathlib import Path

# Import and patch the original module
sys.path.insert(0, str(Path(__file__).parent))
import wikidata_match_parallel as wm

DATA_DIR = Path(__file__).parent.parent / "data"
STATE_FILE = DATA_DIR / "wikidata_state.json"
CHUNK_SIZE = 50000


def load_checkpoint_split():
    """Load checkpoint from split files (state + result chunks)"""
    if not STATE_FILE.exists():
        # Try old format
        old_path = DATA_DIR / "wikidata_checkpoint.json"
        if old_path.exists():
            wm.safe_print("Found old checkpoint format, converting...")
            with open(old_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            # Convert and save split format
            save_checkpoint_split(
                [wm.MatchResult(**r) for r in data.get("results", [])],
                data.get("stats", {}),
                data.get("last_offset", 0),
                data.get("llm_pending", [])
            )
            return load_checkpoint_split()
        return None

    with open(STATE_FILE, "r", encoding="utf-8") as f:
        state = json.load(f)

    # Load existing results from chunks
    results = []
    num_chunks = state.get("result_chunks", 0)
    wm.safe_print(f"Loading {num_chunks} result chunks...")
    for i in range(num_chunks):
        chunk_path = DATA_DIR / f"wikidata_results_chunk_{i}.json"
        if chunk_path.exists():
            with open(chunk_path, "r", encoding="utf-8") as f:
                results.extend(json.load(f))

    state["results"] = results
    wm.safe_print(f"  Loaded {len(results):,} existing results")
    return state


def save_checkpoint_split(results, stats, offset, llm_pending=None):
    """Save checkpoint in split format"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Convert MatchResult objects to dicts if needed
    result_dicts = []
    for r in results:
        if isinstance(r, dict):
            result_dicts.append(r)
        else:
            result_dicts.append({
                "person_id": r.person_id,
                "person_name": r.person_name,
                "wikidata_qid": r.wikidata_qid,
                "match_type": r.match_type,
                "confidence": r.confidence,
                "aliases": r.aliases
            })

    # Save results in chunks
    num_chunks = 0
    for i in range(0, len(result_dicts), CHUNK_SIZE):
        chunk = result_dicts[i:i+CHUNK_SIZE]
        chunk_path = DATA_DIR / f"wikidata_results_chunk_{num_chunks}.json"
        with open(chunk_path, "w", encoding="utf-8") as f:
            json.dump(chunk, f, ensure_ascii=False)
        num_chunks += 1

    # Save lightweight state
    state = {
        "last_offset": offset,
        "stats": stats,
        "llm_pending": llm_pending or [],
        "result_chunks": num_chunks,
        "total_results": len(result_dicts)
    }

    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

    wm.safe_print(f"  [Checkpoint saved: {len(results):,} results in {num_chunks} chunks, offset {offset}]")


# Monkey-patch the original module
wm.load_checkpoint = load_checkpoint_split
wm.save_checkpoint = save_checkpoint_split


def main():
    parser = argparse.ArgumentParser(description="Wikidata matching with split checkpoint")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--limit", type=int, default=10000, help="Persons to process in this run")
    parser.add_argument("--llm-batch", type=int, default=10)
    parser.add_argument("--delay", type=float, default=0.2)
    parser.add_argument("--skip-llm", action="store_true")
    parser.add_argument("--checkpoint-interval", type=int, default=500)
    parser.add_argument("--fresh", action="store_true", help="Start fresh (ignore checkpoint)")
    args = parser.parse_args()

    # Build args for original main
    sys.argv = ["wikidata_match_parallel.py"]
    sys.argv.extend(["--workers", str(args.workers)])
    sys.argv.extend(["--limit", str(args.limit)])
    sys.argv.extend(["--llm-batch", str(args.llm_batch)])
    sys.argv.extend(["--delay", str(args.delay)])
    sys.argv.extend(["--checkpoint-interval", str(args.checkpoint_interval)])

    if args.skip_llm:
        sys.argv.append("--skip-llm")

    if not args.fresh:
        sys.argv.append("--resume")

    # Show status
    state = load_checkpoint_split()
    if state:
        total = state['stats']['total']
        offset = state['last_offset']
        remaining = total - offset
        print(f"\n=== Current Status ===")
        print(f"Progress: {offset:,} / {total:,} ({100*offset/total:.1f}%)")
        print(f"Remaining: {remaining:,}")
        print(f"This run will process: {min(args.limit, remaining):,}")
        print()

    # Run original main
    wm.main()


if __name__ == "__main__":
    main()
