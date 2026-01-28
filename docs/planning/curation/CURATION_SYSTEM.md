# V3 Curation System - 큐레이션 시스템

> **작성일**: 2026-01-16
> **상태**: 설계 완료
> **의존성**: HistoricalUnit 통합, Universe 시스템

---

## 개요

V3 큐레이션 시스템은 **AI가 작성한 내러티브**를 HistoricalUnit 기반으로 제공.

```
┌─────────────────────────────────────────────────────────────┐
│                    Curation System                           │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  HistoricalUnit ──► Curator AI ──► Story Content           │
│       │                │                 │                  │
│       │                │                 ├── Narrative     │
│       │                │                 ├── Sources       │
│       │                └── Persona       └── Translations  │
│       │                    ├── official                    │
│       │                    ├── mash (해요체)               │
│       │                    └── leonardo (반말)             │
│       │                                                    │
│       └── unit_type: person_story / place_story / arc_story│
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Story 유형 (V3)

### 1. Person Story (인물 스토리)

인물의 생애를 지도 위에서 따라가기.

```
┌─ Person Story: 잔 다르크 ─────────────────────────────────┐
│                                                           │
│  ●═══○═══○═══★═══○═══○═══★═══○═══○═══○═══✝             │
│  출생  환시  시농  오를레앙  파테  랭스  파리  체포  화형    │
│  1412      1429   1429    1429  1429  1429  1430  1431   │
│                                                           │
│  각 노드 = HistoricalUnit (unit_type: battle/coronation/etc)│
└───────────────────────────────────────────────────────────┘
```

### 2. Place Story (장소 스토리)

장소의 역사적 변천 (시간순).

```
┌─ Place Story: 로마 ──────────────────────────────────────┐
│                                                          │
│  ●═══○═══○═══○═══○═══○═══○═══○                         │
│ BC753 BC509 BC44  27  313  476  800  현재               │
│ 건국  공화정 카이사르 제정 기독교 서멸망 신성로마         │
│                                                          │
│  지도 고정, 타임라인에서 시대 이동                        │
│  각 노드 = HistoricalUnit (scale: longue_duree/conjuncture)│
└──────────────────────────────────────────────────────────┘
```

### 3. Arc Story (아크 스토리)

사건/흐름의 전개 (전쟁, 사상, 예술 운동).

```
┌─ Arc Story: 백년전쟁 ─────────────────────────────────────┐
│                                                           │
│  여러 장소 + 시간순 전개                                   │
│                                                           │
│  ●═══○═══○═══○═══○═══○═══○═══○                          │
│ 크레시  푸아티에  오를레앙  랭스  파리  카스티용           │
│  1346    1356    1429    1429  1429   1453              │
│                                                           │
│  parent = 백년전쟁 HistoricalUnit (scale: conjuncture)    │
│  각 노드 = 하위 전투들 (scale: evenementielle)             │
└───────────────────────────────────────────────────────────┘
```

---

## 데이터 모델 (V3)

### 1. story_contents (스토리 콘텐츠)

```sql
CREATE TABLE story_contents (
    id SERIAL PRIMARY KEY,

    -- V3: HistoricalUnit 기반
    story_type VARCHAR(20) NOT NULL,  -- 'person', 'place', 'arc'
    subject_id INTEGER NOT NULL,       -- person_id (person story) or unit_id (arc)
    unit_id INTEGER REFERENCES historical_units(id),  -- V3: events → historical_units
    node_order INTEGER NOT NULL,

    -- Universe 지원 (V3)
    universe_id INTEGER REFERENCES universes(id) DEFAULT 1,  -- 1=historical

    -- 콘텐츠 (언어별)
    narrative_en TEXT,
    narrative_ko TEXT,
    narrative_ja TEXT,

    -- 페르소나
    persona VARCHAR(20) DEFAULT 'official',  -- 'official', 'mash', 'leonardo'

    -- 생성 정보
    generated_by VARCHAR(50),          -- 'gpt-4o', 'manual'
    generated_at TIMESTAMP DEFAULT NOW(),

    -- 검증
    is_verified BOOLEAN DEFAULT FALSE,
    verified_by VARCHAR(100),
    verified_at TIMESTAMP,

    UNIQUE(story_type, subject_id, unit_id, persona, universe_id)
);

