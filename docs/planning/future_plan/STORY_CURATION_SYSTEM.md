# Story Curation System 설계

> **작성일**: 2026-01-12
> **상태**: 기획
> **의존성**: Story UI 인프라 완료 (StoryModal, StoryGlobe)

---

## 현재 상태 vs 목표

### 현재 구현된 것 (인프라)

| 구분 | 내용 | 상태 |
|------|------|------|
| Backend API | event_connections에서 이벤트 조회 | ✅ |
| Frontend UI | 지도 + 노드 + 컨트롤 | ✅ |
| DB 테이블 | event_connections (person layer) | ✅ |

**문제: 이벤트 데이터만 보여줌. 스토리/내러티브 없음.**

### 구현 안 된 것 (핵심)

| 구분 | 내용 | 상태 |
|------|------|------|
| Story Content | 각 노드의 내러티브 텍스트 | ❌ |
| Curator AI | 스토리 작성하는 AI | ❌ |
| Source Citations | 1차 사료 인용 | ❌ |
| Story DB 테이블 | 작성된 스토리 저장 | ❌ |

---

## 1. Story Content가 뭔가?

### 현재 노드가 보여주는 것
```
노드: 오를레앙 해방
연도: 1429
위치: 오를레앙 (47.90, 1.91)
설명: (events.description에서 가져온 짧은 텍스트)
```

### 목표: 큐레이터가 작성한 스토리
```
노드: 오를레앙 해방
연도: 1429년 4월 29일 - 5월 8일
위치: 오를레앙, 프랑스

[큐레이터 내러티브]
"1429년 4월, 잔 다르크는 4천 명의 병사를 이끌고 오를레앙에 도착했다.
7개월간 잉글랜드군에 포위되어 있던 도시였다. 그녀가 도착한 지 단 9일
만에 포위는 풀렸다. 이 승리는 백년전쟁의 전환점이 되었다."

[원본 출처]
📜 "Le 29 avril, la Pucelle entra dans Orléans..."
   - Journal du Siège d'Orléans (오를레앙 포위전 일지)

[관련 인물]
- 뒤누아 백작 (Jean de Dunois)
- 라 이르 (La Hire)
```

---

## 2. 필요한 DB 테이블

### 2.1 story_contents (스토리 콘텐츠)

```sql
CREATE TABLE story_contents (
    id SERIAL PRIMARY KEY,

    -- 어떤 스토리의 어떤 노드인지
    story_type VARCHAR(20) NOT NULL,  -- 'person', 'place', 'arc'
    subject_id INTEGER NOT NULL,       -- person_id, location_id, or arc_id
    event_id INTEGER REFERENCES events(id),
    node_order INTEGER NOT NULL,

    -- 콘텐츠 (언어별)
    narrative_en TEXT,                 -- 영어 내러티브
    narrative_ko TEXT,                 -- 한국어 내러티브
    narrative_ja TEXT,                 -- 일본어 내러티브

    -- 메타데이터
    persona VARCHAR(20) DEFAULT 'official',  -- 'official', 'mash', 'leonardo'

    -- 생성 정보
    generated_by VARCHAR(50),          -- 'gpt-4o', 'manual', etc.
    generated_at TIMESTAMP DEFAULT NOW(),

    -- 검증
    is_verified BOOLEAN DEFAULT FALSE,
    verified_by VARCHAR(100),
    verified_at TIMESTAMP,

    UNIQUE(story_type, subject_id, event_id, persona)
);
```

### 2.2 story_sources (출처 연결)

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

    display_order INTEGER DEFAULT 0
);
```

### 2.3 story_arcs (아크 정의) - 선택적

```sql
CREATE TABLE story_arcs (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    name_ko VARCHAR(200),
    arc_type VARCHAR(50),              -- 'war', 'philosophy', 'religion', 'art'
    description TEXT,
    start_year INTEGER,
    end_year INTEGER
);
```

---

## 3. Curator AI 시스템

### 3.1 역할

**Curator AI가 하는 일:**
1. 이벤트 데이터를 받아서
2. 1차 사료를 참조하여
3. 페르소나에 맞는 내러티브를 작성

### 3.2 워크플로우

```
[Input]
- event_id: 12345
- event.title: "Siege of Orléans lifted"
- event.description: "Joan of Arc leads French forces..."
- event.year: 1429
- person: Joan of Arc
- persona: "mash"
- language: "ko"

