# 2026-01-18 복구 작업 계획

## 현재 상태 요약

### DB
| 테이블 | 총 개수 | wikidata_id | wikipedia_url | 본문 |
|--------|---------|-------------|---------------|------|
| Persons | 286,609 | 101,839 (35%) | 13,606 (5%) | 57,214 (20%) |
| Events | 46,704 | 0 (0%) | 550 (1%) | 23,225 (50%) |
| Locations | 40,613 | 0 (0%) | 0 (0%) | - |

### Wikipedia 추출 데이터 (보강 필요)
| 파일 | 레코드 수 | 상태 |
|------|----------|------|
| persons.jsonl | 200,427 | content/links 없음 |
| events.jsonl | 267,364 | content/links 없음 |
| locations.jsonl | 821,848 | content/links 없음 |

---

## 작업 계획

### Phase 1: Wikipedia 추출 데이터 보강

**스크립트**: `poc/scripts/enrich_wikipedia_extract.py`

**입력**: `poc/data/wikipedia_extract/*.jsonl`
**출력**: `poc/data/wikipedia_enriched/*.jsonl`

**채울 필드**:
- `content`: 전체 본문 (깨끗한 텍스트)
- `links`: 내부 하이퍼링크 목록
- `qid`: null이면 다시 추출
- `summary`: 정리된 요약
- `wikipedia_url`: path에서 생성

#### 체크리스트

- [ ] 1.1 persons.jsonl 보강 (200,427개)
- [ ] 1.2 events.jsonl 보강 (267,364개)
- [ ] 1.3 locations.jsonl 보강 (821,848개)
- [ ] 1.4 결과 검증: 모든 레코드에 content 있는지 확인
- [ ] 1.5 에러 레코드 분석 (path로 ZIM 못 찾은 경우)

**예상 시간**: 수 시간 (로컬 I/O, 병렬 처리)

---

### Phase 2: 원본소스 검증

**목표**: 추출된 모든 레코드가 원본 Wikipedia 문서를 찾을 수 있는지 확인

#### 체크리스트

- [ ] 2.1 enriched 파일에서 `_error` 필드 있는 레코드 추출
- [ ] 2.2 에러 유형 분류
  - path 없음
  - ZIM에서 못 찾음
  - 기타 에러
- [ ] 2.3 에러 원인 분석
- [ ] 2.4 가능하면 에러 복구

**기대 결과**: 에러율 1% 미만

---

### Phase 3: DB 임포트

**목표**: enriched 데이터를 DB에 반영

#### 체크리스트

- [ ] 3.1 Sources 테이블 구조 확인
- [ ] 3.2 임포트 스크립트 작성 (`import_enriched_to_db.py`)
- [ ] 3.3 Persons 임포트
  - Sources 레코드 생성 (content 포함)
  - person_sources 연결
  - persons.wikidata_id 업데이트 (있으면)
  - persons.wikipedia_url 업데이트
- [ ] 3.4 Events 임포트
  - Sources 레코드 생성
  - event_sources 연결
  - events.wikidata_id 업데이트 (컬럼 추가 필요할 수 있음)
  - events.wikipedia_url 업데이트
- [ ] 3.5 Locations 임포트
  - Sources 레코드 생성
  - location_sources 연결
  - locations.wikidata_id 업데이트 (컬럼 추가 필요할 수 있음)
  - locations.wikipedia_url 업데이트
- [ ] 3.6 임포트 결과 검증

---

### Phase 4: 관계 생성 (links 활용)

**목표**: Wikipedia 내부 링크를 활용하여 엔티티 간 관계 발견

#### 체크리스트

- [ ] 4.1 links 데이터 분석 (어떤 형태로 되어있는지)
- [ ] 4.2 관계 생성 로직 설계
  - Person A의 문서에 Person B 링크 있음 → 관계 후보
  - Event의 문서에 Person 링크 있음 → 참여자 후보
  - etc.
- [ ] 4.3 관계 생성 스크립트 작성
- [ ] 4.4 테스트 (샘플 데이터)
- [ ] 4.5 전체 실행
- [ ] 4.6 결과 검증

**참고**: links는 관계 발견의 **보조 수단**. 기존 방법론에 추가되는 것.

---

### Phase 5: 기존 Wikidata 작업 정리

**목표**: 이전 wikidata 매칭 작업 결과 정리

#### 체크리스트

- [ ] 5.1 현재 persons.wikidata_id 데이터 출처 확인
  - Wikipedia 추출 (qid 필드)
  - Wikidata reconcile 결과
  - 둘 다?
- [ ] 5.2 충돌 확인 (같은 person에 다른 qid)
- [ ] 5.3 정리 방침 결정
- [ ] 5.4 필요시 재매칭

---

## 우선순위

```
Phase 1 (보강) → Phase 2 (검증) → Phase 3 (임포트) → Phase 4 (관계) → Phase 5 (정리)
     ↓
   [현재 진행 중]
```

---

## 실행 명령어

### Phase 1
```bash
# Persons 보강
python poc/scripts/enrich_wikipedia_extract.py --type persons --workers 16

# Events 보강
python poc/scripts/enrich_wikipedia_extract.py --type events --workers 16

# Locations 보강
python poc/scripts/enrich_wikipedia_extract.py --type locations --workers 16

# 또는 전체
python poc/scripts/enrich_wikipedia_extract.py --type all --workers 16
```

### 진행 상황 확인
```bash
# 체크포인트 확인
cat poc/data/wikipedia_enriched/enrich_checkpoint.json

# 출력 파일 확인
wc -l poc/data/wikipedia_enriched/*.jsonl
```

---

## 진행 상황 추적

| Phase | 작업 | 상태 | 완료일 |
|-------|------|------|--------|
| 1.1 | persons 보강 | ✅ 완료 (200,427개, 에러 60) | 2026-01-18 |
| 1.2 | events 보강 | ✅ 완료 (267,363개, 에러 66) | 2026-01-18 |
| 1.3 | locations 보강 | ✅ 완료 (821,839개, 에러 36) | 2026-01-18 |
| 1.4 | 결과 검증 | ✅ 에러율 0.013% | 2026-01-18 |
| 1.5 | 에러 분석 | 보류 (에러 162개, 무시 가능) | - |
| 2.1~2.4 | 소스 검증 | 보류 | - |
| 3.1~3.6 | DB 임포트 | 대기 | - |
| 4.1~4.6 | 관계 생성 | ✅ 완료 | 2026-01-18 |
| 5.1~5.4 | Wikidata 정리 | 대기 | - |

## Phase 4 관계 생성 결과

| 관계 테이블 | 최종 레코드 수 |
|------------|---------------|
| person_relationships | 146,161 |
| event_persons | 417,666 |
| event_locations | 81,489 |
| person_locations | 510,431 |
