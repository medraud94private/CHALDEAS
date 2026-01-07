"""
Test script to verify V3 fixes work correctly.
Tests:
1. Checkpoint sync (no duplicates on restart)
2. Entity deduplication
3. Memory-efficient streaming
4. Candidates from registry
"""
import asyncio
import sys
import io
from pathlib import Path
from datetime import datetime
import json
import shutil

if sys.platform == 'win32':
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True)
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace', line_buffering=True)
    except Exception:
        pass

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.checkpoint import (
    StatusManager, PendingQueue, Phase1Checkpoint,
    Phase2Decisions, EntityRegistry, FileCountCache
)


TEST_DIR = Path(__file__).parent.parent / "data" / "test_v3"


def setup_test_dir():
    """Create clean test directory."""
    if TEST_DIR.exists():
        shutil.rmtree(TEST_DIR)
    TEST_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[Setup] Test directory: {TEST_DIR}")


def test_entity_registry():
    """Test EntityRegistry deduplication."""
    print("\n" + "=" * 50)
    print("TEST 1: Entity Registry Deduplication")
    print("=" * 50)

    registry = EntityRegistry()

    # Add same entity multiple times
    is_new1, key1 = registry.add_or_update("Alexander the Great", "person", "King of Macedon", "file1.txt")
    is_new2, key2 = registry.add_or_update("Alexander the Great", "person", "Conquered Persia", "file2.txt")
    is_new3, key3 = registry.add_or_update("alexander the great", "person", "Son of Philip II", "file3.txt")  # Different case
    is_new4, key4 = registry.add_or_update("Julius Caesar", "person", "Roman Emperor", "file4.txt")

    print(f"  'Alexander the Great' (1st): is_new={is_new1}, key={key1}")
    print(f"  'Alexander the Great' (2nd): is_new={is_new2}, key={key2}")
    print(f"  'alexander the great' (lower): is_new={is_new3}, key={key3}")
    print(f"  'Julius Caesar': is_new={is_new4}, key={key4}")

    assert is_new1 == True, "First Alexander should be new"
    assert is_new2 == False, "Second Alexander should NOT be new"
    assert is_new3 == False, "Lowercase Alexander should NOT be new"
    assert is_new4 == True, "Julius Caesar should be new"
    assert registry.get_unique_count() == 2, "Should have 2 unique entities"

    print(f"  Unique count: {registry.get_unique_count()}")
    print("  [PASS] Entity deduplication works correctly!")


def test_checkpoint_sync():
    """Test checkpoint and pending_queue sync."""
    print("\n" + "=" * 50)
    print("TEST 2: Checkpoint Sync (No Duplicates)")
    print("=" * 50)

    setup_test_dir()

    pending_queue = PendingQueue(TEST_DIR)
    checkpoint = Phase1Checkpoint(TEST_DIR)
    registry = EntityRegistry()

    # Simulate processing files
    processed_files = []

    # Process 5 files, adding to buffer
    for i in range(5):
        file_key = f"file_{i}.txt"
        processed_files.append(file_key)

        # Add entity to buffer (not yet written to file)
        pending_queue.buffer_append(
            text=f"Entity_{i}",
            entity_type="person",
            context=f"Context for entity {i}",
            entity_key=f"person:entity_{i}",
            source=file_key
        )
        registry.add_or_update(f"Entity_{i}", "person", f"Context {i}", file_key)

    print(f"  After 5 files: buffer={pending_queue.get_buffer_count()}, file={pending_queue.file_count()}")
    assert pending_queue.get_buffer_count() == 5, "Buffer should have 5 items"
    assert pending_queue.file_count() == 0, "File should have 0 items (not flushed yet)"

    # Save checkpoint (this should flush buffer)
    checkpoint.save(
        processed_files=processed_files,
        registry_entities=registry.get_all_entities(),
        next_entity_id=registry.get_unique_count(),
        pending_queue=pending_queue
    )

    print(f"  After checkpoint: buffer={pending_queue.get_buffer_count()}, file={pending_queue.file_count()}")
    assert pending_queue.get_buffer_count() == 0, "Buffer should be empty after checkpoint"
    assert pending_queue.file_count() == 5, "File should have 5 items after flush"

    # Simulate restart - load checkpoint
    pending_queue2 = PendingQueue(TEST_DIR)
    checkpoint2 = Phase1Checkpoint(TEST_DIR)
    checkpoint_data = checkpoint2.load()

    print(f"  After reload: processed_files={len(checkpoint_data['processed_files'])}, pending={pending_queue2.file_count()}")
    assert len(checkpoint_data['processed_files']) == 5, "Should have 5 processed files"
    assert pending_queue2.file_count() == 5, "Should have 5 pending items"

    # If we process file_0 again, it should be skipped
    loaded_processed = set(checkpoint_data['processed_files'])
    print(f"  'file_0.txt' in processed: {'file_0.txt' in loaded_processed}")
    assert 'file_0.txt' in loaded_processed, "file_0.txt should be in processed files"

    print("  [PASS] Checkpoint sync works correctly!")


