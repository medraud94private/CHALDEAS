# Phase 7: Historical Chain - 다층 방향성 이벤트 그래프

**작성일**: 2026-01-10
**최종 수정**: 2026-01-11
**상태**: ✅ 구현 완료

---

## 1. 핵심 개념

### 1.1 Historical Chain이란?

이벤트들이 서로 연결되어 형성하는 **다층 방향성 그래프(Multi-layer Directed Graph)**.

- 스토리/글 생성이 아님
- 소스(사료)가 이벤트를 연결
- 인물/장소/인과 등 다양한 레이어
- 시간 흐름에 따른 방향성 존재

### 1.2 관련 연구

| 연구/표준 | 핵심 개념 | 참고 |
|---------|---------|------|
| **CIDOC-CRM** | Event-centric 온톨로지, ISO 표준 | 81 classes, 160 properties |
| **Temporal KG** | 시간 축 포함 지식그래프 (ICEWS, GDELT) | Semantic vs Event-centric |
| **PLEASING** | Historical + Global 인코더, 가중치 게이팅 | 적응형 가중치 메커니즘 |
| **VisKonnect** | 이벤트 공유를 통한 인물 연결 | VIS 2021 |

---

## 2. 방향성 규칙

### 2.1 시간 기반 방향성

**핵심 원칙**: 후대 사건은 전대 사건에 영향을 줄 수 없다.

```
[일방향] A(1800) → B(1850)
  - A가 B에 영향/원인 가능
  - B가 A에 영향 불가능

[양방향] A(1800) ↔ B(1805)
  - 동시대 또는 근접 시대 (±10년)
  - 상호 영향 가능

[무방향] A(1800) — B(1803)
  - 같은 큰 사건의 일부 (part_of)
  - 시간 관계 아닌 구조적 관계
```

### 2.2 Edge Direction 결정 로직

```python
def determine_direction(event_a, event_b, connection_type):
    time_diff = event_b.year - event_a.year

    if connection_type == 'part_of':
        return 'undirected'  # 같은 사건의 일부

    if abs(time_diff) <= 10:
        return 'bidirectional'  # 동시대, 상호영향 가능

    if time_diff > 10:
        return 'forward'  # A → B (A가 먼저)

    if time_diff < -10:
        return 'backward'  # B → A (B가 먼저)
```

### 2.3 Connection Type별 방향성

| Connection Type | 방향성 | 설명 |
|----------------|-------|------|
| `causes` | 일방향 (→) | A가 B의 원인 |
| `leads_to` | 일방향 (→) | A가 B로 이어짐 |
| `follows` | 일방향 (→) | A 다음에 B |
| `influences` | 시간 기반 | 동시대면 양방향 가능 |
| `part_of` | 무방향 (—) | 같은 큰 사건의 일부 |
| `concurrent` | 양방향 (↔) | 동시 발생 |
| `related` | 시간 기반 | 맥락에 따라 결정 |

---

## 3. 다층 그래프 구조

### 3.1 레이어 정의

```
[Layer 1: Person Chain] ─────────────────────────────
  Shakespeare의 인생: Event A → Event B → Event C
                                   ↓ (만남)
                             Anne Hathaway 체인과 교차

[Layer 2: Location Chain] ───────────────────────────
  London의 역사: Event D → Event E → Event F
                    ↑
              Shakespeare Event B와 교차

[Layer 3: Causal Chain] ─────────────────────────────
  프랑스혁명 체인: 삼부회 → 바스티유 → 왕정폐지 → 나폴레옹
                              ↓ (영향)
                         아이티 혁명 체인

[Layer 4: Thematic Chain] ───────────────────────────
  르네상스: (약한 연결, 큐레이션으로 강화)
```

### 3.2 레이어 간 교차

