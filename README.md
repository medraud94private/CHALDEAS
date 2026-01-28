# CHALDEAS

> **Fate/Grand Order 2부 종장 클리어 기념 - 되찾은 범인류사를 탐험하세요**
>
> **FGO Part 2 Final Chapter Clear Celebration - Explore the Pan-Human History We Fought to Restore**
>
> **FGO 第2部終章クリア記念 - 取り戻した汎人類史を探検しよう**

Fate/Grand Order의 칼데아 시스템에서 영감받은 **3D 지구본 역사 탐색 플랫폼**

![Version](https://img.shields.io/badge/version-0.7.0-blue)
![License](https://img.shields.io/badge/license-MIT-green)

---

## What is CHALDEAS?

BCE 3000년부터 현재까지, 인류 역사의 모든 순간을 3D 지구본 위에서 탐험하세요.

| 데이터 | 수량 |
|--------|------|
| **역사적 사건** | 10,000+ |
| **인물** | 57,000+ |
| **장소** | 34,000+ |
| **Historical Chains** | 50,000+ connections |

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

### Core Features
- **3D Globe Visualization**: Interactive globe with react-globe.gl (3 styles: Default, HOLO, Night)
- **Timeline Travel**: BCE 3000 ~ Present with timelapse animation
- **Historical Chain**: Event connections by Person/Location/Causal relationships
- **Semantic Search**: AI-powered search with autocomplete across events, persons, locations
- **Multi-language**: Korean / English / Japanese with Wikipedia-sourced descriptions
- **Settings Page**: Language preference, display options, data source attribution

### Recent Features (v0.5~v0.7)
- **PWA Support**: Offline access, installable app
- **Virtual Scrolling**: Smooth performance with 1000+ events
- **Event Clustering**: Zoom-level based marker grouping
- **Heatmap Visualization**: Event density overlay on globe
- **Timelapse Animation**: Animated time travel with speed control
- **Bookmarks**: Save and manage favorite events
- **Advanced Filters**: Layer type, year range, connection strength
- **Arc Particle Animation**: Dynamic connection visualization

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

| Source | Data | License |
|--------|------|---------|
| **Wikipedia** | Multilingual descriptions (en/ko/ja) | CC BY-SA 4.0 |
| **Wikidata** | Entity linking, coordinates | CC0 1.0 |
| **Pleiades** | Ancient Mediterranean locations (34k+) | CC BY 3.0 |
| **Project Gutenberg** | Historical book extractions | Public Domain |
| **DBpedia** | Events with coordinates | CC BY-SA 3.0 |
| **World History Encyclopedia** | Historical articles | Fair Use |
| **Stanford Encyclopedia** | Philosophy | Fair Use |

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

---

## Changelog

### v0.7.0 (2026-01-28) - Multilingual & Settings

#### Multilingual Support
- **3-Language Descriptions**: Korean (ko), Japanese (ja), English (en) for all entities
- **Wikipedia Integration**: Fetch descriptions from language-specific Wikipedia via Wikidata
- **Source Attribution**: Track and display data sources with Wikipedia/AI badges
- **CC BY-SA License**: Proper attribution for Wikipedia-sourced content

#### Settings Page
| Feature | Description |
|---------|-------------|
| Language Preference | Auto/English/Korean/Japanese selection |
| Display Settings | Hide entities without descriptions |
| Globe Style | Default/Holographic/Night themes |
| SHEBA API Key | Optional API key management |
| License Info | Wikipedia CC BY-SA attribution |

#### New Components
- `SettingsPage`: Full settings modal with all preferences
- `SourceBadge`: Wikipedia/AI source attribution badge
- `settingsStore`: Zustand store with localStorage persistence

---

### v0.6.0 (2026-01-19) - Relationship Strength & DB Management

#### Relationship System
- **Strength Scoring**: 1-5 scale relationship strength
- **Confidence Tracking**: Evidence-based confidence scores
- **Auto-updating**: Relationships strengthen with more evidence

#### Database
- **Compact DB Management**: Optimized storage and queries
- **DB Sync Automation**: Local ↔ Cloud sync scripts

---

### v0.5.0 (2025-01-11) - UI/UX Major Update

#### Performance Improvements
- **Code Splitting**: Lazy loading for Three.js/Globe (~1.4MB → ~327KB initial)
- **PWA Support**: Service Worker with Workbox caching
- **Virtual Scrolling**: @tanstack/react-virtual for 500+ event lists

#### New Components
| Component | Description |
|-----------|-------------|
| `FilterPanel` | Advanced filters (layer type, year range, strength) |
| `SearchAutocomplete` | Debounced search with categorized results |
| `TimelineBar` | Enhanced timeline with era markers and density heatmap |
| `TimelapseControls` | Animated time travel with play/pause/speed |
| `VirtualEventList` | Virtualized sidebar event list |

#### Globe Enhancements
| Feature | Description |
|---------|-------------|
| Event Clustering | Zoom-level based marker grouping |
| Heatmap Layer | Event density visualization (hexBin) |
| Arc Animation | Dynamic particle-like effects based on connection strength |
| Clustering Toggle | On/off control for marker clustering |

#### Data Features
- **Bookmarks**: LocalStorage-persisted favorites with Zustand
- **Historical Chain API**: Globe arcs and connection statistics

#### Files Added
```
frontend/src/components/
├── filters/FilterPanel.tsx, FilterPanel.css
├── search/SearchAutocomplete.tsx, SearchAutocomplete.css
├── timeline/TimelineBar.tsx, TimelapseControls.tsx
├── sidebar/VirtualEventList.tsx, VirtualEventList.css
├── globe/GlobeHeatmap.css
└── chain/ChainPanel.tsx

frontend/src/store/
└── bookmarkStore.ts

backend/app/api/v1_new/
├── globe.py (markers, arcs API)
└── chains.py (Historical Chain API)
```

---

### v0.4.0 - Historical Chain System
- Event connection system (Person/Location/Causal layers)
- Globe arc visualization
- Chain statistics API

### v0.3.0 - Entity Detail Views
- Person detail view with biography, events, relationships
- Location detail view with history, events
- Entity pool explorer (pre-curation)

### v0.2.0 - Core Features
- 3D Globe with multiple styles (Default, HOLO, Night)
- Timeline controls with era navigation
- SHEBA chat interface
- Category filtering

### v0.1.0 - Initial Release
- Basic 3D globe visualization
- Event markers and detail panel
- Backend API foundation