-- V3: Universe 인덱스
CREATE INDEX idx_story_universe ON story_contents(universe_id);
```

### 2. story_sources (출처 연결)

```sql
CREATE TABLE story_sources (
    id SERIAL PRIMARY KEY,
    story_content_id INTEGER REFERENCES story_contents(id),

    -- 출처 정보
    source_type VARCHAR(20),           -- 'primary', 'secondary'
    title VARCHAR(500),
    author VARCHAR(200),
    year INTEGER,
    excerpt TEXT,                      -- 원문 발췌
    excerpt_translation TEXT,          -- 번역
    url VARCHAR(500),
    reliability VARCHAR(20),           -- 'high', 'medium', 'low'

    -- V3: Wikidata 연결
    wikidata_id VARCHAR(20),           -- Q-number (책/문서의 QID)

    display_order INTEGER DEFAULT 0
);
```

---

## Curator AI 페르소나

### Official (공식)

객관적이고 중립적인 다큐멘터리 스타일.

```
프롬프트:
당신은 CHALDEAS의 큐레이터 AI로, 다큐멘터리 스타일의 역사 서술을 제공합니다.

스타일:
- 중립적이고 다큐멘터리 같은 톤
- 사실과 맥락 중심
- 학술적이면서도 접근하기 쉬운
- 항상 1차 사료 인용

예시:
"잔 다르크(1412-1431)는 백년전쟁 중 프랑스군을 여러 차례 승리로
이끈 프랑스 농민 출신 소녀였다."
```

### Mash (마슈)

따뜻하고 친근한 말투 (해요체). FGO 마슈 키리에라이트 모티브.

```
프롬프트:
당신은 CHALDEAS의 큐레이터 AI "마슈"입니다.
사용자와 함께 역사를 탐험하는 따뜻한 안내자예요.

스타일:
- 따뜻하고 친근하면서도 정중한 말투 (해요체)
- 함께 탐험하는 동료 느낌
- 배려심 있고 응원하는 톤

예시:
"잔 다르크에 대해 알고 싶으신 거군요! 제가 안내해 드릴게요.
그녀가 백년전쟁의 흐름을 바꿨을 때, 겨우 열일곱 살이었어요."
```

### Leonardo (레오나르도)

자신감 넘치고 장난기 있는 천재 (반말). FGO 레오나르도 다 빈치 모티브.

```
프롬프트:
당신은 CHALDEAS의 큐레이터 AI "레오나르도"입니다.
역사에 대한 지식을 나누는 것을 좋아하는 만능 천재죠.

스타일:
- 자신감 넘치고 약간의 자기 과시 ("이 천재가 설명해줄게!")
- 친근하고 장난기 있는 말투 (반말)
- 역사적 사실은 정확하게, 하지만 재미있게 전달

예시:
"오, 잔 다르크에 대해 알고 싶다고? 좋은 선택이야!
천재인 내가 또 다른 천재를 설명하는 건 언제나 즐거운 일이지."
```

---

## Universe 통합 (V3)

### FGO 페르소나 처리

FGO 캐릭터 기반 페르소나(마슈, 레오나르도)는 **역사적 내러티브**를 제공.
FGO 세계관 내 스토리는 별도 Universe에서 관리.

```
┌─────────────────────────────────────────────────────────┐
│  Historical Universe (universe_id: 1)                    │
├─────────────────────────────────────────────────────────┤
│  잔 다르크 Person Story                                  │
│  ├── official 페르소나 내러티브                          │
│  ├── mash 페르소나 내러티브 (해요체)                     │
│  └── leonardo 페르소나 내러티브 (반말)                   │
│                                                         │
│  → 모두 역사적 사실 서술, 말투만 다름                    │
└─────────────────────────────────────────────────────────┘
                         │
                         │ canonical_id 참조
                         ▼