```
Event X는 여러 레이어에 동시 존재 가능:

Shakespeare's marriage (1582)
  ├─ [Person Layer] Shakespeare 체인의 일부
  ├─ [Person Layer] Anne Hathaway 체인의 일부
  ├─ [Location Layer] Stratford 체인의 일부
  └─ [Thematic Layer] Tudor era 체인의 일부

→ 교차점이 많을수록 해당 이벤트의 중요도 ↑
```

---

## 4. 연결 강도 (Connection Strength)

### 4.1 강도 계산 공식

```python
import math

def calculate_strength(connection):
    # 기본 강도 (연결 유형별)
    base = BASE_STRENGTH[connection.layer_type]

    # 소스 기반 강화 (비선형 - 많을수록 급격히 증가)
    source_factor = calculate_source_factor(connection.source_count)

    # 시간 근접성 (50년 이내)
    temporal_factor = max(0, (50 - connection.time_distance) * 0.02)

    # 큐레이션 승인 보너스
    curation_bonus = 5.0 if connection.curated_approved else 0

    # 교차점 보너스 (여러 레이어에서 연결)
    intersection_bonus = (connection.layer_count - 1) * 2.0

    return base + source_factor + temporal_factor + curation_bonus + intersection_bonus


def calculate_source_factor(source_count):
    """
    소스 수에 따른 비선형 강화
    - 초기: 곱셈 효과
    - 후기: 더 급격한 증가

    공식: n * (1 + ln(n))^1.5
    """
    if source_count <= 0:
        return 0

    n = source_count
    return n * math.pow(1 + math.log(n), 1.5)
```

### 4.1.1 소스 강화 곡선

| 소스 수 | 강화 값 | 설명 |
|--------|--------|------|
| 1 | 1.0 | 기본 |
| 2 | 3.7 | 거의 4배 |
| 3 | 6.9 | 7배 |
| 5 | 14.0 | 14배 |
| 10 | 38.0 | 38배 |
| 20 | 100.0 | 100배 |
| 50 | 340.0 | 압도적 |

```
강화값
  │
340├                                    ●
   │
100├                          ●
   │
 38├                 ●
 14├         ●
  7├     ●
  4├  ●
  1├●
   └──────────────────────────────────── 소스 수
     1   3   5      10        20       50
```

→ **5개 이상 소스면 person 체인(10.0)보다 강해짐**

### 4.2 레이어별 기본 강도

| Layer Type | Base Strength | 이유 |
|-----------|---------------|------|
| `person` | **10.0** | 인물의 인생 = 가장 확실한 연결 |
| `location` | **5.0** | 같은 장소의 역사 |
| `causal` | **1.0** | 소스 언급으로 강화 필요 |
| `thematic` | **0.5** | 약함, 큐레이션으로 승격 |

### 4.3 강도 분류

| 강도 범위 | 분류 | 처리 |
|----------|------|------|
| < 3.0 | 약함 | unverified 유지, 추가 신호 탐색 |
| 3.0 - 10.0 | 중간 | auto_verified, LLM 검증 대기 |
| 10.0 - 30.0 | 강함 | LLM 검증 → connection_type 분류 |
| > 30.0 | 매우 강함 | 자동 승인 (다수 소스 확인) |

**예시**:
| 케이스 | Base | Source Factor | Total | 분류 |
|-------|------|---------------|-------|------|
| Person 체인 (소스 1개) | 10.0 | 1.0 | 11.0 | 강함 |
| Causal (소스 2개) | 1.0 | 3.7 | 4.7 | 중간 |
| Causal (소스 5개) | 1.0 | 14.0 | 15.0 | 강함 |
| Causal (소스 10개) | 1.0 | 38.0 | 39.0 | **매우 강함** |

---

## 5. 데이터 구조

### 5.1 event_connections 테이블

