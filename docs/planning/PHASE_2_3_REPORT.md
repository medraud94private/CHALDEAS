# Phase 2 & 3: Source 연결 및 Entity 정리 보고서

**Date**: 2026-01-08
**Status**: 계획 수립 완료
**Prerequisites**: Phase 1 (Event Enrichment) 완료

---

## Executive Summary

| Phase | 목표 | 현재 상태 | 예상 작업량 |
|-------|------|----------|------------|
| Phase 2 | Source-Event 연결 | 910/10,428 (8.7%) | 9,518건 연결 필요 |
| Phase 3 | Person/Location 정리 | 중복 존재 | 정리 및 보강 |

---

## Phase 2: Source-Event 연결 검증

### 2.1 현재 상태

```
총 이벤트:        10,428건
소스 연결된 이벤트:    910건 (8.7%)
소스 없는 이벤트:   9,518건 (91.3%)

총 소스 문서:     76,023건
이벤트 멘션:       4,675건 (text_mentions)
```

### 2.2 문제점

대부분의 이벤트(91.3%)가 소스와 연결되어 있지 않음:

```
┌─────────────────┐     ┌─────────────────┐
│   Events        │     │   Sources       │
│   10,428건      │ ??? │   76,023건      │
│                 │     │                 │
│  [9,518 orphan] │     │                 │
└─────────────────┘     └─────────────────┘
```

**영향**:
- 멀티소스 요약 불가 (어떤 소스가 어떤 이벤트 언급하는지 모름)
- 출처 추적 불가
- Historical Chain 생성 시 근거 제시 불가

### 2.3 연결이 잘 된 이벤트 (Top 10)

| Event | 소스 수 |
|-------|--------|
| Battle of Waterloo | 276 |
| Battle of Hastings | 149 |
| French Revolution | 107 |
| War of 1812 | 76 |
| Battle of Bunker Hill | 63 |
| Battle of Agincourt | 61 |
| Treaty of Paris (1812) | 56 |
| American Revolution | 50 |
| Crimean War | 47 |
| Battle of Marathon | 45 |

### 2.4 해결 방안

#### Option A: LLM 기반 매칭 (권장)

소스 문서를 읽고 어떤 이벤트를 언급하는지 LLM이 판단:

```
Source Document
    ↓ LLM reads
"This book discusses the Battle of Marathon,
 the Persian Wars, and Alexander's campaigns..."
    ↓ LLM identifies
[event_123: Battle of Marathon]
[event_456: Persian Wars]
[event_789: Alexander's Indian Campaign]
    ↓
text_mentions 테이블에 저장
```

**장점**:
- 높은 정확도
- 문맥 이해 가능 ("마라톤 승리" → "Battle of Marathon")

**단점**:
- 비용 발생 (76,023 문서 × ~$0.01 = ~$760)
- 시간 소요

#### Option B: 키워드 매칭 (저비용)

이벤트 제목으로 소스 본문 검색:

```python
for event in events:
    matches = search_sources(event.title)
    for source in matches:
        create_text_mention(event, source)
```

**장점**:
- 비용 없음
- 빠름

**단점**:
- 정확도 낮음 ("테르모필레 전투" ≠ "Battle of Thermopylae")
- 동음이의어 문제 ("Marathon" = 전투? 달리기?)

#### Option C: 하이브리드 (권장)

1. 키워드 매칭으로 후보 생성
2. 낮은 confidence 건만 LLM 검증

```
Step 1: 키워드 매칭
  76,023 sources × 10,428 events
    ↓ 후보 생성
  ~50,000 후보 쌍

Step 2: Confidence 분류
  높음 (>90%): 자동 연결
  중간 (50-90%): LLM 검증
  낮음 (<50%): 폐기

Step 3: LLM 검증
  ~10,000건 검증 × $0.001 = ~$10
```

### 2.5 체크포인트

#### CP-2.1: 현황 분석 ✅ (이 보고서)
- [x] text_mentions 테이블 분석
- [x] 연결 현황 통계
- [x] 해결 방안 비교

#### CP-2.2: 매칭 전략 선택
- [ ] Option A/B/C 중 선택
- [ ] 파일럿 테스트 (100건)
- [ ] 정확도/비용 평가

#### CP-2.3: 매칭 스크립트 개발
- [ ] `poc/scripts/match_events_to_sources.py`
- [ ] 키워드 매칭 로직
- [ ] (Option C 시) LLM 검증 로직

#### CP-2.4: 전체 매칭 실행
- [ ] 전체 소스 처리
- [ ] text_mentions 테이블 업데이트
- [ ] 결과 검증

#### CP-2.5: 결과 분석
- [ ] 연결률 개선 확인
- [ ] 샘플 검토
- [ ] 문제 케이스 식별

---