┌─────────────────────────────────────────────────────────┐
│  FGO Universe (universe_id: 2)                           │
├─────────────────────────────────────────────────────────┤
│  FGO 잔 다르크 (Ruler) Story                             │
│  ├── FGO 설정/배경 스토리                                │
│  ├── 특이점 관련 스토리                                  │
│  └── 게임 내 이벤트 등                                   │
│                                                         │
│  → FGO 세계관 내 픽션 스토리                             │
└─────────────────────────────────────────────────────────┘
```

### 크로스 유니버스 표시

```typescript
// 역사 인물 상세에서 FGO 버전 참조
{
  "canonical": {
    "id": 1,
    "name": "Jeanne d'Arc",
    "universe": "historical",
    "story_personas": ["official", "mash", "leonardo"]
  },
  "variants": [
    {
      "id": 1001,
      "name": "Jeanne d'Arc (Ruler)",
      "universe": "fgo",
      "has_story": true
    }
  ]
}
```

---

## API 설계 (V3)

### Person Story API

```
GET /api/v3/story/person/{person_id}
    ?universe=historical (default)
    ?persona=official (default) | mash | leonardo
    ?language=en (default) | ko | ja

Response:
{
  "person": {
    "id": 1,
    "name": "Jeanne d'Arc",
    "universe": "historical"
  },
  "nodes": [
    {
      "order": 0,
      "unit": {
        "id": 501,
        "name": "Birth of Joan of Arc",
        "unit_type": "birth",
        "date_start": "1412-01-06",
        "date_precision": "day"
      },
      "location": {
        "id": 101,
        "name": "Domrémy",
        "lat": 48.44,
        "lng": 5.67,
        "hierarchy": ["Lorraine", "France"]
      },
      "narrative": "로렌 지방의 작은 마을 도미레미에서...",
      "sources": [
        {
          "title": "Procès en nullité",
          "excerpt": "Jeanne naquit à Domrémy...",
          "excerpt_translation": "잔은 도미레미에서 태어났다...",
          "wikidata_id": "Q123456"
        }
      ]
    }
  ],
  "map_view": {
    "center": { "lat": 48.5, "lng": 2.5 },
    "zoom": 6
  }
}
```

### Arc Story API (V3 신규)

```
GET /api/v3/story/arc/{unit_id}
    ?persona=official
    ?language=ko

Response:
{
  "arc": {
    "id": 100,
    "name": "Hundred Years' War",
    "unit_type": "war",
    "scale": "conjuncture",
    "date_start": "1337",
    "date_end": "1453"
  },
  "nodes": [
    {
      "order": 0,
      "unit": {
        "id": 501,
        "name": "Battle of Crécy",
        "parent_id": 100
      },
      ...
    }
  ]
}
```

---

## Curator AI 파이프라인

### 워크플로우

```
[Input]
├── unit_id: 501 (HistoricalUnit)
├── persona: "mash"
├── language: "ko"
└── universe: "historical"

[Process]
1. HistoricalUnit 정보 수집 (V3 API)
   ├── 날짜 (precision 포함)
   ├── 위치 (hierarchy 포함)
   └── 관련 인물
2. Wikidata에서 추가 정보 fetch
3. 관련 1차 사료 검색
4. 페르소나 프롬프트 적용
5. 내러티브 생성 (200-400자)
6. 출처 인용 포맷팅

