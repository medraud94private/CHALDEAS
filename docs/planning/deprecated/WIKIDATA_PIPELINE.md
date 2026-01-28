# Wikidata Entity Matching Pipeline

> **Status**: In Progress
> **Last Updated**: 2026-01-15
> **Related**: `v2/ENTITY_MATCHING_STRATEGY.md`

---

## Current State (2026-01-15)

### Database Status
| Metric | Count | Percentage |
|--------|-------|------------|
| Total persons | 286,609 | 100% |
| With wikidata_id | 33,631 | 11.73% |
| Without wikidata_id | 252,978 | 88.27% |

### Pipeline Progress

#### 1. Forward Matching (DB → Wikidata Reconciliation API)
| Metric | Value |
|--------|-------|
| Script | `wikidata_reconcile.py` |
| Progress | 111,404 / 285,652 (39.0%) |
| Remaining | 174,248 |
| matched | 82,702 |
| uncertain | 11,379 |
| no_match | 16,548 |
| errors | 475 |

**Checkpoint Files**:
- `poc/data/reconcile_index.json` - Current offset (small)
- `poc/data/reconcile_results.jsonl` - Results (append-only, 111,604 lines)
- `poc/data/reconcile_checkpoint.json` - Legacy format (30MB)

#### 2. Reverse Matching (Wikidata → DB)
| Category | Collected | Matched | New | Status |
|----------|-----------|---------|-----|--------|
| philosophers | 500 | 377 | 123 | Done |
| rulers | 1,000 | 418 | 582 | Done |
| military | 1,000 | 637 | 363 | Done |
| scientists | 1,000 | 329 | 671 | Done |
| religious | 2,000 | 466 | 1,534 | Done |
| philosophers_ext | 2,000 | 1,433 | 567 | Done |
| rulers_ext | 2,831 | 1,245 | 1,586 | Done |
| **TOTAL** | **10,331** | **4,905** | **5,426** | |

**Scripts**:
- `fetch_wikidata_persons.py` - Wikidata에서 카테고리별 인물 수집
- `apply_reverse_wikidata.py` - 매칭 결과 DB 적용

**Result Files**: `poc/data/wikidata_{category}_matches.json`

---

## Today's Work Plan (2026-01-15)

### Phase 1: Forward Matching 완료 (진행 중)
- [x] Reconcile 작업 재개 (`--resume --limit 50000`)
- [ ] 50k 완료 후 추가 50k 실행 (반복)
- [ ] 전체 285k 완료까지 진행

**Command**:
```bash
python poc/scripts/wikidata_reconcile.py --resume --limit 50000 --batch-size 25 --delay 1.0
```

### Phase 2: Forward 결과 DB 적용
- [ ] reconcile_results.jsonl에서 matched 결과 추출
- [ ] apply 스크립트 수정 (reconcile 포맷 지원)
- [ ] DB에 wikidata_id 적용 (confidence >= 0.8)

**TODO**: `apply_wikidata_matches.py`가 reconcile 결과 포맷 지원하도록 수정 필요

### Phase 3: Reverse 결과 DB 적용
- [ ] `apply_reverse_wikidata.py --dry-run` 실행하여 확인
- [ ] matched 4,905명 → 기존 인물 wikidata_id 업데이트
- [ ] new 5,426명 → 새 인물로 추가 (선택적)

**Command**:
```bash
python poc/scripts/apply_reverse_wikidata.py --dry-run
python poc/scripts/apply_reverse_wikidata.py --min-score 70
```

### Phase 4: 결과 검증
- [ ] DB wikidata_id 보유 인물 수 확인
- [ ] 주요 역사 인물 샘플 검증

---

## Scripts Reference

| Script | Purpose | Input | Output |
|--------|---------|-------|--------|
| `wikidata_reconcile.py` | DB→Wikidata 매칭 | DB persons | reconcile_results.jsonl |
| `wikidata_match_parallel.py` | DB→Wikidata (직접 API) | DB persons | wikidata_checkpoint.json |
| `fetch_wikidata_persons.py` | Wikidata 인물 수집 | - | wikidata_{cat}.json |
| `match_wikidata_to_db.py` | Wikidata→DB 매칭 | wikidata_{cat}.json | wikidata_{cat}_matches.json |
| `apply_wikidata_matches.py` | 매칭 결과 적용 | checkpoint.json | DB update |
| `apply_reverse_wikidata.py` | 역순 매칭 적용 | *_matches.json | DB update/insert |

---

## Architecture

### Forward Pipeline (DB → Wikidata)
```
DB Persons (without wikidata_id)
       │
       ▼
┌──────────────────────────────┐
│  Reconciliation API          │  wikidata.reconci.link
│  - Batch queries (25/req)    │
│  - Name + Lifespan matching  │
└──────────────┬───────────────┘
               │
       ┌───────┴───────┐
       ▼               ▼
   matched         uncertain
   (≥0.8)          (0.5-0.8)
       │               │
       ▼               ▼
   Apply to DB     Manual review
                   or LLM verify
```

### Reverse Pipeline (Wikidata → DB)
```
Wikidata SPARQL Query
  (category + year filter)
       │
       ▼
┌──────────────────────────────┐
│  Local Matching              │
│  - Name fuzzy match          │
│  - Lifespan validation       │
└──────────────┬───────────────┘
               │
       ┌───────┴───────┐
       ▼               ▼
   matched           new
   (existing DB)     (not in DB)
       │               │
       ▼               ▼
   Update          Insert new
   wikidata_id     person record
```

---

## Confidence Thresholds

| Score | Action | Notes |
|-------|--------|-------|
| ≥ 0.95 | Auto-match | Exact name + lifespan match |
| 0.80-0.95 | Auto-match | Strong fuzzy match |
| 0.50-0.80 | Uncertain | Review needed |
| < 0.50 | No match | Skip |

---

## Commands Quick Reference

```bash
# Check current DB status
cd backend && python -c "
from app.db.session import SessionLocal
from app.models.person import Person
db = SessionLocal()
print('Total:', db.query(Person).count())
print('With wikidata:', db.query(Person).filter(Person.wikidata_id.isnot(None)).count())
db.close()
"

# Resume forward matching
python poc/scripts/wikidata_reconcile.py --resume --limit 50000

# Apply reverse matches (dry run)
python poc/scripts/apply_reverse_wikidata.py --dry-run

# Apply reverse matches
python poc/scripts/apply_reverse_wikidata.py --min-score 70
```

---

## Notes

### Rate Limits
- Reconciliation API: ~1 req/sec recommended
- Wikidata SPARQL: 60 req/min

### Checkpoint System
- Forward: JSONL append-only (no memory issues)
- Reverse: Per-category JSON files (already complete)

### Known Issues
1. Legacy checkpoint format (30MB JSON) causes memory issues
2. Some fictional characters in DB get false positives
3. Name variations (Mr., Mrs., titles) reduce match rate
