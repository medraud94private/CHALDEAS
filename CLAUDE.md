# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CHALDEAS is a world-centric historical knowledge system inspired by Fate/Grand Order's Chaldea. It provides an immersive 3D globe interface for exploring interconnected history, philosophy, science, mythology, and biographical information across time (BCE 3000 to present).

**Core Principle**: "World State is explicit and immutable" - Intelligence proposes but never executes.

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

### Docker Compose (full stack)
```bash
docker-compose up -d           # Start all services
docker-compose down            # Stop services
```

### Data Pipeline
```bash
python data/scripts/collect_all.py      # Collect from sources
python data/scripts/transform_data.py   # Transform to common format
python backend/app/scripts/index_events.py   # Index to vector DB
```

### Database
```bash
docker-compose exec db psql -U chaldeas -d chaldeas
# Or native: psql -U chaldeas -d chaldeas -h localhost -p 5433
```

## Fixed Ports (Hardcoded)
- Frontend: 5200 (dev) / 5173 (docker)
- Backend API: 8100
- PostgreSQL: 5433 (external) / 5432 (internal)
- API Docs: http://localhost:8100/docs

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
- OpenAI/Anthropic (LLM integration via LangChain)

### Database
- PostgreSQL 16 with pgvector extension
- BCE dates stored as negative integers (-490 = 490 BCE)

## Key API Endpoints

```
GET  /api/v1/events                    # List events (filters: year_start, year_end, category_id)
GET  /api/v1/persons                   # List historical figures
GET  /api/v1/locations                 # List places
GET  /api/v1/search?q=...&type=all     # Unified search
POST /api/v1/chat/agent                # Agent-based intelligent query (SHEBA + LOGOS)
```

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
```

## Important Patterns

1. **Immutability**: All world state changes must go through Layer 6 (PATCH/APPLY)
2. **Source Attribution**: Every fact must trace back to a source
3. **BCE Handling**: Use negative years for BCE dates in all calculations
4. **Agent Responses**: Return structured data with confidence scores and follow-up suggestions
5. **Multilingual**: Support `name_ko` fields for Korean translations

## Documentation

- `docs/implemented/ARCHITECTURE.md` - Full 7-layer design
- `docs/implemented/API.md` - Complete API reference
- `docs/implemented/DATABASE.md` - Schema and relationships
- `docs/guides/SETUP.md` - Development environment setup
- `docs/DEPLOYMENT.md` - GCP Cloud Run deployment
