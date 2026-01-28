"""
Checkpoint utilities for split checkpoint format.

Usage:
    # View checkpoint status
    python poc/scripts/checkpoint_utils.py status

    # Merge results back to single file (if needed)
    python poc/scripts/checkpoint_utils.py merge

    # Split large checkpoint into chunks
    python poc/scripts/checkpoint_utils.py split
"""

import json
import sys
from pathlib import Path


DATA_DIR = Path(__file__).parent.parent / "data"
STATE_FILE = DATA_DIR / "wikidata_state.json"
OLD_CHECKPOINT = DATA_DIR / "wikidata_checkpoint.json"
CHUNK_SIZE = 50000


def load_state():
    """Load just the state (fast, small file)"""
    if STATE_FILE.exists():
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def load_all_results():
    """Load all results from chunks"""
    state = load_state()
    if not state:
        return []

    results = []
    num_chunks = state.get("result_chunks", 0)
    for i in range(num_chunks):
        chunk_path = DATA_DIR / f"wikidata_results_chunk_{i}.json"
        if chunk_path.exists():
            with open(chunk_path, "r", encoding="utf-8") as f:
                results.extend(json.load(f))
    return results


def status():
    """Show checkpoint status"""
    state = load_state()

    if not state:
        print("No checkpoint found")
        if OLD_CHECKPOINT.exists():
            size_mb = OLD_CHECKPOINT.stat().st_size / (1024 * 1024)
            print(f"  Old format exists: {size_mb:.1f} MB")
            print("  Run 'split' to convert to new format")
        return

    total = state['stats']['total']
    offset = state['last_offset']
    remaining = total - offset

    print("=== Wikidata Checkpoint Status ===")
    print(f"Progress: {offset:,} / {total:,} ({100*offset/total:.1f}%)")
    print(f"Remaining: {remaining:,}")
    print()
    print("Stats:")
    for k, v in state['stats'].items():
        if v > 0 and k != 'total':
            print(f"  {k}: {v:,}")
    print()
    print(f"Result chunks: {state.get('result_chunks', 0)}")
    print(f"Total results: {state.get('total_results', 0):,}")

    # File sizes
    print()
    print("File sizes:")
    print(f"  State file: {STATE_FILE.stat().st_size / 1024:.1f} KB")
    for i in range(state.get('result_chunks', 0)):
        chunk_path = DATA_DIR / f"wikidata_results_chunk_{i}.json"
        if chunk_path.exists():
            size_mb = chunk_path.stat().st_size / (1024 * 1024)
            print(f"  Chunk {i}: {size_mb:.1f} MB")


def split():
    """Split old checkpoint into new format"""
    if not OLD_CHECKPOINT.exists():
        print("No old checkpoint to split")
        return

    print(f"Loading {OLD_CHECKPOINT}...")
    with open(OLD_CHECKPOINT, "r", encoding="utf-8") as f:
        data = json.load(f)

    results = data.pop("results", [])
    print(f"Found {len(results):,} results")

    # Save chunks
    num_chunks = 0
    for i in range(0, len(results), CHUNK_SIZE):
        chunk = results[i:i+CHUNK_SIZE]
        chunk_path = DATA_DIR / f"wikidata_results_chunk_{num_chunks}.json"
        with open(chunk_path, "w", encoding="utf-8") as f:
            json.dump(chunk, f, ensure_ascii=False)
        print(f"  Saved chunk {num_chunks}: {len(chunk):,} results")
        num_chunks += 1

    # Save state
    data["result_chunks"] = num_chunks
    data["total_results"] = len(results)

    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\nSplit complete!")
    print(f"  State file: {STATE_FILE}")
    print(f"  Chunks: {num_chunks}")

    # Optionally rename old file
    backup = DATA_DIR / "wikidata_checkpoint.json.split_backup"
    OLD_CHECKPOINT.rename(backup)
    print(f"  Old file backed up to: {backup}")


def merge():
    """Merge chunks back to single file"""
    state = load_state()
    if not state:
        print("No state file found")
        return

    print("Loading all chunks...")
    results = load_all_results()
    print(f"Loaded {len(results):,} results")

    # Build merged data
    merged = {
        "last_offset": state["last_offset"],
        "stats": state["stats"],
        "llm_pending": state.get("llm_pending", []),
        "results": results
    }

    output = DATA_DIR / "wikidata_checkpoint_merged.json"
    with open(output, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False)

    print(f"Merged to: {output}")
    print(f"Size: {output.stat().st_size / (1024*1024):.1f} MB")


def resume_info():
    """Show command to resume processing"""
    state = load_state()
    if not state:
        print("No checkpoint found")
        return

    print("To resume processing, run:")
    print()
    print("  python poc/scripts/wikidata_match_parallel.py --resume --skip-llm")
    print()
    print(f"This will continue from offset {state['last_offset']:,}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python checkpoint_utils.py [status|split|merge|resume]")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "status":
        status()
    elif cmd == "split":
        split()
    elif cmd == "merge":
        merge()
    elif cmd == "resume":
        resume_info()
    else:
        print(f"Unknown command: {cmd}")
        print("Available: status, split, merge, resume")
