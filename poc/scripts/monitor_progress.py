"""
Archivist Progress Monitor (Console)
- Auto-refresh every 5 seconds
- Shows Phase 1 and Phase 2 status
- Press Ctrl+C to exit
"""
import json
import time
import os
import sys
from pathlib import Path
from datetime import datetime

DATA_DIR = Path(__file__).parent.parent / "data"
STATUS_FILE = DATA_DIR / "status.json"
PENDING_QUEUE_FILE = DATA_DIR / "pending_queue.jsonl"
DECISIONS_FILE = DATA_DIR / "phase2_decisions.jsonl"


def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')


def count_lines(file_path: Path) -> int:
    if not file_path.exists():
        return 0
    count = 0
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                count += 1
    return count


def format_duration(hours: float) -> str:
    if hours < 1:
        return f"{int(hours * 60)}m"
    elif hours < 24:
        return f"{hours:.1f}h"
    else:
        days = hours / 24
        return f"{days:.1f}d"


def get_status():
    if not STATUS_FILE.exists():
        return None
    try:
        with open(STATUS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return None


def print_progress_bar(percent: float, width: int = 40) -> str:
    filled = int(width * percent / 100)
    bar = "=" * filled + "-" * (width - filled)
    return f"[{bar}] {percent:.1f}%"


def display_status():
    clear_screen()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    print("=" * 60)
    print("  ARCHIVIST PROGRESS MONITOR")
    print(f"  Last update: {now}")
    print("=" * 60)
    print()

    status = get_status()

    if not status:
        print("  [!] No status file found.")
        print("  [!] Run archivist_fullscale.py to start processing.")
        return

    # Phase 1
    p1 = status.get("phase1", {})
    p1_status = p1.get("status", "idle")

    print("  PHASE 1 (Fast Mode - CPU)")
    print("  " + "-" * 40)

    if p1_status == "idle":
        print("  Status: IDLE (not started)")
    elif p1_status == "running":
        print(f"  Status: RUNNING")
        print(f"  Files:  {p1.get('processed_files', 0):,} / {p1.get('total_files', 0):,}")
        print(f"  {print_progress_bar(p1.get('progress_percent', 0))}")
        print(f"  Speed:  {p1.get('speed_files_per_hour', 0):,.0f} files/hour")
        print(f"  ETA:    {format_duration(p1.get('eta_hours', 0))}")
        print(f"  Entities: {p1.get('total_entities', 0):,}")
        print(f"  Pending:  {p1.get('total_pending', 0):,}")
    elif p1_status == "completed":
        print(f"  Status: COMPLETED")
        print(f"  Files:  {p1.get('processed_files', 0):,} / {p1.get('total_files', 0):,}")
        print(f"  {print_progress_bar(100)}")
        print(f"  Entities: {p1.get('total_entities', 0):,}")
        print(f"  Pending:  {p1.get('total_pending', 0):,}")
    elif p1_status == "error":
        print(f"  Status: ERROR")
        errors = p1.get("errors", [])
        if errors:
            print(f"  Last Error: {errors[-1][:50]}...")

    print()

    # Phase 2
    p2 = status.get("phase2", {})
    p2_status = p2.get("status", "waiting")

    print("  PHASE 2 (LLM Review - GPU)")
    print("  " + "-" * 40)

    if p2_status == "waiting":
        print("  Status: WAITING (for Phase 1)")
    elif p2_status == "running":
        print(f"  Status: RUNNING")
        print(f"  Items:  {p2.get('processed_pending', 0):,} / {p2.get('total_pending', 0):,}")
        print(f"  {print_progress_bar(p2.get('progress_percent', 0))}")
        print(f"  Speed:  {p2.get('speed_items_per_hour', 0):,.0f} items/hour")
        print(f"  LINK_EXISTING: {p2.get('link_existing_count', 0):,}")
        print(f"  CREATE_NEW:    {p2.get('create_new_count', 0):,}")
    elif p2_status == "completed":
        print(f"  Status: COMPLETED")
        print(f"  {print_progress_bar(100)}")
        print(f"  LINK_EXISTING: {p2.get('link_existing_count', 0):,}")
        print(f"  CREATE_NEW:    {p2.get('create_new_count', 0):,}")

    print()

    # File counts
    pending_count = count_lines(PENDING_QUEUE_FILE)
    decisions_count = count_lines(DECISIONS_FILE)

    print("  FILE COUNTS")
    print("  " + "-" * 40)
    print(f"  pending_queue.jsonl:    {pending_count:,} items")
    print(f"  phase2_decisions.jsonl: {decisions_count:,} decisions")
    print(f"  Remaining:              {max(0, pending_count - decisions_count):,} items")

    print()
    print("=" * 60)
    print("  Press Ctrl+C to exit")
    print("=" * 60)


def main():
    print("Starting Archivist Progress Monitor...")
    print("Press Ctrl+C to exit.")
    time.sleep(1)

    try:
        while True:
            display_status()
            time.sleep(5)  # Refresh every 5 seconds
    except KeyboardInterrupt:
        print("\n\nMonitor stopped.")


if __name__ == "__main__":
    main()
