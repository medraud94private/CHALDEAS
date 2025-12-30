# API Reference

## 구현 상태: 완료

Base URL: `/api/v1`

## Events API

### GET /events
이벤트 목록 조회 (지구본 마커용)

**Query Parameters:**
| 파라미터 | 타입 | 설명 |
|----------|------|------|
| year_start | int | 시작 연도 (음수 = BCE) |
| year_end | int | 종료 연도 |
| category_id | int | 카테고리 필터 |
| importance_min | int | 최소 중요도 (1-5) |
| limit | int | 결과 수 (기본 100) |
| offset | int | 오프셋 |

**Response:**
```json
{
  "items": [
    {
      "id": 1,
      "title": "Battle of Marathon",
      "title_ko": "마라톤 전투",
      "date_start": -490,
      "date_display": "490 BCE",
      "importance": 5,
      "category": { "id": 1, "name": "Military", "color": "#EF4444" },
      "location": { "id": 10, "name": "Marathon", "latitude": 38.15, "longitude": 23.96 }
    }
  ],
  "total": 100
}
```

### GET /events/{id}
이벤트 상세 조회

### GET /events/slug/{slug}
슬러그로 이벤트 조회

---

## Persons API

### GET /persons
인물 목록 조회

### GET /persons/{id}
인물 상세 조회

### GET /persons/{id}/events
인물 관련 이벤트 조회

---

## Locations API

### GET /locations
장소 목록 조회

### GET /locations/{id}
장소 상세 조회

### GET /locations/{id}/events
장소에서 발생한 이벤트 조회

---

## Search API

### GET /search
통합 검색

**Query Parameters:**
| 파라미터 | 타입 | 설명 |
|----------|------|------|
| q | string | 검색어 (필수) |
| type | string | event/person/location/all |
| limit | int | 결과 수 |

**Response:**
```json
{
  "query": "socrates",
  "results": {
    "events": [...],
    "persons": [...],
    "locations": [...]
  }
}
```

### GET /search/date-location
시간+장소 관측 (SHEBA)

**Query Parameters:**
| 파라미터 | 타입 | 설명 |
|----------|------|------|
| year | int | 연도 (필수) |
| latitude | float | 위도 |
| longitude | float | 경도 |
| radius_km | float | 반경 (기본 100km) |

**Response:**
```json
{
  "year": -490,
  "year_display": "490 BCE",
  "events": [...],
  "persons_active": [...]
}
```

---

## Chat API (SHEBA)

### POST /chat
자연어 질의

**Request:**
```json
{
  "query": "What happened at Marathon in 490 BCE?",
  "context": {
    "year": -490,
    "location": "Marathon"
  },
  "language": "en"
}
```

**Response:**
```json
{
  "answer": "The Battle of Marathon was...",
  "sources": [
    {
      "source": { "name": "Herodotus, Histories", "url": "..." },
      "relevance": 0.95
    }
  ],
  "confidence": 0.85,
  "related_events": [...],
  "suggested_queries": [
    "Who was Miltiades?",
    "What caused the Persian Wars?"
  ]
}
```

---

## Categories API

### GET /categories
카테고리 트리 조회

**Response:**
```json
{
  "items": [
    {
      "id": 1,
      "name": "History",
      "name_ko": "역사",
      "color": "#3B82F6",
      "children": [
        { "id": 2, "name": "Military", "color": "#EF4444" }
      ]
    }
  ]
}
```

---

## 구현 파일

- `backend/app/api/v1/events.py`
- `backend/app/api/v1/persons.py`
- `backend/app/api/v1/locations.py`
- `backend/app/api/v1/search.py`
- `backend/app/api/v1/chat.py`
- `backend/app/api/v1/categories.py`