[Curator AI Process]
1. 이벤트 정보 수집
2. 관련 1차 사료 검색 (있으면)
3. 페르소나 프롬프트 적용
4. 내러티브 생성 (200-400자)
5. 출처 인용 포맷팅

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

### 3.3 페르소나 프롬프트 (from JOAN_OF_ARC_SHOWCASE.md)

| 페르소나 | 톤 | 용도 |
|----------|-----|------|
| official | 다큐멘터리/백과사전 | 기본값 |
| mash | 따뜻하고 친근 (해요체) | 친근한 안내 |
| leonardo | 자신감/장난기 (반말) | 재미있는 설명 |

---

## 4. 구현 단계

### Phase A: DB 테이블 생성

- [ ] `story_contents` 테이블 생성
- [ ] `story_sources` 테이블 생성
- [ ] Alembic 마이그레이션

### Phase B: Curator AI 파이프라인

- [ ] `poc/scripts/generate_story_content.py` 생성
- [ ] OpenAI API 연동 (gpt-4o-mini 또는 gpt-4o)
- [ ] 페르소나 프롬프트 구현
- [ ] 배치 생성 로직

### Phase C: 잔 다르크 시범 생성

- [ ] 잔 다르크 11개 노드에 대해 콘텐츠 생성
- [ ] 3개 페르소나 × 3개 언어 = 99개 콘텐츠
- [ ] 1차 사료 연결 (수동)

### Phase D: API 확장

- [ ] `/api/v1/story/person/{id}` 응답에 narrative 포함
- [ ] 페르소나/언어 선택 파라미터 추가

### Phase E: UI 확장

- [ ] StoryModal에 내러티브 표시 영역
- [ ] 출처 인용 표시
- [ ] 페르소나/언어 선택 UI

---

## 5. 비용 추정

### 잔 다르크 1인 기준

| 항목 | 수량 | 토큰 | 비용 |
|------|------|------|------|
| 노드 | 11개 | - | - |
| 페르소나 | 3개 | - | - |
| 언어 | 3개 | - | - |
| **총 콘텐츠** | 99개 | ~50K output | ~$0.50 |

### 전체 인물 (48,373명) 기준

**가정**: 평균 5개 노드, official 페르소나만, 영어만

| 항목 | 계산 |
|------|------|
| 콘텐츠 수 | 48,373 × 5 = ~240K |
| 토큰 | 240K × 500 = 120M output tokens |
| 비용 | gpt-4o-mini: ~$60 |

→ 선택적 생성 필요 (유명 인물만, 요청 시 생성 등)

---

## 6. 대안: On-demand 생성

전체 사전 생성 대신, 사용자가 요청할 때 생성:

```
사용자가 "잔 다르크 Story" 클릭
  ↓
story_contents에 있는지 확인
  ↓
없으면 → Curator AI가 실시간 생성 → DB 저장 → 응답
있으면 → DB에서 반환
```

**장점**: 비용 절감, 실제 필요한 것만 생성
**단점**: 첫 로딩 느림 (5-10초), API 키 필요

---

## 7. 1차 사료 수집 (별도 작업)

### 잔 다르크 관련 사료

| 사료 | 유형 | 접근성 | 우선순위 |
|------|------|--------|----------|
| Procès de condamnation (재판 기록) | 1차 | Archive.org | 높음 |
| Procès en nullité (복권 재판) | 1차 | Archive.org | 높음 |
| Journal du Siège d'Orléans | 1차 | BnF Gallica | 높음 |
| Chronique de la Pucelle | 1차 | 출판본 | 중간 |

### 수집 방법

1. **수동 수집**: 핵심 인용문만 직접 추출
2. **반자동**: URL + 페이지 범위 지정 → 스크래핑
3. **외부 데이터셋**: 이미 디지털화된 사료 활용

---

## 요약

| 구분 | 현재 | 목표 |
|------|------|------|
| 노드 데이터 | DB events에서 조회 | ✅ 완료 |
| 내러티브 | 없음 | Curator AI 생성 |
| 출처 인용 | 없음 | story_sources 테이블 |
| 페르소나 | 프롬프트만 정의 | API/UI 연동 |

**다음 작업**: Phase A (DB 테이블) → Phase B (Curator 파이프라인)
