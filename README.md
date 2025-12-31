# CHALDEAS

> **Fate/Grand Order 2부 종장 클리어 기념 - 되찾은 범인류사를 탐험하세요**
>
> **FGO Part 2 Final Chapter Clear Celebration - Explore the Pan-Human History We Fought to Restore**
>
> **FGO 第2部終章クリア記念 - 取り戻した汎人類史を探検しよう**

Fate/Grand Order의 칼데아 시스템에서 영감받은 **3D 지구본 역사 탐색 플랫폼**

---

## What is CHALDEAS?

BCE 3000년부터 현재까지, 인류 역사의 모든 순간을 3D 지구본 위에서 탐험하세요.

| 데이터 | 수량 |
|--------|------|
| **역사적 사건** | 10,000+ |
| **인물** | 57,000+ |
| **장소** | 34,000+ |

---

## Core Systems (FGO-Inspired)

| System | FGO Reference | Role |
|--------|---------------|------|
| **CHALDEAS** | Earth Simulator | World State - 3D Globe Visualization |
| **SHEBA** | Near-Future Lens | Query Processing, Vector Search |
| **LAPLACE** | Heroic Spirit Records | History Records, Source Attribution |
| **LOGOS** | Logos | LLM-based Response Generator |

---

## Features

- **3D Globe Visualization**: Interactive globe with react-globe.gl
- **Timeline Travel**: BCE 3000 ~ Present
- **Event Markers**: Historical events with detailed information
- **Category Filters**: War, Politics, Religion, Philosophy, Science, Culture
- **Semantic Search**: AI-powered search across events, persons, locations
- **Multi-language**: Korean / English / Japanese (coming soon)

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | React 18 + TypeScript + Vite |
| 3D Globe | react-globe.gl (Three.js) |
| State | Zustand |
| Backend | Python 3.12 + FastAPI |
| Database | PostgreSQL + pgvector |
| AI | OpenAI Embeddings + RAG |

---

## Quick Start

### Requirements

- Node.js 20+
- Python 3.12+
- PostgreSQL 16+

### Installation

```bash
# Clone
git clone https://github.com/medraud94private/CHALDEAS.git
cd CHALDEAS

# Backend
cd backend
python -m venv venv
venv\Scripts\activate  # Windows
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8100

# Frontend (new terminal)
cd frontend
npm install
npm run dev -- --port 5200
```

### Access

| Service | URL |
|---------|-----|
| Frontend | http://localhost:5200 |
| Backend API | http://localhost:8100 |
| API Docs | http://localhost:8100/docs |

---

## Data Sources

| Source | Data | Status |
|--------|------|--------|
| **Pleiades** | Ancient Mediterranean locations | 34,000+ |
| **Wikidata** | Historical events | 8,000+ |
| **DBpedia** | Events with coordinates | 1,500+ |
| **World History Encyclopedia** | Historical articles | 200+ |
| **Stanford Encyclopedia** | Philosophy | 200+ |
| **Theoi** | Greek Mythology | 200+ |

---

## License

MIT License

---

## Credits

- [Fate/Grand Order](https://fate-go.jp/) - Inspiration
- [react-globe.gl](https://github.com/vasturiano/react-globe.gl) - 3D Globe
- [Pleiades](https://pleiades.stoa.org/) - Ancient Geography Database

---

> *"Even if the future is uncertain, the history we've reclaimed is real."*
>
> *"未来が不確かでも、取り戻した歴史は確かなものだ。"*
>
> *"미래가 불확실해도, 되찾은 역사는 확실한 것이다."*
