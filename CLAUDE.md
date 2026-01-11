# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CHALDEAS is a world-centric historical knowledge system inspired by Fate/Grand Order's Chaldea. It provides an immersive 3D globe interface for exploring interconnected history, philosophy, science, mythology, and biographical information across time (BCE 3000 to present).

**Core Philosophy**: "모든 역사는 **누가(Person)** **어디서(Location)** **언제(Time)** **무엇을(Event)** 했는가로 결정된다."

**Core Principle**: "World State is explicit and immutable" - Intelligence proposes but never executes.

---

## Version System

| 버전 | 설명 | 상태 | 경로 |
|-----|------|------|------|
| **V0** | 레거시 구조 (기존) | 운영 중 | `backend/app/models/`, `backend/app/api/v1/` |
| **V1** | Historical Chain 기반 신규 구조 | 개발 중 | `backend/app/models/v1/`, `backend/app/api/v1_new/` |

### V1 핵심 개념: Historical Chain (역사의 고리)

4가지 큐레이션 유형:
- **Person Story**: 인물의 생애와 주요 사건
- **Place Story**: 장소의 역사적 변천
- **Era Story**: 시대의 인물, 장소, 사건 종합
- **Causal Chain**: 인과관계로 연결된 사건 흐름

### V1 개발 원칙

1. **V0 영향 없음**: 기존 서버/API 유지, 별도 경로에서 개발
2. **체크포인트 작업**: `docs/planning/V1_WORKPLAN.md` 참조
3. **작업 로그**: `docs/logs/V1_WORKLOG.md`에 진행상황 기록
4. **완성 후 전환**: V1이 V0 기능 100% 커버 시 전환

---

## AI Models

### 사용 모델

| 모델 | 용도 | 비용 |
|-----|------|------|
| `gpt-5-nano` | NER 검증, 체인 생성 (기본) | ~$0.001/1K tokens |
| `gpt-5.1-chat-latest` | 복잡한 체인 (폴백) | ~$0.01/1K tokens |
| `spaCy en_core_web_lg` | 1차 NER 추출 | 무료 (로컬) |
| `text-embedding-3-small` | 벡터 검색 | ~$0.00002/1K tokens |

### 비용 예산

- **초기 구축**: ~$47 (일회성)
- **월간 운영**: ~$7/월
- 상세: `docs/planning/COST_ESTIMATION.md`

---

## Common Commands

### Frontend (from `frontend/`)
```bash
npm run dev -- --port 5200    # Dev server (MUST use port 5200)
npm run build                  # Production build
npm run lint                   # ESLint checks
```

### Backend (from `backend/`)
```bash
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8100    # Dev server (MUST use port 8100)
```

### Database (Native PostgreSQL)
```bash
# 현재 네이티브 PostgreSQL 사용 (포트 5432)
psql -U chaldeas -d chaldeas -h localhost -p 5432

# Alembic 마이그레이션
cd backend
python -m alembic upgrade head
python -m alembic current  # 현재 버전 확인
```

### Data Pipeline
```bash
python data/scripts/collect_all.py      # Collect from sources
python data/scripts/transform_data.py   # Transform to common format
python poc/scripts/import_to_v1_db.py   # NER 데이터 DB 임포트
```

## Fixed Ports (Hardcoded)
- Frontend: 5200 (dev)
- Backend API: 8100
- **PostgreSQL: 5432** (네이티브, Docker 미사용)
- API Docs: http://localhost:8100/docs

> **주의**: DATABASE_URL은 항상 `localhost:5432` 사용. Docker compose의 5433 포트는 더 이상 사용하지 않음.

---

## Architecture: 7-Layer World-Centric Model

```
Layer 7: EXPLAIN (LAPLACE)     - Interpretation, causation tracking, source attribution
Layer 6: PATCH / APPLY         - Sole path for state modification
Layer 5: EFFECT RUNTIME        - Pure functions without side effects
Layer 4: ACTION                - Compute action availability
Layer 3: PROJECTION (SHEBA)    - Read-only view generation, query observation
Layer 2: SNAPSHOT              - Immutable state snapshot
Layer 1: SCHEMA                - World structure definition (CHALDEAS)
```

### Named Subsystems (FGO-Inspired)

| System | Role | Location |
|--------|------|----------|
| **CHALDEAS** | World state, immutable snapshots | `backend/app/core/chaldeas/` |
| **SHEBA** | Query observation, intent detection, vector search | `backend/app/core/sheba/` |
| **LOGOS** | LLM-based response proposer (GPT-5-nano) | `backend/app/core/logos/` |
| **PAPERMOON** | Proposal verification, fact-checking | `backend/app/core/papermoon/` |
| **LAPLACE** | Explanation, source attribution | `backend/app/core/laplace/` |
| **TRISMEGISTUS** | System orchestrator | `backend/app/core/trismegistus/` |

