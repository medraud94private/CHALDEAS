# CHALDEAS V1 Globe Integration Plan

## 목표
NER 추출된 엔티티 데이터를 3D Globe UI와 연계하여, 시공간적 역사 탐색 경험 구현

---

## Phase 2: 위치 데이터 보강

### 2.1 현황 분석
- **Locations**: 34,409개
- **좌표 있음**: ~100개 미만 (추정)
- **좌표 없음**: ~34,000개 이상

### 2.2 Geocoding 전략

#### Option A: 외부 API 활용
| 서비스 | 무료 한도 | 특징 |
|--------|----------|------|
| Nominatim (OSM) | 무제한 (1req/s) | 무료, 역사 지명 부족 |
| GeoNames | 30K/day | 역사 지명 풍부 |
| Google Geocoding | $5/1K | 정확도 높음 |

**권장**: GeoNames + Nominatim 조합
- 비용: ~$0 (무료 API만 사용)
- 예상 매칭률: 60-70%

#### Option B: 역사 지명 데이터셋 활용
- **Pleiades**: 고대 지중해/근동 지명 (35K+ 위치)
- **Getty TGN**: 미술사 관련 지명
- **WHG (World Historical Gazetteer)**: 역사 지명 통합 DB

**권장**: Pleiades + GeoNames 조합

### 2.3 Geocoding 작업 계획

```
[Step 1] 기존 좌표 매핑 (~5%)
- modern_name이 있는 경우 → GeoNames 조회

[Step 2] Pleiades 매칭 (~30%)
- 고대 지명 → Pleiades DB 조회

[Step 3] GeoNames 폴백 (~30%)
- 현대 지명으로 변환 후 조회

[Step 4] 수동 검토 큐 (~35%)
- 매칭 실패 → pending_locations 테이블로 이동
- 관리자 UI에서 수동 매핑
```

### 2.4 필요한 작업
- [ ] `pending_locations` 테이블 생성
- [ ] Pleiades 데이터셋 다운로드 및 임포트
- [ ] Geocoding 스크립트 작성 (`poc/scripts/enrich_locations.py`)
- [ ] 관리자 UI: 미매핑 위치 큐

---

## Phase 3: Globe 마커 시스템

### 3.1 마커 레이어 구조

```
Globe Layers:
├── Base Layer (지구본)
├── Events Layer (사건 마커)
│   ├── Battles (빨강)
│   ├── Treaties (파랑)
│   ├── Discoveries (초록)
│   └── Cultural (보라)
├── Persons Layer (인물 마커)
│   └── birth_location / death_location
├── Polities Layer (정치체 영역)
│   └── 시대별 영토 폴리곤 (선택)
└── Connection Layer (연결선)
    └── 인물 이동, 사건 연쇄
```

### 3.2 마커 데이터 구조

```typescript
interface GlobeMarker {
  id: number
  type: 'event' | 'person' | 'location'
  lat: number
  lng: number
  year: number  // 필터링용
  category: string
  title: string
  description?: string
  relatedEntities: number[]  // 연결된 엔티티 ID
}
```

### 3.3 API 엔드포인트 (신규)

```
GET /api/v1/globe/markers
  ?year_start=-500&year_end=500
  &types=event,person
  &bounds=lat1,lng1,lat2,lng2
  → 시간/공간 필터링된 마커 반환

GET /api/v1/globe/connections/{entity_id}
  → 특정 엔티티와 연결된 다른 엔티티들
```

### 3.4 필요한 작업
- [ ] `globe.py` API 라우터 생성
- [ ] 마커 쿼리 최적화 (공간 인덱스)
- [ ] `GlobeContainer.tsx` 마커 레이어 추가
- [ ] 마커 클릭 → 상세 패널 연동

---

## Phase 4: 타임라인 연동

### 4.1 현재 타임라인
- 연도 표시 (BCE/CE)
- ±10년, ±100년 이동
- 재생/일시정지

### 4.2 개선 사항

#### 4.2.1 이벤트 밀도 표시
```
타임라인 하단에 히트맵 추가:
|████░░░░████████░░░░░████░░░░|
-3000                        2000
(이벤트가 많은 시기 = 진하게)
```

#### 4.2.2 시대 구분 표시
```
|--고대--|---중세---|--근대--|--현대--|
-3000   500      1500    1800   2000
```

#### 4.2.3 Globe-Timeline 동기화
- 타임라인 이동 → Globe 마커 필터링
- 마커 클릭 → 타임라인 해당 연도로 이동

### 4.3 필요한 작업
- [ ] 이벤트 밀도 계산 API
- [ ] 타임라인 히트맵 컴포넌트
- [ ] 시대 구분 오버레이
- [ ] Globe-Timeline 양방향 연동

---

## Phase 5: Historical Chain 생성

### 5.1 Chain 유형

| 유형 | 설명 | 예시 |
|------|------|------|
| **Person Story** | 인물 생애의 사건들 | "알렉산더 대왕의 생애" |
| **Place Story** | 장소의 시대별 역사 | "로마의 역사" |
| **Era Story** | 시대의 주요 사건/인물 | "르네상스 시대" |
| **Causal Chain** | 인과관계 연결 | "로마 멸망의 원인들" |

