# CHALDEAS 빌드 브리핑 - 2026-01-07

---

## 현재 버전 상태

| 버전 | 상태 | 설명 |
|------|------|------|
| **V0** | 운영 중 | 기존 레거시 (변경 없음) |
| **V1** | 개발 중 | Historical Chain 기반 신규 구조 |
| **V2** | 기획 중 | Open Curation + 사용자 데이터 기여 |

---

## V1 개발 진행 현황

### Phase 1: 데이터 모델 확장 ✅ 완료

| 체크포인트 | 내용 | 상태 |
|-----------|------|------|
| CP-1.1 | V1 디렉토리 구조 생성 | ✅ |
| CP-1.2 | Period 모델 생성 | ✅ |
| CP-1.3 | Location 이중 계층 확장 | ✅ |
| CP-1.4 | Event 필드 확장 (Braudel 시간척도) | ✅ |
| CP-1.5 | Alembic 마이그레이션 | ✅ |

### Phase 2: 관계형 스키마 확장 ✅ 완료

| 체크포인트 | 내용 | 상태 |
|-----------|------|------|
| CP-2.1 | Polity 모델 (정치단체) | ✅ |
| CP-2.2 | HistoricalChain, ChainSegment 모델 | ✅ |
| CP-2.3 | TextMention, EntityAlias 모델 | ✅ |
| CP-2.4 | Person, Source 모델 확장 | ✅ |
| CP-2.5 | associations.py 확장 | ✅ |
| CP-2.6 | Alembic 마이그레이션 실행 | ✅ |
| CP-2.7 | 인덱스 최적화 | ✅ |

---

## 주요 변경사항 (이번 빌드)

### 1. DB 스키마 (10개 신규 테이블)

```
V1 신규 테이블:
├── periods          - 시대/기간
├── polities         - 정치 단체 (제국, 왕국 등)
├── polity_relationships
├── person_polities
├── historical_chains - 역사의 고리 (4가지 타입)
├── chain_segments
├── chain_entity_roles
├── text_mentions    - NER 출처 추적
├── entity_aliases   - 중복 제거용
└── import_batches   - 배치 임포트 추적
```

### 2. 기존 테이블 확장

| 테이블 | 추가된 필드 |
|--------|------------|
| `persons` | canonical_id, role, era, floruit_*, certainty, embedding, primary_polity_id 등 15개 |
| `sources` | document_id, document_path, title, original_year, language |
| `events` | temporal_scale, period_id, certainty |
| `person_relationships` | strength, valid_from/until, confidence |
| `event_relationships` | certainty, evidence_type, confidence |

### 3. Historical Chain 4가지 유형

1. **Person Story**: 인물 생애의 시간순 사건
2. **Place Story**: 한 장소의 시대별 역사
3. **Era Story**: 시대의 인물, 장소, 사건 종합
4. **Causal Chain**: 인과관계로 연결된 사건

### 4. NER 파이프라인

- **1차**: spaCy en_core_web_lg (무료, 로컬)
- **2차**: Ollama Qwen3 8B (무료, 로컬) 또는 OpenAI gpt-5-nano (폴백)
- **Batch 처리**: OpenAI Batch API 지원

### 5. 성능 인덱스

```sql
idx_events_temporal_range  -- Historical Chain 시간 범위 쿼리
idx_events_period_date     -- 시대별 이벤트 조회
idx_event_persons_person   -- Person Story 쿼리
idx_event_locations_location -- Place Story 쿼리
idx_event_rel_causal       -- Causal Chain 쿼리
```

---

## 이론적 기반

| 이론 | 적용 내용 |
|------|----------|
| CIDOC-CRM | Event 중심 온톨로지 (ISO 21127:2014) |
| Braudel/Annales | 3단계 시간 척도 (evenementielle, conjuncture, longue_duree) |
| Prosopography | 인물 네트워크 분석 (Factoid Model) |
| Historical GIS | 이중 계층 구조, 시공간 표현 |

---

## PoC 현황

| 항목 | 상태 |
|------|------|
| 백엔드 (FastAPI + SQLite) | ✅ 동작 |
| NER 파이프라인 (spaCy + Ollama) | ✅ 동작 |
| Chain 생성 API | ✅ 구현 |
| Batch NER 처리 | ✅ 5.65M 엔티티 추출 완료 |

---

## 오늘 추가된 기획 (V2 비전)

### 1. Open Curation (`docs/planning/v2/OPEN_CURATION_VISION.md`)

- 큐레이션 레이어 오픈소스화
- 위키 스타일 하이퍼링크 연결
- 해석 충돌 정책 (병렬 표시, 출처 명시)
- 삭제/수정 권한 정책 (Immutable Core 유지)

### 2. User Data Contribution (`docs/planning/v2/USER_DATA_CONTRIBUTION.md`)

- 사용자 자료 업로드 기능
- 데이터 품질 등급 (Tier 1-4)
- 충돌 해결 정책
- 동일 라이센스 조건 적용

### 3. Agentic RAG 참고 (`docs/reference/AGENTIC_RAG_REVIEW.md`)

- Hierarchical Indexing 패턴
- Self-Correction Loop
- SHEBA 쿼리 파이프라인 개선 참고용

---

## 다음 작업 (V1 계속)

- [ ] 벡터 검색 인덱스 생성 (pgvector IVFFlat)
- [ ] 시드 데이터 임포트 (periods.json)
- [ ] NER 배치 데이터 → DB 임포트 파이프라인
- [ ] Chain 생성 API V1 통합

---

## 파일 변경 요약

```
수정: 18개 파일 (+995 lines, -115 lines)
신규: 80+ 파일 (POC 스크립트, 배치 데이터, V2 기획 등)
```

### 주요 수정 파일

| 파일 | 변경 내용 |
|------|----------|
| `backend/app/models/person.py` | V1 필드 15개 추가 |
| `backend/app/models/source.py` | V1 필드 5개 추가 |
| `backend/app/models/associations.py` | 관계 테이블 확장 |
| `docs/reference/DATABASE.md` | V1 스키마 문서화 (+261 lines) |
| `docs/roadmap/V1_WORKPLAN.md` | 체크포인트 업데이트 |

---

## 실행 방법

```bash
# Backend
cd backend
pip install -r requirements.txt
python -m alembic upgrade head
uvicorn app.main:app --reload --port 8100

# Frontend
cd frontend
npm install
npm run dev -- --port 5200

# PoC NER 테스트
cd poc
python scripts/test_ollama.py
```

---

## 비용 현황

| 항목 | 비용 |
|------|------|
| NER (spaCy + Ollama) | $0 (무료) |
| NER 폴백 (OpenAI gpt-5-nano) | ~$0.001/1K tokens |
| 임베딩 (text-embedding-3-small) | ~$0.00002/1K tokens |
| **월간 예상** | **~$7/월** |
