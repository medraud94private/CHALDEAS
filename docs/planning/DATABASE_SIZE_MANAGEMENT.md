# 데이터베이스 용량 관리

## 개요

CHALDEAS는 두 가지 DB 버전을 운영합니다:

| 버전 | 용량 | 용도 |
|------|------|------|
| **Full** | ~5,040 MB | 로컬 개발, 데이터 파이프라인 |
| **Compact** | ~1,600 MB | 프로덕션 배포 |

**핵심 원칙**: 서버 코드는 동일, 데이터만 다름 → API 결과 동일

---

## Full vs Compact 비교

### 공통 (양쪽 모두 포함)

| 테이블 | 설명 | Compact 크기 |
|--------|------|--------------|
| events | 역사적 사건 (연결된 것만) | ~127 MB |
| persons | 역사적 인물 (연결된 것만) | ~509 MB |
| locations | 장소 (연결된 것만) | ~77 MB |
| **sources** | **Wikipedia 원문 전체** | **~448 MB** |
| 관계 테이블 | 모든 연결 정보 | ~328 MB |
| categories, periods 등 | 메타데이터 | ~10 MB |

### Full에만 포함

| 테이블 | 용량 | 용도 |
|--------|------|------|
| 고아 엔티티 | ~400 MB | connection_count=0인 엔티티 |
| gazetteer | ~1,677 MB | 지명→좌표 변환 사전 |
| text_mentions | ~173 MB | NER 추출 메타데이터 |
| embeddings | ~149 MB | 벡터 검색용 |
| 백업 테이블 | ~1,035 MB | 개발용 스냅샷 |

---

## 서버 호환성

### API 동작 비교

| API | Full | Compact | 차이 |
|-----|------|---------|------|
| `GET /events` | 43,214개 | 43,214개 | 없음 (기본 orphan 제외) |
| `GET /persons` | 222,418개 | 222,418개 | 없음 (기본 orphan 제외) |
| `GET /search?q=xxx` | 모두 검색 | 연결된 것만 | 고아는 검색 안됨 |
| `GET /events/123` | 상세+원문 | 상세+원문 | 없음 |

### 왜 결과가 같은가?

1. **고아 필터링 기본 적용**: `include_orphans=false`가 기본값
2. **Sources 유지**: Wikipedia 원문은 Compact에도 포함
3. **관계 테이블 유지**: 모든 연결 정보 보존

```python
# person_service.py
def get_persons(..., include_orphans: bool = False):
    if not include_orphans:
        query = query.filter(Person.connection_count > 0)
```

---

## Compact DB 생성

### 스크립트 사용법

```bash
# 1. 분석 (변경 없음)
python scripts/create-compact-db.py --dry-run

# 2. Compact DB 생성
python scripts/create-compact-db.py --execute

# 3. 생성 + 덤프 파일
python scripts/create-compact-db.py --dump
```

### 생성 과정

```
1. chaldeas → chaldeas_compact 복사
2. 고아 엔티티 삭제 (connection_count = 0)
3. 파이프라인 테이블 삭제 (gazetteer, text_mentions, embeddings)
4. 백업 테이블 삭제 (*_backup_*)
5. VACUUM FULL
6. (선택) pg_dump로 덤프 파일 생성
```

### 출력 파일

- `chaldeas_compact_YYYYMMDD.dump` - pg_dump 커스텀 포맷

---

## 배포 워크플로우

### 로컬 테스트 (Compact)

```powershell
# Compact DB로 서버 실행
$env:DATABASE_URL = "postgresql://chaldeas:chaldeas_dev@localhost/chaldeas_compact"
cd backend
uvicorn app.main:app --reload --port 8100
```

### Cloud Run 배포

```powershell
# 1. Compact DB 생성 및 덤프
python scripts/create-compact-db.py --dump

# 2. Cloud SQL로 복원
gcloud sql import sql chaldeas-db gs://bucket/chaldeas_compact.dump

# 3. 또는 sync-db.ps1 사용
.\scripts\sync-db.ps1 up-compact
```

---

## 용량 절감 상세

### 현재 상태 (2026-01-19)

```
Full DB: 5,040 MB

제거 대상:
├── 고아 엔티티:        398 MB (7.9%)
├── gazetteer:       1,677 MB (33.3%)
├── text_mentions:     173 MB (3.4%)
├── embeddings:        149 MB (3.0%)
└── 백업 테이블:      1,035 MB (20.5%)
                     ─────────
합계:                3,432 MB (68.1%)

Compact DB: ~1,608 MB
```

### 절감 효과

| 항목 | Full | Compact | 절감 |
|------|------|---------|------|
| 용량 | 5,040 MB | 1,608 MB | 68% |
| Cloud SQL 비용 | ~$50/월 | ~$17/월 | 66% |
| 백업 시간 | ~5분 | ~2분 | 60% |

---

## 관련 파일

| 파일 | 설명 |
|------|------|
| `scripts/create-compact-db.py` | Compact DB 생성 스크립트 |
| `scripts/sync-db.ps1` | DB 동기화 (Cloud SQL) |
| `poc/scripts/update_connection_counts.py` | 고아 식별용 |

---

## FAQ

### Q: 검색 결과가 다르지 않나요?

A: 고아 엔티티는 어차피 기본 검색에서 제외됩니다. 연결 없는 엔티티는 검색해도 의미 없습니다.

### Q: 원문 조회는 되나요?

A: 네. `sources` 테이블은 Compact에도 전체 포함됩니다 (448 MB).

### Q: Full에서 새 데이터 추가 후 Compact 재생성?

A: 네. 파이프라인은 Full에서 실행 → Compact 재생성 → 배포

```
[Full DB] ──파이프라인──→ [Full DB'] ──create-compact──→ [Compact] ──배포──→ [Cloud]
```