### 5.2 자동 생성 로직

```python
# Person Story 자동 생성
def generate_person_story(person_id):
    # 1. 인물의 모든 이벤트 조회
    events = get_events_by_person(person_id)

    # 2. 시간순 정렬
    events.sort(key=lambda e: e.date_start)

    # 3. Chain 생성
    chain = HistoricalChain(
        chain_type='person_story',
        focal_person_id=person_id,
        year_start=events[0].date_start,
        year_end=events[-1].date_start
    )

    # 4. Segments 생성
    for i, event in enumerate(events):
        segment = ChainSegment(
            chain_id=chain.id,
            sequence_number=i,
            event_id=event.id,
            transition_type='follows' if i > 0 else None
        )

    return chain
```

### 5.3 Chain 시각화 (Globe)

```
Person Story 시각화:
1. 인물의 이동 경로를 Globe에 선으로 표시
2. 각 사건 위치에 마커
3. 시간순으로 애니메이션 재생 가능

Place Story 시각화:
1. 해당 장소 중심으로 Globe 포커스
2. 시대별 이벤트 마커 표시
3. 타임라인 재생 시 순차적으로 하이라이트
```

### 5.4 필요한 작업
- [ ] Chain 자동 생성 스크립트
- [ ] Chain API 엔드포인트
- [ ] Chain 시각화 컴포넌트
- [ ] Globe 경로 애니메이션

---

## Phase 6: 검색 및 필터링 강화

### 6.1 통합 검색
```
검색창에 "Alexander" 입력:
→ Persons: Alexander the Great, Alexander II, ...
→ Events: Battle of Gaugamela, ...
→ Locations: Alexandria, ...
→ Sources: "The Anabasis of Alexander", ...
```

### 6.2 고급 필터
- 시간 범위: -500 ~ 500
- 지역: Mediterranean, Asia, Europe
- 카테고리: War, Culture, Science
- 확실성: Fact, Probable, Legendary

### 6.3 필요한 작업
- [ ] 통합 검색 API
- [ ] 검색 UI 개선
- [ ] 필터 패널 추가

---

## 구현 우선순위

### Sprint 1: 위치 보강 (1주)
1. Pleiades 데이터 임포트
2. Geocoding 스크립트 작성
3. 좌표 매핑 실행

### Sprint 2: Globe 마커 (1주)
1. Globe 마커 API
2. 마커 레이어 구현
3. 마커 클릭 상호작용

### Sprint 3: 타임라인 연동 (1주)
1. Globe-Timeline 동기화
2. 이벤트 밀도 히트맵
3. 시대 구분 표시

### Sprint 4: Historical Chain (1주)
1. Chain 자동 생성
2. Chain API
3. 기본 시각화

### Sprint 5: 검색 강화 (1주)
1. 통합 검색
2. 고급 필터
3. UI 개선

---

## 기술 스택 추가 예정

| 항목 | 기술 | 용도 |
|------|------|------|
| 공간 인덱스 | PostGIS | 위치 쿼리 최적화 |
| 지명 매칭 | Pleiades API | 고대 지명 → 좌표 |
| 경로 시각화 | Three.js curves | Globe 위 경로 표시 |
| 애니메이션 | GSAP / Framer | 타임라인 재생 |

---

## 예상 결과물

### 사용자 시나리오 1: 인물 탐색
1. 검색창에 "Caesar" 입력
2. Julius Caesar 선택
3. Globe에 Caesar 관련 마커 표시 (생애 경로)
4. 타임라인이 -100 ~ -44 BCE로 조정
5. "Caesar's Life" Historical Chain 자동 생성
6. 클릭하면 상세 패널에서 원문 출처 확인

### 사용자 시나리오 2: 시대 탐색
1. 타임라인에서 "르네상스" 시대 선택
2. Globe에 1400-1600년 유럽 이벤트 표시
3. 인물, 예술작품, 발견 등 카테고리별 필터
4. 특정 마커 클릭 → 관련 Historical Chain 제안

### 사용자 시나리오 3: 장소 탐색
1. Globe에서 "Rome" 클릭
2. "Rome's History" Place Story 표시
3. 타임라인 재생 → 시대별 로마 이벤트 순차 표시
4. 관련 인물, 정치체 연결

---

## 체크포인트

- [ ] CP-3.1: Pleiades 데이터 임포트
- [ ] CP-3.2: Geocoding 스크립트 완성
- [ ] CP-3.3: 위치 좌표 70%+ 매핑
- [ ] CP-4.1: Globe 마커 API
- [ ] CP-4.2: 마커 레이어 구현
- [ ] CP-5.1: Timeline 연동
- [ ] CP-5.2: 이벤트 밀도 표시
- [ ] CP-6.1: Person Story 자동 생성
- [ ] CP-6.2: Chain 시각화
- [ ] CP-7.1: 통합 검색
- [ ] CP-7.2: 고급 필터