### Data Flow
```
User Query → CHALDEAS (state) → SHEBA (observe) → LOGOS (propose) → PAPERMOON (verify) → LAPLACE (explain) → Response
```

---

## Tech Stack

### Frontend
- React 18 + TypeScript 5.3 + Vite 5.0
- react-globe.gl (Three.js-based 3D globe)
- Zustand (state management)
- Tailwind CSS 3.4

### Backend
- Python 3.12 + FastAPI 0.109
- SQLAlchemy 2.0 + Alembic (migrations)
- pgvector (PostgreSQL vector search)
- OpenAI (LLM integration)

### Database
- PostgreSQL 16 with pgvector extension
- BCE dates stored as negative integers (-490 = 490 BCE)

---

## Key API Endpoints

### V0 (현재 운영)
```
GET  /api/v1/events                    # List events
GET  /api/v1/persons                   # List historical figures
GET  /api/v1/locations                 # List places
GET  /api/v1/search?q=...&type=all     # Unified search
POST /api/v1/chat/agent                # Agent-based intelligent query
```

### V1 (개발 중)
```
POST /api/v1/curation/chain            # 역사의 고리 생성/조회
GET  /api/v1/curation/chain/{id}       # 체인 상세 조회
GET  /api/v1/periods                   # 시대 목록
```

---

## Frontend State Stores (Zustand)

- `globeStore`: Selected event, viewport, markers
- `timelineStore`: Current year, playback state, animation speed

## Environment Variables

Required in `.env`:
```
POSTGRES_USER=chaldeas
POSTGRES_PASSWORD=chaldeas_dev
POSTGRES_DB=chaldeas
OPENAI_API_KEY=sk-...
VITE_API_URL=http://localhost:8100

# V1 Model Settings
NER_PRIMARY_MODEL=gpt-5-nano
NER_FALLBACK_MODEL=gpt-5.1-chat-latest
CHAIN_PRIMARY_MODEL=gpt-5-nano
```

---

## Important Patterns

1. **Immutability**: All world state changes must go through Layer 6 (PATCH/APPLY)
2. **Source Attribution**: Every fact must trace back to a source
3. **BCE Handling**: Use negative years for BCE dates in all calculations
4. **Agent Responses**: Return structured data with confidence scores and follow-up suggestions
5. **Multilingual**: Support `name_ko` fields for Korean translations
6. **Braudel's Temporal Scale**: evenementielle (단기) / conjuncture (중기) / longue_duree (장기)

---

## Documentation

### 구현 완료 (Implemented)
- `docs/implemented/ARCHITECTURE.md` - Full 7-layer design
- `docs/implemented/API.md` - Complete API reference
- `docs/implemented/DATABASE.md` - Schema and relationships
- `docs/guides/SETUP.md` - Development environment setup
- `docs/DEPLOYMENT.md` - GCP Cloud Run deployment

### V1 계획 (Planning)
- `docs/planning/METHODOLOGY.md` - 역사학 방법론 (CIDOC-CRM, Annales 학파 등)
- `docs/planning/HISTORICAL_CHAIN_CONCEPT.md` - 역사의 고리 컨셉 설계
- `docs/planning/REDESIGN_PLAN.md` - V1 재설계 상세 계획
- `docs/planning/COST_ESTIMATION.md` - AI 비용 산정
- `docs/planning/MODELS.md` - 사용 AI 모델 목록
- `docs/planning/V1_WORKPLAN.md` - 체크포인트별 작업 계획

### 작업 로그
- `docs/logs/V1_WORKLOG.md` - V1 개발 진행 로그

---

## Development Workflow

### 작업 체크리스트 규칙 (필수!)

**Claude Code는 반드시 작업 시작 전 체크리스트를 작성해야 함:**

1. **TodoWrite 도구 사용**: 모든 비단순 작업에서 TodoWrite로 체크리스트 생성
2. **작업 시작 전 계획**: 무엇을 할지 먼저 목록화
3. **진행 상태 업데이트**: 작업 중 `in_progress` → 완료 시 `completed`
4. **작은 단위로 분할**: 큰 작업은 작은 체크포인트로 나누기

```
예시:
[ ] Globe API 생성
[ ] 라우터 등록
[ ] API 테스트
[ ] 프론트엔드 연동
```

### V1 작업 시

1. **체크포인트 확인**: `docs/planning/V1_WORKPLAN.md`에서 다음 CP 확인
2. **작업 시작**: 해당 CP의 [ ] 체크박스를 [x]로 변경하며 진행
3. **로그 기록**: `docs/logs/V1_WORKLOG.md`에 작업 내용 기록
4. **테스트**: 각 CP 완료 시 관련 테스트 실행
5. **커밋**: CP 단위로 커밋 (예: `feat(v1): CP-1.2 Period 모델 생성`)

### 커밋 메시지 형식

```
feat(v1): CP-X.X 작업 내용
fix(v0): 버그 수정 내용
docs: 문서 업데이트
```