```sql
CREATE TABLE event_connections (
    id SERIAL PRIMARY KEY,

    -- 연결된 이벤트 쌍
    event_a_id INTEGER REFERENCES events(id),
    event_b_id INTEGER REFERENCES events(id),

    -- 방향성
    direction VARCHAR(20) NOT NULL,  -- 'forward', 'backward', 'bidirectional', 'undirected'

    -- 레이어 정보
    layer_type VARCHAR(20) NOT NULL,  -- 'person', 'location', 'causal', 'thematic'
    layer_entity_id INTEGER,           -- person_id, location_id, etc. (NULL for causal/thematic)

    -- 연결 유형
    connection_type VARCHAR(50),       -- causes, follows, part_of, etc.

    -- 강도
    strength_score FLOAT DEFAULT 0,
    source_count INTEGER DEFAULT 0,
    time_distance INTEGER,             -- 연도 차이 (절대값)

    -- 검증 상태
    verification_status VARCHAR(20) DEFAULT 'unverified',
    verified_by VARCHAR(50),
    verified_at TIMESTAMP,

    -- 큐레이션
    curated_status VARCHAR(20),        -- approved, rejected, pending
    curated_by INTEGER,
    curated_at TIMESTAMP,
    curation_note TEXT,

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    -- 복합 유니크: 같은 레이어에서 같은 이벤트 쌍
    UNIQUE(event_a_id, event_b_id, layer_type)
);

CREATE INDEX idx_conn_direction ON event_connections(direction);
CREATE INDEX idx_conn_layer ON event_connections(layer_type, layer_entity_id);
CREATE INDEX idx_conn_strength ON event_connections(strength_score DESC);
```

### 5.2 connection_sources 테이블

```sql
CREATE TABLE connection_sources (
    id SERIAL PRIMARY KEY,
    connection_id INTEGER REFERENCES event_connections(id),
    source_id INTEGER REFERENCES sources(id),

    mention_context TEXT,              -- 연결을 언급하는 문맥
    proximity_in_text INTEGER,         -- 텍스트 내 거리

    created_at TIMESTAMP DEFAULT NOW()
);
```

---

## 6. 구현 단계

### CP-7.1: 테이블 생성 및 Person/Location 체인 추출
- [ ] 마이그레이션 생성 (event_connections, connection_sources)
- [ ] Person 체인 추출: 같은 person_id 연결된 이벤트들
- [ ] Location 체인 추출: 같은 location_id 연결된 이벤트들
- [ ] 방향성 계산 (시간 순서 기반)

### CP-7.2: 소스 기반 Causal 체인 추출
- [ ] text_mentions에서 같은 소스가 언급하는 이벤트 쌍 추출
- [ ] source_count 집계
- [ ] connection_sources에 증거 저장

### CP-7.3: 강도 계산 및 자동 검증
- [ ] 강도 계산 로직 구현
- [ ] 임계값 기반 자동 검증
- [ ] 강도 분포 분석

### CP-7.4: LLM 연결 유형 분류
- [ ] 강한 연결 (strength >= 5.0) 대상 LLM 분류
- [ ] connection_type 결정
- [ ] 파일럿 테스트 (100개)

### CP-7.5: API 구현
- [ ] GET /api/v1/chains/event/{id}/connections
- [ ] GET /api/v1/chains/traverse
- [ ] GET /api/v1/chains/person/{id}
- [ ] GET /api/v1/chains/location/{id}

---

## 7. 비용 예상

| 단계 | 작업 | LLM | 비용 |
|-----|------|-----|------|
| 7.1 | Person/Location 체인 추출 | No | $0 |
| 7.2 | Causal 체인 추출 | No | $0 |
| 7.3 | 강도 계산 | No | $0 |
| 7.4 | LLM 연결 분류 (~5,000개) | Yes | ~$5-10 |
| 7.5 | API 구현 | No | $0 |
| **Total** | | | **~$5-10** |

---

## 8. 예시

### 8.1 Shakespeare의 Person Chain

