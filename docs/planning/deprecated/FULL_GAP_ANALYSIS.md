# CHALDEAS 전체 Gap 분석

> 궁극적 목표 달성까지 부족한 것 전부

## 궁극적 목표

### 비전
```
"3D 글로브에서 시간과 공간을 탐색하며 역사를 배운다"
"모든 역사는 누가(Person) 어디서(Location) 언제(Time) 무엇을(Event) 했는가"
"FGO 서번트의 실제 역사를 탐구한다"
```

### 핵심 기능 (완성 시)
1. **글로브 탐색**: 지도에서 시대별 사건/인물 확인
2. **타임라인**: 시간 슬라이더로 역사 흐름 탐색
3. **인물 스토리**: "나폴레옹의 생애" 자동 생성
4. **인과관계**: "프랑스 혁명 → 나폴레옹 집권 → 워털루" 체인
5. **소스 추적**: "이 정보는 어디서 왔나?"
6. **FGO 연결**: "잔 다르크 서번트 → 실제 역사"

---

## 현재 상태 vs 필요한 것

### Layer 1: 데이터 (가장 심각)

| 항목 | 현재 상태 | 필요한 것 | Gap |
|------|----------|----------|-----|
| **Persons** | 286K (65% QID 없음) | 깨끗한 QID 기반 | 🔴 전면 재구축 |
| **Locations** | 40K (대부분 좌표 없음) | 좌표 + QID | 🔴 보강 필요 |
| **Events** | 46K (연도 불명확) | 정확한 연도 + 위치 | 🔴 보강 필요 |
| **Relations** | 불신뢰 | 검증된 관계 | 🔴 재구축 |
| **Sources** | 88K (연결 안 됨) | 엔티티와 연결 | 🔴 재구축 |
| **Text Mentions** | 거의 없음 | 출처 추적용 | 🔴 새로 구축 |

**결론**: 데이터 레이어 전면 재구축 필요

---

### Layer 2: 데이터 파이프라인

| 항목 | 현재 상태 | 필요한 것 | Gap |
|------|----------|----------|-----|
| **책 추출** | 이름만 추출 | 이름 + context + time hint | 🔴 프롬프트 재설계 |
| **엔티티 매칭** | embedding 기반 | Wikidata 검색 기반 | 🔴 재구현 |
| **중복 처리** | 이름 비교 | QID 비교 | 🔴 재구현 |
| **검증 없는 엔티티** | 버림 or 쓰레기 | 별도 관리 + 신뢰도 | 🟡 설계 필요 |
| **관계 추출** | 없음 | 책에서 관계도 추출 | 🔴 새로 구현 |

---

### Layer 3: 백엔드 API

| 항목 | 현재 상태 | 필요한 것 | Gap |
|------|----------|----------|-----|
| **기본 CRUD** | ✅ 있음 | - | ✅ |
| **검색 API** | ✅ 있음 | - | ✅ |
| **Vector 검색** | ✅ pgvector | - | ✅ |
| **소스 추적 API** | ❌ 없음 | "이 정보 출처는?" | 🔴 구현 필요 |
| **관계 쿼리 API** | 부분적 | "이 인물과 연결된 것들" | 🟡 보강 필요 |
| **스토리 생성 API** | 부분적 | Person/Place/Era Story | 🟡 보강 필요 |
| **인과관계 API** | ❌ 없음 | Causal Chain 조회 | 🔴 구현 필요 |

---

### Layer 4: Core 시스템

| 시스템 | 역할 | 현재 상태 | Gap |
|--------|------|----------|-----|
| **CHALDEAS** | World State | 부분 구현 | 🟡 데이터 필요 |
| **SHEBA** | Query/Search | 부분 구현 | 🟡 데이터 필요 |
| **LOGOS** | LLM 응답 생성 | 부분 구현 | 🟡 데이터 필요 |
| **PAPERMOON** | Fact 검증 | ❌ 없음 | 🔴 구현 필요 |
| **LAPLACE** | 소스 추적 | ❌ 없음 | 🔴 구현 필요 |
| **TRISMEGISTUS** | 오케스트레이터 | ❌ 없음 | 🔴 구현 필요 |

**결론**: Core 시스템은 있어도 데이터가 쓰레기라 무의미

---

### Layer 5: 프론트엔드

| 항목 | 현재 상태 | 필요한 것 | Gap |
|------|----------|----------|-----|
| **3D 글로브** | ✅ 있음 | - | ✅ |
| **타임라인** | ✅ 있음 | - | ✅ |
| **검색 UI** | ✅ 있음 | - | ✅ |
| **인물 상세** | ✅ 있음 | 소스 표시 추가 | 🟡 |
| **관계 시각화** | 부분적 | 그래프 뷰 | 🟡 보강 필요 |
| **스토리 뷰** | 부분적 | 타임라인 스토리 | 🟡 보강 필요 |
| **FGO 연동** | ❌ 없음 | 서번트 ↔ 역사 | 🔴 구현 필요 |

**결론**: UI는 있는데 보여줄 데이터가 쓰레기

---

### Layer 6: 배포/운영

| 항목 | 현재 상태 | 필요한 것 | Gap |
|------|----------|----------|-----|
| **GCP 배포** | ✅ 있음 | - | ✅ |
| **도메인** | ✅ chaldeas.site | - | ✅ |
| **DB 동기화** | ✅ 스크립트 있음 | - | ✅ |
| **모니터링** | ❌ 없음 | 에러 추적 | 🟡 |
| **백업** | 수동 | 자동화 | 🟡 |

---

## 우선순위 분석

### 🔴 Critical (이거 없으면 아무것도 안 됨)