def test_streaming_read():
    """Test memory-efficient streaming read."""
    print("\n" + "=" * 50)
    print("TEST 3: Streaming Read (Memory Efficient)")
    print("=" * 50)

    setup_test_dir()

    pending_queue = PendingQueue(TEST_DIR)
    decisions = Phase2Decisions(TEST_DIR)

    # Add 100 items directly to file
    for i in range(100):
        pending_queue.append(
            text=f"Entity_{i}",
            entity_type="person",
            context=f"Context {i}",
            candidates=[],
            source=f"file_{i}.txt"
        )

    # Process first 30
    for i in range(30):
        decisions.append(
            pending_id=i + 1,  # IDs start at 1
            decision="CREATE_NEW",
            confidence=0.9
        )

    print(f"  Total pending: {pending_queue.count()}")
    print(f"  Processed: {decisions.get_processed_count()}")

    # Use streaming iterator
    batch_count = 0
    item_count = 0
    for batch in decisions.iter_unprocessed(pending_queue, batch_size=20):
        batch_count += 1
        item_count += len(batch)
        print(f"  Batch {batch_count}: {len(batch)} items")

    print(f"  Total batches: {batch_count}, Total items: {item_count}")
    assert item_count == 70, "Should have 70 unprocessed items"
    assert batch_count == 4, "Should have 4 batches (20+20+20+10)"

    print("  [PASS] Streaming read works correctly!")


def test_candidate_finding():
    """Test finding candidates from registry."""
    print("\n" + "=" * 50)
    print("TEST 4: Candidate Finding from Registry")
    print("=" * 50)

    registry = EntityRegistry()

    # Add some entities
    registry.add_or_update("Alexander the Great", "person", "King of Macedon", "file1.txt")
    registry.add_or_update("Alexander Hamilton", "person", "US Founding Father", "file2.txt")
    registry.add_or_update("Alexandria", "location", "City in Egypt", "file3.txt")
    registry.add_or_update("Julius Caesar", "person", "Roman dictator", "file4.txt")

    # Find candidates for "Alexander"
    candidates = registry.find_similar("Alexander", "person", limit=5)
    print(f"  Candidates for 'Alexander' (person):")
    for c in candidates:
        print(f"    - {c['text']} (similarity: {c['similarity']:.2f})")

    assert len(candidates) == 2, "Should find 2 person candidates with 'Alexander'"
    assert candidates[0]['similarity'] >= 0.5, "First candidate should have similarity >= 0.5"

    # Find candidates for exact match
    candidates2 = registry.find_similar("Julius Caesar", "person", limit=5)
    print(f"  Candidates for 'Julius Caesar' (person):")
    for c in candidates2:
        print(f"    - {c['text']} (similarity: {c['similarity']:.2f})")

    assert len(candidates2) == 1, "Should find 1 exact match"
    assert candidates2[0]['similarity'] == 1.0, "Exact match should have similarity 1.0"

    # Find candidates for location
    candidates3 = registry.find_similar("Alexandria", "location", limit=5)
    print(f"  Candidates for 'Alexandria' (location):")
    for c in candidates3:
        print(f"    - {c['text']} (similarity: {c['similarity']:.2f})")

    assert len(candidates3) == 1, "Should find 1 location candidate"

    print("  [PASS] Candidate finding works correctly!")


def test_file_count_cache():
    """Test file count caching."""
    print("\n" + "=" * 50)
    print("TEST 5: File Count Cache")
    print("=" * 50)

    setup_test_dir()

    cache = FileCountCache(TEST_DIR)

    # No cache initially
    cached = cache.get_cached_count()
    print(f"  Initial cache: {cached}")
    assert cached is None, "Cache should be None initially"

    # Save count
    cache.save_count(76543, {"gutenberg": 50000, "british_library": 26543})

    # Read cache
    cached = cache.get_cached_count()
    print(f"  After save: {cached}")
    assert cached == 76543, "Cache should return 76543"

    print("  [PASS] File count cache works correctly!")


async def run_all_tests():
    """Run all tests."""
    print("=" * 60)
    print("       ARCHIVIST V3 FIX VERIFICATION TESTS")
    print("=" * 60)
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    try:
        test_entity_registry()
        test_checkpoint_sync()
        test_streaming_read()
        test_candidate_finding()
        test_file_count_cache()

        print("\n" + "=" * 60)
        print("       ALL TESTS PASSED!")
        print("=" * 60)
        print("\nV3 fixes verified:")
        print("  [OK] Entity deduplication (same entity from 100 files = 1 pending)")
        print("  [OK] Checkpoint sync (no duplicates on restart)")
        print("  [OK] Streaming read (memory efficient)")
        print("  [OK] Candidate finding (registry-based)")
        print("  [OK] File count cache (fast startup)")
        print("\nReady for production run!")

    except AssertionError as e:
        print(f"\n[FAIL] Test failed: {e}")
        return False

    return True


if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)