## Phase 3: Person/Location 정리

### 3.1 Persons 현재 상태

```
총 인물:          285,750건
생년 있음:         65,411건 (22.9%)
몰년 있음:         59,824건 (20.9%)
소스 연결:        232,623건 (81.4%)
중복 이름:            597개
```

#### 메타데이터 품질

| 필드 | 채워진 비율 |
|-----|-----------|
| name | ~100% |
| birth_year | 22.9% |
| death_year | 20.9% |
| nationality | ? |
| occupation | ? |

#### 중복 예시

```
"William Smith" → 5건 (다른 사람들)
"Appius Claudius Pulcher" → 5건 (로마 역사에 동명이인 많음)
```

### 3.2 Locations 현재 상태

```
총 위치:          38,244건
좌표 있음:        38,244건 (100%) ← Phase 1에서 보강됨
중복 이름:            854개
```

#### 중복 예시

동일 이름이지만 다른 장소:
- "Paris" → Paris, France / Paris, Texas / Paris, Ontario
- "Alexandria" → 알렉산더가 세운 여러 도시들

### 3.3 해결 방안

#### 3.3.1 Persons 정리

**A. 중복 병합**

```
동일 인물 판단 기준:
1. 이름 유사도 > 90%
2. 생몰년 일치 (±5년)
3. 동일 소스에서 추출

"Socrates" (BC 470-399, Athens)
  = "소크라테스" (BC 470-399, 아테네)
  ≠ "Socrates Scholasticus" (AD 380-450, Constantinople)
```

**B. 메타데이터 보강 (LLM)**

```python
prompt = """
Person: Socrates
Current data:
  birth_year: -470
  death_year: -399

Please provide:
  - nationality: Greek
  - occupation: [philosopher]
  - era: CLASSICAL
  - notable_for: Founder of Western philosophy
"""
```

**예상 비용**: 285,750 × $0.001 = ~$285 (선택적)

#### 3.3.2 Locations 정리

**A. 중복 병합**

좌표 기반으로 동일 장소 판단:
```
거리 < 1km AND 이름 유사도 > 80% → 병합 후보
```

**B. 타입 정규화**

```
battlefield, city, region, country, sea, river, mountain...
```

### 3.4 체크포인트

#### CP-3.1: Persons 분석
- [ ] 중복 인물 목록 추출
- [ ] 메타데이터 현황 상세 분석
- [ ] 보강 필요 항목 식별

#### CP-3.2: Persons 중복 처리
- [ ] 중복 판단 기준 확정
- [ ] 병합 스크립트 개발
- [ ] 자동 병합 실행 (높은 confidence)
- [ ] 수동 검토 대상 추출

#### CP-3.3: Persons 메타데이터 보강 (선택)
- [ ] LLM 보강 프롬프트 설계
- [ ] 파일럿 테스트 (100건)
- [ ] 전체 실행 여부 결정

#### CP-3.4: Locations 분석
- [ ] 중복 위치 목록 추출
- [ ] 좌표 정확도 샘플 검토
- [ ] 타입 분포 확인

#### CP-3.5: Locations 정리
- [ ] 중복 병합
- [ ] 타입 정규화
- [ ] 좌표 검증 (outlier 확인)

---

## 우선순위 및 의존성

```
Phase 1 (완료)
    ↓
Phase 2 (Source 연결)  ←── 큐레이션(멀티소스 요약)에 필수
    ↓
Phase 3 (Entity 정리)  ←── Person/Place Story에 필요
    ↓
Phase 4 (큐레이션)
```

### 권장 순서

1. **Phase 2 먼저** (필수)
   - 멀티소스 요약의 기반
   - 비용 효율적 (Option C: ~$10)

2. **Phase 3은 선택적**
   - Person Story 필요 시 진행
   - 비용 높음 (LLM 보강 시 ~$285)

---

## 예상 비용 요약

| Phase | 작업 | 예상 비용 |
|-------|------|----------|
| Phase 2 | Source-Event 매칭 (Option C) | ~$10 |
| Phase 3a | Person 중복 병합 | $0 (로직만) |
| Phase 3b | Person 메타데이터 보강 | ~$285 (선택) |
| Phase 3c | Location 정리 | $0 (로직만) |
| **합계** | | **$10 ~ $295** |

---

## 파일 위치

| Component | Path |
|-----------|------|
| 이 보고서 | `docs/planning/PHASE_2_3_REPORT.md` |
| Phase 2 스크립트 (예정) | `poc/scripts/match_events_to_sources.py` |
| Phase 3 스크립트 (예정) | `poc/scripts/cleanup_entities.py` |

---

## 다음 단계

1. Phase 2 진행 여부 결정
2. Option A/B/C 중 선택
3. 파일럿 테스트 후 전체 실행
