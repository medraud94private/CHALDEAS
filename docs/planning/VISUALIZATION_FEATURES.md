# Visualization Features Plan

## User Vision

> "특정 사건을 검색하면 그 시대, 그 위치를 보여주면서 설명이 나옴. 연관 사건의 장소나 시간을 선으로 보여주고, 각 인물별로 시대별 이동이나 어떤 사건에 엮였는지를 일대기로 볼 수 있게. 위키피디아처럼, 그걸 지도로 보는 거야. 그 시대의 굵직한 사건은 연관 없어도 상시 표시."

## Core Features

### 1. Event Search & Display (기본 구조)

```
┌─────────────────────────────────────────────────────────────────────┐
│                     Event Search & Display                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  User searches: "마라톤 전투"                                        │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                     3D Globe View                           │    │
│  │                                                             │    │
│  │              Timeline: -490 BCE                             │    │
│  │                    ┌──────┐                                 │    │
│  │                    │ 🔴  │ ← Marathon                       │    │
│  │                    └──────┘                                 │    │
│  │         Greece ━━━━┛                                        │    │
│  │                                                             │    │
│  │  Camera animates to location, zooms in                      │    │
│  │                                                             │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                   Wiki Panel (Side)                         │    │
│  │                                                             │    │
│  │  # Battle of Marathon (마라톤 전투)                          │    │
│  │  490 BCE | Marathon, Greece                                 │    │
│  │                                                             │    │
│  │  The Battle of Marathon took place in 490 BC...             │    │
│  │                                                             │    │
│  │  📚 Sources:                                                │    │
│  │  - Herodotus, Histories Book 6 (Perseus)                   │    │
│  │  - Plutarch, Life of Miltiades                             │    │
│  │                                                             │    │
│  │  🔗 Related Events: [Greco-Persian Wars] [Battle of...]    │    │
│  │  👤 Key Figures: [Miltiades] [Darius I] [Pheidippides]    │    │
│  │                                                             │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### 2. Related Events Connection (연관 사건 연결선)

```
┌─────────────────────────────────────────────────────────────────────┐
│                   Related Events Visualization                       │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  When viewing "Battle of Marathon":                                  │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                                                             │    │
│  │       Sardis                                                │    │
│  │         🔵 ─────────────────────┐                          │    │
│  │        (Ionian Revolt start)    │                          │    │
│  │                                 │  Causal chain            │    │
│  │                                 │  (dashed line)           │    │
│  │                                 ▼                          │    │
│  │                              Marathon                       │    │
│  │       Persepolis              🔴 ◄────┐                    │    │
│  │          🟡 ─────────────────────────┘                     │    │
│  │        (Persian Empire HQ)         │                       │    │
│  │                                    │                       │    │
│  │                                    ▼                       │    │
│  │                               Salamis                       │    │
│  │                                  🔵                        │    │
│  │                             (Future event)                  │    │
│  │                                                             │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  Line Types:                                                        │
│  ━━━━  Causal relationship (direct cause/effect)                   │
│  ─ ─ ─  Temporal sequence (same war/period)                        │
│  ······  Thematic connection (similar type)                         │
│                                                                      │
│  Animation: Lines draw progressively, following time order          │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### 3. Person Biography View (인물 일대기)

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Person Biography View                             │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Selected: Alexander the Great (알렉산드로스 대왕)                    │
│  356 BCE - 323 BCE                                                  │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                  Life Journey on Globe                      │    │
│  │                                                             │    │
│  │    1. Pella (Birth) ─────────────────┐                     │    │
│  │         🟢                            │                     │    │
│  │                                       ▼                     │    │
│  │    2. Thebes ─────────────────────────┼──┐                 │    │
│  │         🔵                            │  │                 │    │
│  │                                       │  │                 │    │
│  │    3. Granicus ──────────────────────┼──┼──┐              │    │
│  │         ⚔️                            │  │  │              │    │
│  │                                       │  │  │              │    │
│  │    4. Issus ─────────────────────────┼──┼──┼──┐           │    │
│  │         ⚔️                            │  │  │  │           │    │
│  │                                       ▼  ▼  ▼  ▼           │    │
│  │    ... → Persepolis → Bactria → India → Babylon (Death)   │    │
│  │                                              🔴            │    │
│  │                                                             │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                    Timeline Strip                           │    │
│  │                                                             │    │
│  │  356 BCE         336        331        326        323 BCE   │    │
│  │    │              │          │          │          │        │    │
│  │    🟢─────────────⚔️─────────⚔️─────────⚔️──────────🔴       │    │
│  │  Birth        Becomes    Gaugamela   India     Death        │    │
│  │              King                   Campaign                │    │
│  │                                                             │    │
│  │  [Click any point to view that event/location]              │    │
│  │                                                             │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  Play Button: [▶️ Animate Journey] - Globe flies through locations   │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### 4. Era Background Events (시대 배경 상시 표시)

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Era Background Events                             │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Timeline set to: -490 BCE (마라톤 전투 시기)                        │
│                                                                      │
│  Regardless of search focus, always show major events:              │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                                                             │    │
│  │     🟡 Rome (Republic era)                                  │    │
│  │         └ "Roman Republic established ~509 BCE"             │    │
│  │                                                             │    │
│  │     🟡 Persepolis                                           │    │
│  │         └ "Achaemenid Empire at peak"                       │    │
│  │                                                             │    │
│  │     🟡 Babylon                                              │    │
│  │         └ "Under Persian control"                           │    │
│  │                                                             │    │
│  │     🟡 Chang'an                                             │    │
│  │         └ "Spring and Autumn Period (China)"                │    │
│  │                                                             │    │
│  │     🔴 Marathon (FOCUSED)                                   │    │
│  │         └ "Battle of Marathon"                              │    │
│  │                                                             │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  Event Importance Levels:                                           │
│  ★★★★★  Always visible (world-changing events)                     │
│  ★★★★☆  Visible when era ±50 years                                 │
│  ★★★☆☆  Visible when era ±20 years                                 │
│  ★★☆☆☆  Visible when directly related                              │
│  ★☆☆☆☆  Visible only when searched                                 │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

