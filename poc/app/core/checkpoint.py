"""
Checkpoint System for Archivist V4
- StatusManager: 상황판 관리
- PendingQueue: PENDING 큐 관리 (JSONL, append-only, with buffering)
- Phase1Checkpoint: Phase 1 체크포인트 (경량화 - mentions 분리)
- Phase2Decisions: Phase 2 결정 저장 (streaming read)
- EntityRegistry: Entity 중복 제거용 레지스트리 (mentions 미저장)
- MentionStore: Mention 별도 저장 (JSONL, append-only)

V4 변경사항:
- mentions를 EntityRegistry에서 분리 → MentionStore로 이동
- checkpoint 파일 크기 대폭 감소 (811MB → ~5MB)
- mentions.jsonl은 append-only로 빠른 저장
"""
import json
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional, Set, Generator, Tuple
from dataclasses import dataclass, asdict
import threading
import hashlib


DATA_DIR = Path(__file__).parent.parent.parent / "data"


@dataclass
class Phase1Status:
    status: str = "idle"  # idle, running, completed, error
    started_at: Optional[str] = None
    updated_at: Optional[str] = None
    completed_at: Optional[str] = None
    total_files: int = 0
    processed_files: int = 0
    progress_percent: float = 0.0
    speed_files_per_hour: float = 0.0
    eta_hours: float = 0.0
    total_entities: int = 0
    total_pending: int = 0
    unique_entities: int = 0  # 중복 제거 후 개수
    errors: List[str] = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []


@dataclass
class Phase2Status:
    status: str = "waiting"  # waiting, running, completed, error
    started_at: Optional[str] = None
    updated_at: Optional[str] = None
    completed_at: Optional[str] = None
    total_pending: int = 0
    processed_pending: int = 0
    progress_percent: float = 0.0
    speed_items_per_hour: float = 0.0
    link_existing_count: int = 0
    create_new_count: int = 0
    errors: List[str] = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []


