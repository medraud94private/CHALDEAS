"""
체크포인트 시스템 테스트
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.checkpoint import (
    StatusManager, PendingQueue, Phase2Decisions, Phase1Checkpoint
)

TEST_DIR = Path(__file__).parent.parent / "data" / "test_checkpoint"


def test_status_manager():
    print("=== Testing StatusManager ===")
    sm = StatusManager(TEST_DIR)

    # Phase 1 시작
    sm.start_phase1(total_files=100)
    status = sm.get_status()
    assert status["phase1"]["status"] == "running"
    assert status["phase1"]["total_files"] == 100
    print("  [OK] start_phase1")

    # Phase 1 업데이트
    sm.update_phase1(processed_files=50, total_entities=500, total_pending=200)
    status = sm.get_status()
    assert status["phase1"]["processed_files"] == 50
    assert status["phase1"]["progress_percent"] == 50.0
    print("  [OK] update_phase1")

    # Phase 1 완료
    sm.complete_phase1()
    assert sm.is_phase1_completed()
    print("  [OK] complete_phase1")

    print("  StatusManager: PASSED\n")


def test_pending_queue():
    print("=== Testing PendingQueue ===")
    pq = PendingQueue(TEST_DIR)
    pq.clear()

    # 항목 추가
    id1 = pq.append(
        text="Caesar",
        entity_type="person",
        context="Julius Caesar was...",
        candidates=[{"id": 1, "normalized": "Julius Caesar"}],
        source="test.txt"
    )
    assert id1 == 1
    print(f"  [OK] append (id={id1})")

    id2 = pq.append(
        text="Rome",
        entity_type="location",
        context="The city of Rome...",
        candidates=[],
        source="test.txt"
    )
    assert id2 == 2
    print(f"  [OK] append (id={id2})")

    # 조회
    all_items = pq.get_all()
    assert len(all_items) == 2
    assert all_items[0]["text"] == "Caesar"
    assert all_items[1]["text"] == "Rome"
    print(f"  [OK] get_all (count={len(all_items)})")

    # 개수
    assert pq.count() == 2
    print(f"  [OK] count")

    print("  PendingQueue: PASSED\n")


def test_phase2_decisions():
    print("=== Testing Phase2Decisions ===")
    p2d = Phase2Decisions(TEST_DIR)
    p2d.clear()
    pq = PendingQueue(TEST_DIR)

    # 결정 추가
    p2d.append(pending_id=1, decision="LINK_EXISTING", linked_entity_id=42)
    assert p2d.is_processed(1)
    assert not p2d.is_processed(2)
    print("  [OK] append & is_processed")

    # 처리 안 된 항목
    unprocessed = p2d.get_unprocessed(pq)
    assert len(unprocessed) == 1
    assert unprocessed[0]["id"] == 2
    print(f"  [OK] get_unprocessed (count={len(unprocessed)})")

    # 통계
    stats = p2d.get_stats()
    assert stats["total"] == 1
    assert stats["link_existing"] == 1
    print(f"  [OK] get_stats: {stats}")

    print("  Phase2Decisions: PASSED\n")


def test_phase1_checkpoint():
    print("=== Testing Phase1Checkpoint ===")
    cp = Phase1Checkpoint(TEST_DIR)
    cp.clear()

    # 저장
    cp.save(
        processed_files=["file1.txt", "file2.txt"],
        registry_entities=[
            {"id": 1, "text": "Caesar", "normalized": "Julius Caesar"}
        ],
        next_entity_id=2
    )
    print("  [OK] save")

    # 로드
    data = cp.load()
    assert data is not None
    assert data["processed_files_count"] == 2
    assert len(data["registry"]["entities"]) == 1
    print("  [OK] load")

    # 처리된 파일 목록
    processed = cp.get_processed_files()
    assert "file1.txt" in processed
    assert "file2.txt" in processed
    print(f"  [OK] get_processed_files: {processed}")

    print("  Phase1Checkpoint: PASSED\n")


def cleanup():
    import shutil
    if TEST_DIR.exists():
        shutil.rmtree(TEST_DIR)
    print("Cleanup done.")


if __name__ == "__main__":
    print("\n" + "="*50)
    print("  Checkpoint System Test")
    print("="*50 + "\n")

    try:
        test_status_manager()
        test_pending_queue()
        test_phase2_decisions()
        test_phase1_checkpoint()

        print("="*50)
        print("  ALL TESTS PASSED!")
        print("="*50 + "\n")
    except Exception as e:
        print(f"\n  FAILED: {e}")
        import traceback
        traceback.print_exc()
    finally:
        cleanup()