## UI Components

### Globe Markers

```typescript
interface MapMarker {
  id: string;
  type: 'event' | 'person_birth' | 'person_death' | 'location';
  latitude: number;
  longitude: number;

  // Visual properties
  color: string;          // Category-based
  size: number;           // Importance-based
  icon?: string;          // Optional icon
  pulsing?: boolean;      // For focused item

  // Display
  label: string;
  tooltip: string;

  // Filtering
  year: number;           // BCE as negative
  importance: 1 | 2 | 3 | 4 | 5;
  isBackground: boolean;  // Always show for era
}
```

### Connection Lines (Arcs)

```typescript
interface ConnectionArc {
  id: string;
  from: { lat: number; lng: number };
  to: { lat: number; lng: number };

  // Visual
  type: 'causal' | 'temporal' | 'thematic' | 'journey';
  color: string;
  dashArray?: string;     // For dashed lines
  animated?: boolean;     // Moving dots along arc

  // Data
  fromEventId: string;
  toEventId: string;
  label?: string;
}
```

### Wiki Panel States

```typescript
type WikiPanelContent =
  | { type: 'event'; event: Event; sources: Source[]; related: Event[] }
  | { type: 'person'; person: Person; events: Event[]; journey: Location[] }
  | { type: 'location'; location: Location; events: Event[]; persons: Person[] }
  | { type: 'search_results'; results: SearchResult[] };
```

## Interaction Flows

### 1. Event Search Flow

```
User types "마라톤" in search
         │
         ▼
SHEBA parses query, identifies "Battle of Marathon"
         │
         ▼
Globe animates to Marathon, Greece
Timeline slides to -490 BCE
         │
         ▼
Wiki panel shows event details with sources (LAPLACE)
         │
         ▼
Related events appear as markers with connection lines
Background events for -490 BCE become visible
```

### 2. Person View Flow

```
User clicks person name "소크라테스"
         │
         ▼
Globe shows Athens (primary location)
Timeline shows lifespan (-470 to -399)
         │
         ▼
Wiki panel shows biography
Life events listed chronologically
         │
         ▼
[View Journey] button available
Click → Globe animates through life locations
```

### 3. Era Exploration Flow

```
User drags timeline to -500 BCE
         │
         ▼
Globe updates to show major events of era
Markers fade in/out based on importance threshold
         │
         ▼
User can click any marker to focus
Connection lines appear for related events
```

## Data Requirements

### Event Relationships Table

```sql
CREATE TABLE event_relationships (
    id SERIAL PRIMARY KEY,
    event_from_id INTEGER REFERENCES events(id),
    event_to_id INTEGER REFERENCES events(id),
    relationship_type VARCHAR(50),  -- causal, temporal, thematic
    strength INTEGER DEFAULT 3,     -- 1-5
    description TEXT
);
```

### Person Events Table

```sql
CREATE TABLE person_events (
    id SERIAL PRIMARY KEY,
    person_id INTEGER REFERENCES persons(id),
    event_id INTEGER REFERENCES events(id),
    role VARCHAR(100),              -- commander, participant, victim
    location_id INTEGER REFERENCES locations(id),
    year INTEGER
);
```

### Person Locations Table (Journey)

```sql
CREATE TABLE person_locations (
    id SERIAL PRIMARY KEY,
    person_id INTEGER REFERENCES persons(id),
    location_id INTEGER REFERENCES locations(id),
    year_start INTEGER,
    year_end INTEGER,
    location_type VARCHAR(50),      -- birth, death, residence, visit
    notes TEXT
);
```

## Implementation Priority

### Phase 1: Basic Display
- [x] Globe with markers
- [x] Timeline slider
- [ ] Event search → focus on location
- [ ] Wiki panel with event details

### Phase 2: Connections
- [ ] Related events markers
- [ ] Connection lines (arcs)
- [ ] Causal relationship visualization

### Phase 3: Person View
- [ ] Person biography panel
- [ ] Life journey visualization
- [ ] Animated journey playback

### Phase 4: Era Context
- [ ] Background events by era
- [ ] Importance-based visibility
- [ ] Era summary overlay

## Performance Considerations

1. **Marker Clustering**: Group nearby markers at low zoom
2. **Level of Detail**: Show fewer events when zoomed out
3. **Arc Simplification**: Reduce arc segments at distance
4. **Virtual List**: Wiki panel uses virtualized scrolling
5. **Data Pagination**: Load events in chunks by era/region