def atomic_write_json(filepath: Path, data: Any, max_retries: int = 5):
    """Atomic JSON write using temp file + rename with retry for Windows file locking"""
    import time
    import random

    # Use random suffix to avoid conflicts
    temp_file = filepath.with_suffix(f'.tmp{random.randint(1000, 9999)}')
    filepath.parent.mkdir(parents=True, exist_ok=True)

    # Write to temp file
    with open(temp_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    # Try to replace with retries (Windows file locking workaround)
    last_error = None
    for attempt in range(max_retries):
        try:
            temp_file.replace(filepath)
            return  # Success
        except PermissionError as e:
            last_error = e
            # Wait with exponential backoff + jitter
            wait_time = (0.1 * (2 ** attempt)) + (random.random() * 0.1)
            time.sleep(wait_time)
        except OSError as e:
            if e.winerror == 32:  # WinError 32: file in use
                last_error = e
                wait_time = (0.1 * (2 ** attempt)) + (random.random() * 0.1)
                time.sleep(wait_time)
            else:
                raise

    # Last resort: try shutil.move
    try:
        import shutil
        shutil.move(str(temp_file), str(filepath))
    except Exception as e:
        # Clean up temp file
        try:
            temp_file.unlink()
        except:
            pass
        raise last_error or e


class StatusManager:
    """상황판 관리 - 실시간 진행 상태 추적"""

    def __init__(self, data_dir: Path = None):
        self.data_dir = data_dir or DATA_DIR
        self.status_file = self.data_dir / "status.json"
        self._lock = threading.Lock()
        self._start_time: Optional[datetime] = None
        self._last_count: int = 0
        self._last_time: Optional[datetime] = None

    def _load(self) -> Dict:
        if self.status_file.exists():
            try:
                with open(self.status_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass
        return {
            "phase1": asdict(Phase1Status()),
            "phase2": asdict(Phase2Status())
        }

    def _save(self, data: Dict):
        atomic_write_json(self.status_file, data)

    def start_phase1(self, total_files: int):
        """Phase 1 시작"""
        with self._lock:
            data = self._load()
            now = datetime.now().isoformat()
            self._start_time = datetime.now()
            self._last_count = 0
            self._last_time = datetime.now()

            data["phase1"] = asdict(Phase1Status(
                status="running",
                started_at=now,
                updated_at=now,
                total_files=total_files
            ))
            self._save(data)
            print(f"[Status] Phase 1 started: {total_files} files")

    def update_phase1(self, processed_files: int, total_entities: int,
                      total_pending: int, unique_entities: int = 0):
        """Phase 1 진행 상황 업데이트"""
        with self._lock:
            data = self._load()
            now = datetime.now()
            p1 = data["phase1"]

            # 속도 계산
            if self._start_time:
                elapsed_hours = (now - self._start_time).total_seconds() / 3600
                if elapsed_hours > 0:
                    p1["speed_files_per_hour"] = round(processed_files / elapsed_hours, 1)
                    remaining = p1["total_files"] - processed_files
                    if p1["speed_files_per_hour"] > 0:
                        p1["eta_hours"] = round(remaining / p1["speed_files_per_hour"], 1)

            p1["updated_at"] = now.isoformat()
            p1["processed_files"] = processed_files
            p1["total_entities"] = total_entities
            p1["total_pending"] = total_pending
            p1["unique_entities"] = unique_entities
            if p1["total_files"] > 0:
                p1["progress_percent"] = round(processed_files / p1["total_files"] * 100, 2)

            self._save(data)

    def complete_phase1(self):
        """Phase 1 완료"""
        with self._lock:
            data = self._load()
            now = datetime.now().isoformat()
            data["phase1"]["status"] = "completed"
            data["phase1"]["completed_at"] = now
            data["phase1"]["updated_at"] = now
            data["phase1"]["progress_percent"] = 100.0
            self._save(data)
            print(f"[Status] Phase 1 completed")

    def error_phase1(self, error_msg: str):
        """Phase 1 에러"""
        with self._lock:
            data = self._load()
            data["phase1"]["status"] = "error"
            data["phase1"]["updated_at"] = datetime.now().isoformat()
            data["phase1"]["errors"].append(f"{datetime.now().isoformat()}: {error_msg}")
            self._save(data)
            print(f"[Status] Phase 1 error: {error_msg}")

    def start_phase2(self, total_pending: int):
        """Phase 2 시작"""
        with self._lock:
            data = self._load()
            now = datetime.now().isoformat()
            self._start_time = datetime.now()

            data["phase2"] = asdict(Phase2Status(
                status="running",
                started_at=now,
                updated_at=now,
                total_pending=total_pending
            ))
            self._save(data)
            print(f"[Status] Phase 2 started: {total_pending} pending items")

    def update_phase2(self, processed: int, link_existing: int, create_new: int):
        """Phase 2 진행 상황 업데이트"""
        with self._lock:
            data = self._load()
            now = datetime.now()
            p2 = data["phase2"]

            # 속도 계산
            if self._start_time:
                elapsed_hours = (now - self._start_time).total_seconds() / 3600
                if elapsed_hours > 0:
                    p2["speed_items_per_hour"] = round(processed / elapsed_hours, 1)

            p2["updated_at"] = now.isoformat()
            p2["processed_pending"] = processed
            p2["link_existing_count"] = link_existing
            p2["create_new_count"] = create_new
            if p2["total_pending"] > 0:
                p2["progress_percent"] = round(processed / p2["total_pending"] * 100, 2)

            self._save(data)

    def complete_phase2(self):
        """Phase 2 완료"""
        with self._lock:
            data = self._load()
            now = datetime.now().isoformat()
            data["phase2"]["status"] = "completed"
            data["phase2"]["completed_at"] = now
            data["phase2"]["updated_at"] = now
            data["phase2"]["progress_percent"] = 100.0
            self._save(data)
            print(f"[Status] Phase 2 completed")

    def get_status(self) -> Dict:
        """현재 상태 조회"""
        return self._load()

    def is_phase1_completed(self) -> bool:
        """Phase 1 완료 여부"""
        data = self._load()
        return data["phase1"]["status"] == "completed"


class MentionStore:
    """
    Mention 저장소 - JSONL, append-only

    V4에서 추가: mentions를 별도 파일로 분리하여 checkpoint 저장 속도 개선
    """

    def __init__(self, data_dir: Path = None):
        self.data_dir = data_dir or DATA_DIR
        self.mentions_file = self.data_dir / "mentions.jsonl"
        self._lock = threading.Lock()
        self._buffer: List[Dict] = []
        self._total_count = 0
        self._load_count()

    def _load_count(self):
        """기존 mention 개수 로드"""
        if self.mentions_file.exists():
            try:
                with open(self.mentions_file, 'r', encoding='utf-8') as f:
                    for _ in f:
                        self._total_count += 1
            except:
                pass

    def buffer_mention(self, entity_key: str, source_path: str,
                       start: int, end: int,
                       chunk_start: int = 0, chunk_end: int = 0):
        """
        Buffer에 mention 추가 (flush 전까지 파일에 쓰지 않음)
        """
        with self._lock:
            self._buffer.append({
                "entity_key": entity_key,
                "source_path": source_path,
                "start": start,
                "end": end,
                "chunk_start": chunk_start,
                "chunk_end": chunk_end
            })

    def flush_buffer(self) -> int:
        """Buffer를 파일에 flush"""
        with self._lock:
            if not self._buffer:
                return 0

            self.data_dir.mkdir(parents=True, exist_ok=True)

            count = len(self._buffer)
            with open(self.mentions_file, 'a', encoding='utf-8') as f:
                for mention in self._buffer:
                    f.write(json.dumps(mention, ensure_ascii=False) + '\n')

            self._total_count += count
            self._buffer.clear()
            return count

    def get_buffer_count(self) -> int:
        """Buffer에 있는 mention 개수"""
        return len(self._buffer)

    def get_total_count(self) -> int:
        """전체 mention 개수 (파일 + 버퍼)"""
        return self._total_count + len(self._buffer)

    def iter_mentions(self, entity_key: str = None) -> Generator[Dict, None, None]:
        """
        Mention 스트리밍 조회

        Args:
            entity_key: 특정 entity의 mentions만 조회 (None이면 전체)
        """
        if self.mentions_file.exists():
            with open(self.mentions_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        mention = json.loads(line)
                        if entity_key is None or mention.get("entity_key") == entity_key:
                            yield mention

    def clear(self):
        """초기화 (주의!)"""
        with self._lock:
            if self.mentions_file.exists():
                self.mentions_file.unlink()
            self._buffer.clear()
            self._total_count = 0


class EntityRegistry:
    """
    Entity registry - 중복 제거 및 카운트 관리

    V4 변경: mentions를 저장하지 않음 (MentionStore로 분리)
    """

    def __init__(self, mention_store: MentionStore = None):
        # Key: entity_key -> entity metadata (without mentions)
        self._entities: Dict[str, Dict] = {}
        self._lock = threading.Lock()
        self._mention_store = mention_store

    @staticmethod
    def normalize(text: str) -> str:
        """Normalize entity text for matching"""
        return text.lower().strip()

    @staticmethod
    def entity_key(text: str, entity_type: str) -> str:
        """Create unique key for entity"""
        normalized = EntityRegistry.normalize(text)
        return f"{entity_type}:{normalized}"

    def add_mention(self, text: str, entity_type: str,
                    source_path: str, start: int, end: int,
                    chunk_start: int = 0, chunk_end: int = 0) -> Tuple[bool, str]:
        """
        Add a mention of an entity.

        Args:
            text: Entity text as found
            entity_type: person/location/event
            source_path: Relative path to source file
            start: Entity start position in file (absolute)
            end: Entity end position in file (absolute)
            chunk_start: Start of the chunk this entity was found in
            chunk_end: End of the chunk this entity was found in

        Returns: (is_new_entity, entity_key)
        """
        with self._lock:
            key = self.entity_key(text, entity_type)

            # Write mention to MentionStore (if provided)
            if self._mention_store:
                self._mention_store.buffer_mention(
                    entity_key=key,
                    source_path=source_path,
                    start=start,
                    end=end,
                    chunk_start=chunk_start,
                    chunk_end=chunk_end
                )

            if key in self._entities:
                # Existing entity - increment count
                entity = self._entities[key]
                entity["mention_count"] += 1

                # Update sample if this text is longer (just for preview)
                if len(text) > len(entity.get("sample_text", "")):
                    entity["sample_text"] = text

                return (False, key)
            else:
                # New entity
                self._entities[key] = {
                    "text": text,  # Original text (first occurrence)
                    "normalized": self.normalize(text),
                    "entity_type": entity_type,
                    "sample_text": text,  # For quick preview
                    "mention_count": 1,
                    "first_seen": datetime.now().isoformat()
                }
                return (True, key)

    def get_unique_count(self) -> int:
        """Get count of unique entities"""
        return len(self._entities)

    def get_total_mentions(self) -> int:
        """Get total mention count across all entities"""
        return sum(e["mention_count"] for e in self._entities.values())

    def get_all_entities(self) -> List[Dict]:
        """Get all entities as list (for checkpoint) - V4: without mentions"""
        result = []
        for key, entity in self._entities.items():
            entry = entity.copy()
            entry["key"] = key
            result.append(entry)
        return result

    def load_from_data(self, entities: List[Dict]):
        """Load from checkpoint data - V4: no mentions in checkpoint"""
        with self._lock:
            self._entities.clear()
            for entity in entities:
                key = entity.get("key") or self.entity_key(entity["text"], entity["entity_type"])
                self._entities[key] = {
                    "text": entity["text"],
                    "normalized": entity.get("normalized", self.normalize(entity["text"])),
                    "entity_type": entity["entity_type"],
                    "sample_text": entity.get("sample_text", entity.get("text", "")),
                    "mention_count": entity.get("mention_count", 1),
                    "first_seen": entity.get("first_seen", datetime.now().isoformat())
                }

    def get_entity(self, key: str) -> Optional[Dict]:
        """Get a specific entity by key"""
        return self._entities.get(key)

    def find_similar(self, text: str, entity_type: str, limit: int = 5) -> List[Dict]:
        """Find similar entities by simple text matching"""
        normalized = self.normalize(text)
        candidates = []

        for key, entity in self._entities.items():
            if entity["entity_type"] != entity_type:
                continue

            entity_norm = entity["normalized"]

            # Calculate simple similarity
            if normalized == entity_norm:
                similarity = 1.0
            elif normalized in entity_norm or entity_norm in normalized:
                similarity = 0.8
            elif len(set(normalized.split()) & set(entity_norm.split())) > 0:
                similarity = 0.5
            else:
                continue

            candidates.append({
                "key": key,
                "text": entity["text"],
                "normalized": entity_norm,
                "entity_type": entity_type,
                "similarity": similarity,
                "mention_count": entity["mention_count"]
            })

        # Sort by similarity and mention count
        candidates.sort(key=lambda x: (-x["similarity"], -x["mention_count"]))
        return candidates[:limit]


class PendingQueue:
    """PENDING 큐 관리 - JSONL, append-only with buffering for checkpoint sync"""

    def __init__(self, data_dir: Path = None):
        self.data_dir = data_dir or DATA_DIR
        self.queue_file = self.data_dir / "pending_queue.jsonl"
        self._lock = threading.Lock()
        self._next_id = 1
        self._buffer: List[Dict] = []  # Buffer for checkpoint sync
        self._load_next_id()

    def _load_next_id(self):
        """마지막 ID 확인"""
        if self.queue_file.exists():
            try:
                with open(self.queue_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        if line.strip():
                            item = json.loads(line)
                            self._next_id = max(self._next_id, item.get("id", 0) + 1)
            except:
                pass

    def buffer_append(self, text: str, entity_type: str,
                      entity_key: str, mention_count: int = 1,
                      sample: str = "") -> int:
        """
        Buffer에 PENDING 항목 추가 (flush 전까지 파일에 쓰지 않음)

        Args:
            text: Entity text
            entity_type: person/location/event
            entity_key: Unique key for this entity
            mention_count: Number of mentions found
            sample: Optional sample text for preview
        """
        with self._lock:
            item = {
                "id": self._next_id,
                "text": text,
                "entity_type": entity_type,
                "entity_key": entity_key,
                "mention_count": mention_count,
                "sample": sample[:200] if sample else text,
                "created_at": datetime.now().isoformat()
            }
            self._buffer.append(item)
            self._next_id += 1
            return item["id"]

    def flush_buffer(self) -> int:
        """Buffer를 파일에 flush (checkpoint 저장 시 호출)"""
        with self._lock:
            if not self._buffer:
                return 0

            self.data_dir.mkdir(parents=True, exist_ok=True)

            count = len(self._buffer)
            with open(self.queue_file, 'a', encoding='utf-8') as f:
                for item in self._buffer:
                    f.write(json.dumps(item, ensure_ascii=False) + '\n')

            self._buffer.clear()
            return count

    def get_buffer_count(self) -> int:
        """Buffer에 있는 항목 개수"""
        return len(self._buffer)

    def append(self, text: str, entity_type: str, context: str,
               candidates: List[Dict], source: str) -> int:
        """PENDING 항목 즉시 추가 (하위 호환용 - 권장하지 않음)"""
        with self._lock:
            self.data_dir.mkdir(parents=True, exist_ok=True)

            item = {
                "id": self._next_id,
                "text": text,
                "entity_type": entity_type,
                "context": context[:500],
                "candidates": candidates,
                "source": source,
                "created_at": datetime.now().isoformat()
            }

            with open(self.queue_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(item, ensure_ascii=False) + '\n')

            self._next_id += 1
            return item["id"]

    def iter_items(self) -> Generator[Dict, None, None]:
        """Streaming read - 메모리 효율적"""
        if self.queue_file.exists():
            with open(self.queue_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        yield json.loads(line)

    def get_all(self) -> List[Dict]:
        """전체 PENDING 항목 조회 (메모리 주의)"""
        return list(self.iter_items())

    def count(self) -> int:
        """총 개수 (파일 + 버퍼)"""
        file_count = 0
        if self.queue_file.exists():
            with open(self.queue_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        file_count += 1
        return file_count + len(self._buffer)

    def file_count(self) -> int:
        """파일에 저장된 개수만"""
        if not self.queue_file.exists():
            return 0
        count = 0
        with open(self.queue_file, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    count += 1
        return count

    def clear(self):
        """큐 초기화 (주의!)"""
        with self._lock:
            if self.queue_file.exists():
                self.queue_file.unlink()
            self._next_id = 1
            self._buffer.clear()


class Phase2Decisions:
    """Phase 2 결정 저장 - JSONL, append-only with streaming"""

    def __init__(self, data_dir: Path = None):
        self.data_dir = data_dir or DATA_DIR
        self.decisions_file = self.data_dir / "phase2_decisions.jsonl"
        self._lock = threading.Lock()
        self._processed_ids: Set[int] = set()
        self._load_processed_ids()

    def _load_processed_ids(self):
        """처리된 ID 목록 로드"""
        if self.decisions_file.exists():
            try:
                with open(self.decisions_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        if line.strip():
                            item = json.loads(line)
                            self._processed_ids.add(item.get("pending_id"))
            except:
                pass

    def is_processed(self, pending_id: int) -> bool:
        """이미 처리됐는지 확인"""
        return pending_id in self._processed_ids

    def append(self, pending_id: int, decision: str,
               linked_entity_id: Optional[int] = None,
               new_entity_id: Optional[int] = None,
               confidence: float = 0.0,
               linked_entity_key: Optional[str] = None):
        """결정 추가 (append-only)"""
        with self._lock:
            self.data_dir.mkdir(parents=True, exist_ok=True)

            item = {
                "pending_id": pending_id,
                "decision": decision,
                "linked_entity_id": linked_entity_id,
                "linked_entity_key": linked_entity_key,
                "new_entity_id": new_entity_id,
                "confidence": confidence,
                "processed_at": datetime.now().isoformat()
            }

            with open(self.decisions_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(item, ensure_ascii=False) + '\n')

            self._processed_ids.add(pending_id)

    def iter_unprocessed(self, pending_queue: PendingQueue, batch_size: int = 100) -> Generator[List[Dict], None, None]:
        """Streaming으로 미처리 항목 batch 단위로 yield (메모리 효율적)"""
        batch = []
        for item in pending_queue.iter_items():
            if item["id"] not in self._processed_ids:
                batch.append(item)
                if len(batch) >= batch_size:
                    yield batch
                    batch = []
        if batch:
            yield batch

    def get_unprocessed(self, pending_queue: PendingQueue) -> List[Dict]:
        """처리 안 된 PENDING 항목들 (하위 호환 - 작은 데이터셋용)"""
        all_pending = pending_queue.get_all()
        return [p for p in all_pending if p["id"] not in self._processed_ids]

    def get_unprocessed_count(self, pending_queue: PendingQueue) -> int:
        """미처리 항목 개수 (메모리 효율적)"""
        count = 0
        for item in pending_queue.iter_items():
            if item["id"] not in self._processed_ids:
                count += 1
        return count

    def get_processed_count(self) -> int:
        """처리된 항목 개수"""
        return len(self._processed_ids)

    def get_stats(self) -> Dict:
        """통계"""
        stats = {
            "total": 0,
            "link_existing": 0,
            "create_new": 0,
            "pending": 0
        }
        if self.decisions_file.exists():
            with open(self.decisions_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        item = json.loads(line)
                        stats["total"] += 1
                        decision = item.get("decision", "")
                        if decision == "LINK_EXISTING":
                            stats["link_existing"] += 1
                        elif decision == "CREATE_NEW":
                            stats["create_new"] += 1
                        else:
                            stats["pending"] += 1
        return stats

    def clear(self):
        """초기화 (주의!)"""
        with self._lock:
            if self.decisions_file.exists():
                self.decisions_file.unlink()
            self._processed_ids.clear()


class Phase1Checkpoint:
    """
    Phase 1 체크포인트 - 경량화 버전 (V4)

    V4 변경: mentions 제외, MentionStore와 분리
    """

    def __init__(self, data_dir: Path = None):
        self.data_dir = data_dir or DATA_DIR
        self.checkpoint_file = self.data_dir / "phase1_checkpoint.json"
        self._lock = threading.Lock()

    def save(self, processed_files: List[str], registry_entities: List[Dict],
             next_entity_id: int, pending_queue: PendingQueue = None,
             mention_store: MentionStore = None,
             exported_entities: List[str] = None):
        """
        체크포인트 저장 (V4: 경량화)

        Args:
            processed_files: 처리된 파일 목록
            registry_entities: EntityRegistry.get_all_entities() 결과 (mentions 미포함)
            next_entity_id: 다음 entity ID
            pending_queue: PendingQueue (buffer flush용)
            mention_store: MentionStore (buffer flush용)
            exported_entities: Export된 entity keys
        """
        with self._lock:
            self.data_dir.mkdir(parents=True, exist_ok=True)

            # pending_queue buffer flush
            pending_flushed = 0
            if pending_queue:
                pending_flushed = pending_queue.flush_buffer()

            # mention_store buffer flush
            mentions_flushed = 0
            if mention_store:
                mentions_flushed = mention_store.flush_buffer()

            # Calculate total mentions from entities
            total_mentions = sum(
                e.get("mention_count", 1)
                for e in registry_entities
            )

            data = {
                "version": 4,
                "timestamp": datetime.now().isoformat(),
                "processed_files_count": len(processed_files),
                "processed_files": processed_files,
                "exported_entities": exported_entities or [],
                "registry": {
                    "entities": registry_entities,  # V4: mentions 미포함
                    "next_id": next_entity_id,
                    "unique_count": len(registry_entities),
                    "total_mentions": total_mentions
                },
                "pending_flushed": pending_flushed,
                "mentions_flushed": mentions_flushed
            }

            # Atomic write
            atomic_write_json(self.checkpoint_file, data)

    def load(self) -> Optional[Dict]:
        """체크포인트 로드"""
        if self.checkpoint_file.exists():
            try:
                with open(self.checkpoint_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass
        return None

    def get_processed_files(self) -> Set[str]:
        """처리된 파일 목록"""
        data = self.load()
        if data:
            return set(data.get("processed_files", []))
        return set()

    def clear(self):
        """초기화 (주의!)"""
        if self.checkpoint_file.exists():
            self.checkpoint_file.unlink()


class FileCountCache:
    """파일 개수 캐싱 (10초 이상 걸리는 카운트 방지)"""

    def __init__(self, data_dir: Path = None):
        self.data_dir = data_dir or DATA_DIR
        self.cache_file = self.data_dir / "file_count_cache.json"

    def get_cached_count(self) -> Optional[int]:
        """캐시된 파일 개수 조회"""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get("total_files")
            except:
                pass
        return None

    def save_count(self, total_files: int, source_counts: Dict[str, int]):
        """파일 개수 캐시 저장"""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        data = {
            "total_files": total_files,
            "source_counts": source_counts,
            "cached_at": datetime.now().isoformat()
        }
        atomic_write_json(self.cache_file, data)

    def clear(self):
        """캐시 초기화"""
        if self.cache_file.exists():
            self.cache_file.unlink()