[Output]
{
  "narrative": "오를레앙에 도착했을 때, 도시는 이미 7개월째 포위당하고 있었어요...",
  "sources": [
    {
      "title": "Journal du Siège d'Orléans",
      "excerpt": "Le 29 avril...",
      "translation": "4월 29일..."
    }
  ]
}
```

### 생성 전략

| 전략 | 설명 | 용도 |
|------|------|------|
| **Pre-generation** | 주요 인물 사전 생성 | 유명 인물 100명 |
| **On-demand** | 사용자 요청 시 생성 | 나머지 인물 |
| **Batch** | 배치 처리 | 새로운 HistoricalUnit 추가 시 |

---

## 구현 순서

### Phase A: DB 테이블 (Phase B 이후)

- [ ] `story_contents` 테이블 (V3 호환)
- [ ] `story_sources` 테이블 (Wikidata 연결)
- [ ] Alembic 마이그레이션

### Phase B: Curator AI 파이프라인

- [ ] `backend/app/core/curator/` 모듈 생성
- [ ] 페르소나 프롬프트 구현
- [ ] HistoricalUnit 기반 컨텍스트 수집
- [ ] OpenAI API 연동 (gpt-4o-mini)

### Phase C: 잔 다르크 시범 생성

- [ ] 잔 다르크 11개 노드 콘텐츠 생성
- [ ] 3개 페르소나 × 3개 언어 = 99개 콘텐츠
- [ ] 1차 사료 연결

### Phase D: API 확장

- [ ] `/api/v3/story/person/{id}` 구현
- [ ] `/api/v3/story/arc/{id}` 구현
- [ ] 페르소나/언어 선택 파라미터

### Phase E: UI 확장

- [ ] StoryModal V3 업데이트 (HistoricalUnit 기반)
- [ ] 페르소나 선택 UI
- [ ] 출처 인용 표시

---

## 비용 추정

### 잔 다르크 1인 기준

| 항목 | 수량 | 비용 |
|------|------|------|
| 노드 | 11개 | - |
| 페르소나 | 3개 | - |
| 언어 | 3개 | - |
| **총 콘텐츠** | 99개 | ~$0.50 |

### 전체 확장 시

| 항목 | 계산 |
|------|------|
| 주요 인물 100명 | 100 × 5 nodes × 3 personas = 1,500 콘텐츠 |
| 비용 | ~$7.50 (gpt-4o-mini) |
| On-demand 나머지 | 요청 시 생성 |

---

## UI 설계 (요약)

### 풀스크린 재생 모드

```
┌─────────────────────────────────────────────────────────────────┐
│ [×]  JOAN OF ARC - Person Story              [페르소나: 마슈 ▼] │
├─────────────────────────────────────────────────────────────────┤
│                                                     │           │
│       [풀스크린 지도 - 프랑스 전체]                 │  진행:    │
│                                                     │  1/11    │
│       ✝ 루앙 ══════════════ ○ 콩피에뉴             │           │
│           ║                      ║                  │ ───────── │
│           ║                  ★ 랭스                 │           │
│           ○ 파리 ─────────╱                         │  [⏸]     │
│           ║                                        │  [◀][▶]  │
│      ★ 오를레앙                    ● 도미레미      │  속도:1x │
│           ║                           │             │           │
│        ○ 시농 ───────────────────────              │           │
│                                                     │           │
├─────────────────────────────────────────────────────┴───────────┤
│  ● 도미레미 출생 (1412년 1월 6일)                                │
│  ───────────────────────────────────────────────────────────── │
│  [마슈 내러티브]                                                │
│  "로렌 지방의 작은 마을 도미레미에서 잔 다르크가 태어났어요.     │
│   아버지 자크 다르크는 평범한 농부였는데, 이 아이가 나중에       │
│   프랑스의 운명을 바꾸게 될 줄은 아무도 몰랐겠죠."              │
│                                                                 │
│  📜 "Jeanne naquit à Domrémy..." - 복권 재판 기록 (1456)       │
│                                                                 │
│  [◀◀ 처음] [◀ 이전]  ●○○★○○★○○○✝  [다음 ▶] [▶▶ 자동재생] │
└─────────────────────────────────────────────────────────────────┘
```

---

## 성공 지표

| 지표 | 목표 |
|------|------|
| 잔 다르크 콘텐츠 완성 | 11노드 × 3페르소나 × 3언어 |
| 1차 사료 연결률 | 80%+ |
| 생성 비용 | < $1/인물 |
| UI 반응성 | 60fps 애니메이션 |
| 확장 적용 | 나폴레옹, 살라딘 등 |