```
[Layer: person, entity: Shakespeare]

Event: Birth (1564, Stratford)
    ↓ forward
Event: Marriage to Anne (1582, Stratford)
    ↓ forward                ↔ bidirectional (동시대)
Event: Arrives London (1586)      Anne's events...
    ↓ forward
Event: Globe Theatre (1599, London)
    ↓ forward
Event: First Folio (1623, London)  ← 사후, 하지만 그의 체인

Direction: 모두 forward (시간순)
Strength: 10.0 (person base) + 교차점 보너스
```

### 8.2 Causal Chain 예시

```
[Layer: causal]

French Revolution (1789, Paris)
    ↓ causes (strength: 8.5)
    │   └─ 12개 소스가 인과관계 언급
Haitian Revolution (1791, Haiti)
    ↓ leads_to (strength: 6.2)
    │   └─ 7개 소스
Latin American Independence movements (1810+)

Direction: 모두 forward (시간순 + 인과)
```

---

## 9. 참고 자료

- [CIDOC-CRM](https://en.wikipedia.org/wiki/CIDOC_Conceptual_Reference_Model) - ISO 21127:2014
- [VisKonnect (VIS 2021)](https://arxiv.org/abs/2109.09380) - Event-based historical figure connections
- [TKG Survey](https://www.sciencedirect.com/science/article/abs/pii/S0950705124010888) - Temporal Knowledge Graph models
- [PLEASING](https://www.sciencedirect.com/science/article/abs/pii/S0893608024004404) - Adaptive weight mechanism
- [SeaLiT Ontology](https://dl.acm.org/doi/full/10.1145/3586080) - CIDOC-CRM 해양사 적용

---

## 10. 구현 결과 (2026-01-11)

### 10.1 데이터 현황

```
Event Connections: 113,830개
├── person:   36,905개 (기본 강도 10.0)
├── location: 20,442개 (기본 강도 5.0)
└── causal:   56,483개 (소스 기반 강화)

검증 상태:
├── auto_verified:  71,969개 (63%)
├── llm_verified:      737개 (0.6%)
└── unverified:     41,124개 (36%)

Causal 연결 분류 (strength >= 10):
├── related:    381개 (37%)
├── concurrent: 261개 (25%)
├── follows:    210개 (20%)
├── part_of:    113개 (11%)
├── leads_to:    62개 (6%)
└── causes:       2개 (0.2%)
```

### 10.2 API 엔드포인트

| Method | Endpoint | 설명 |
|--------|----------|------|
| GET | `/api/v1/chains/` | 연결 목록 (필터링) |
| GET | `/api/v1/chains/stats` | 통계 |
| GET | `/api/v1/chains/{id}` | 단일 연결 |
| POST | `/api/v1/chains/` | 연결 생성 |
| PUT | `/api/v1/chains/{id}` | 연결 수정 |
| DELETE | `/api/v1/chains/{id}` | 연결 삭제 |
| GET | `/api/v1/chains/event/{id}/connections` | 이벤트별 연결 |
| GET | `/api/v1/chains/person/{id}` | 인물 체인 |
| GET | `/api/v1/chains/location/{id}` | 장소 체인 |
| GET | `/api/v1/chains/traverse` | 그래프 탐색 |

### 10.3 비용

| 항목 | 비용 |
|-----|------|
| 체인 추출 (로컬) | $0 |
| 강도 계산 (로컬) | $0 |
| LLM 분류 (1,029개) | $0.85 |
| **총계** | **$0.85** |

### 10.4 생성된 파일

```
backend/alembic/versions/003_event_connections.py
backend/app/api/v1_new/chains.py
poc/scripts/build_event_chains.py
poc/scripts/classify_connections.py
```

---

## 11. 향후 개선

- [ ] 미분류 Causal 연결 55,454개 처리 (strength < 10)
- [ ] Thematic 레이어 추가
- [ ] 그래프 시각화 UI
- [ ] 큐레이션 워크플로우