1. **깨끗한 엔티티 DB**
   - QID 기반 persons/locations/events
   - 중복 없음
   - 이거 없으면 나머지 다 의미 없음

2. **책 추출 파이프라인 재설계**
   - context 포함 추출
   - Wikidata 검색 기반 매칭
   - 소스 연결 (text_mentions)

3. **LAPLACE (소스 추적)**
   - "이 정보는 어디서 왔나?"
   - 신뢰도의 근거

### 🟡 Important (있으면 훨씬 좋음)

4. **관계 데이터 재구축**
   - person ↔ event
   - person ↔ location
   - event ↔ location
   - 인과관계

5. **스토리 생성**
   - Person Story: 인물의 생애
   - Place Story: 장소의 역사
   - Causal Chain: 인과관계

6. **FGO 연동**
   - 서번트 목록 → Wikidata QID 매핑
   - 게임 ↔ 실제 역사 연결

### 🟢 Nice to have

7. **관계 시각화** - 그래프 뷰
8. **PAPERMOON** - Fact 검증
9. **고급 검색** - 시대별, 지역별 필터

---

## 데이터 요구사항 상세

### Persons (인물)

**필수 필드**:
```
- wikidata_id: QID (있으면)
- name: 정식 이름
- birth_year, death_year: 생몰년
- description: 한 줄 설명
```

**선택 필드**:
```
- name_ko: 한국어 이름
- image_url: 초상화
- wikipedia_url: 위키피디아 링크
- occupation: 직업/역할
- nationality: 국적/소속
```

**메타데이터**:
```
- verification_status: verified/unverified/manual
- confidence_score: 신뢰도 (0-1)
- source_count: 출처 개수
- created_at, updated_at
```

### Locations (장소)

**필수 필드**:
```
- wikidata_id: QID (있으면)
- name: 정식 이름
- latitude, longitude: 좌표 ← 글로브에 필수!
- location_type: city/country/region/landmark
```

**현재 문제**:
- 40K 중 대부분 좌표 없음
- 글로브에 표시 불가

### Events (사건)

**필수 필드**:
```
- wikidata_id: QID (있으면)
- title: 사건명
- year_start, year_end: 기간
- location_id: 발생 장소 ← 글로브 연결
```

**현재 문제**:
- 연도 불명확한 것 많음
- 장소 연결 안 된 것 많음

### Relations (관계)

**필요한 관계 유형**:
```
person_events: 인물 ↔ 사건 (참여, 주도, 피해)
person_locations: 인물 ↔ 장소 (출생, 사망, 활동)
person_persons: 인물 ↔ 인물 (가족, 동료, 적대)
event_events: 사건 ↔ 사건 (원인, 결과, 동시)
event_locations: 사건 ↔ 장소 (발생지)
```

**현재 문제**:
- 관계 데이터 신뢰도 낮음
- 엔티티가 쓰레기라 관계도 쓰레기

### Text Mentions (출처)

**필요한 구조**:
```
- entity_type, entity_id: 어떤 엔티티
- source_id: 어떤 책/문서
- mention_text: 실제 언급된 텍스트
- context_text: 주변 문맥
- position: 책 내 위치
- confidence: 신뢰도
```

**현재 상태**: 거의 없음

---

## 실행 로드맵

### Phase 1: 데이터 정리 (1주)

```
Day 1-2: DB 분석 및 QID 있는 것 추출
Day 3-4: 중복 제거 및 정리
Day 5-7: Wikidata에서 기본 정보 보강
```

**결과**: ~90K 깨끗한 persons + locations + events

### Phase 2: 파이프라인 재구축 (1주)

```
Day 1-2: 추출 프롬프트 재설계
Day 3-4: Wikidata 검색 함수 구현
Day 5-7: 매칭 파이프라인 재구현
```

**결과**: 책 → 엔티티 → Wikidata → DB 파이프라인

### Phase 3: 소스 추적 구현 (1주)

```
Day 1-3: text_mentions 테이블 및 API
Day 4-5: LAPLACE 기본 구현
Day 6-7: 프론트엔드 소스 표시
```

**결과**: "이 정보는 [책 이름]에서 왔음" 표시

### Phase 4: 관계 재구축 (1주)

```
Day 1-3: 검증된 관계만 추출
Day 4-5: 관계 API 보강
Day 6-7: 관계 시각화
```

**결과**: 신뢰할 수 있는 관계 데이터

### Phase 5: FGO 연동 (3일)

```
Day 1: FGO 서번트 → Wikidata QID 매핑
Day 2: 서번트 상세 페이지
Day 3: 게임 ↔ 역사 연결 UI
```

**결과**: FGO 플레이어를 위한 역사 탐색

---

## 요약: 부족한 것 목록

### 데이터
- [ ] 깨끗한 persons (QID 기반)
- [ ] 좌표 있는 locations
- [ ] 연도 정확한 events
- [ ] 검증된 relations
- [ ] text_mentions (출처)

### 파이프라인
- [ ] context 포함 추출 프롬프트
- [ ] Wikidata 검색 함수
- [ ] QID 기반 매칭
- [ ] unverified 엔티티 관리
- [ ] 관계 추출

### 백엔드
- [ ] 소스 추적 API
- [ ] 인과관계 API
- [ ] 스토리 생성 API 보강

### Core 시스템
- [ ] LAPLACE (소스 추적)
- [ ] PAPERMOON (검증)
- [ ] TRISMEGISTUS (오케스트레이터)

### 프론트엔드
- [ ] 소스 표시 UI
- [ ] 관계 그래프 뷰
- [ ] FGO 연동 UI

### 콘텐츠
- [ ] FGO 서번트 QID 매핑
- [ ] 주요 인물 스토리
- [ ] 주요 사건 체인
