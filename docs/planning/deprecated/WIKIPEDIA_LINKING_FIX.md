# Wikipedia 링크 문제 분석 및 해결 계획

## 현재 상태

### 데이터 현황

| 데이터 | 개수 | Wikidata ID | Wikipedia URL | 상태 |
|--------|------|-------------|---------------|------|
| DB Persons | 286,609 | 101,839 (35%) | 13,606 (5%) | 부분적 |
| DB Events | 46,704 | 0 (0%) | 550 (1%) | 문제 |
| DB Locations | 40,613 | 0 (0%) | 0 (0%) | 심각 |

### Wikipedia 추출 데이터 (JSONL)

| 파일 | 개수 | 출처 정보 |
|------|------|-----------|
| persons.jsonl | 200,427 | path, title, qid ✓ |
| events.jsonl | 267,364 | path, title, qid ✓ |
| locations.jsonl | 821,848 | path, title, qid ✓ |

**추출 파일은 정상** - 각 항목에 Wikipedia 경로(path)가 기록됨.

---

## 문제점

### 내가 잘못한 것

1. **단순 이름 매칭만 시도**: 기존 DB 데이터와 Wikipedia 추출 데이터를 이름으로만 매칭
2. **낮은 매칭률**: 12,330개만 연결됨 (전체의 극소수)
3. **원본 데이터 보강 안 됨**: DB의 기존 데이터에 wikidata_id, wikipedia_url 직접 업데이트 안 함
4. **새 데이터 임포트 안 됨**: Wikipedia 추출 데이터를 DB에 새로 추가하지 않음

### 해야 했던 것

1. Wikipedia 추출 데이터를 DB에 **임포트** (새 엔티티로)
2. 기존 DB 데이터에 **wikidata_id, wikipedia_url 직접 보강**
3. 중복 체크 후 **병합** (같은 엔티티면 합치기)
4. 모든 엔티티에 **출처(Source) 연결**

---

## 해결 방안

### Option 1: DB 직접 보강 (기존 데이터 유지)

기존 DB 데이터를 유지하면서 Wikipedia 정보 추가.

```
1. DB events/locations에 wikidata_id 컬럼 채우기
   - Wikipedia 추출 데이터의 qid 활용
   - 이름 매칭 + fuzzy matching으로 연결

2. wikipedia_url 컬럼 채우기
   - path를 URL로 변환하여 저장

3. Source 테이블에 Wikipedia 출처 추가
   - 각 엔티티별 Wikipedia Source 레코드 생성
```

**장점**: 기존 데이터 유지
**단점**: 매칭 안 되는 건 여전히 출처 없음

### Option 2: Wikipedia 데이터 우선 임포트 (권장)

Wikipedia 추출 데이터를 메인으로 사용.

```
1. Wikipedia JSONL → DB 임포트
   - 각 항목을 새 레코드로 생성
   - path → wikipedia_url
   - qid → wikidata_id
   - Source 레코드 자동 생성

2. 기존 DB 데이터와 병합
   - 중복 체크 (이름 + 연도 등)
   - 중복이면: 기존 데이터에 Wikipedia 정보 추가
   - 신규면: 새 레코드 유지

3. 기존 전용 데이터 보존
   - Wikipedia에 없는 기존 데이터는 별도 표시
```

**장점**: 모든 Wikipedia 데이터에 출처 보장
**단점**: DB 구조 변경 필요, 중복 처리 복잡

### Option 3: 하이브리드 (실용적)

```
1. 매칭된 12,330개: 기존 DB 레코드에 wikidata_id/wikipedia_url 직접 업데이트
2. 매칭 안 된 Wikipedia 데이터: 새 레코드로 임포트 (is_wikipedia_sourced = true)
3. 매칭 안 된 기존 DB: 유지하되 needs_source = true 표시
```

---

## 즉시 실행 가능한 작업

### 1단계: 매칭된 데이터에 wikidata_id 직접 보강

현재 linker가 만든 Sources 테이블 연결을 활용해서 DB 엔티티에 직접 wikidata_id 업데이트.

```sql
-- 예: Sources에서 wikidata_id 추출하여 persons에 업데이트
UPDATE persons p
SET wikidata_id = s.document_id
FROM person_sources ps
JOIN sources s ON ps.source_id = s.id
WHERE ps.person_id = p.id
AND s.archive_type = 'wikipedia'
AND s.document_id IS NOT NULL
AND p.wikidata_id IS NULL;
```

### 2단계: 기존 DB 데이터 Wikidata 직접 조회

wikidata_id 없는 항목들을 Wikidata API로 직접 조회하여 보강.

### 3단계: Wikipedia 신규 데이터 임포트

매칭 안 된 Wikipedia 데이터 중 품질 좋은 것 선별 임포트.

---

## 결론

**추출 데이터는 살아있음**. JSONL 파일에 출처 정보 다 있음.

문제는 **링킹 방식이 잘못됨**. 이름 매칭만 하고 끝낸 게 아니라:
1. DB 직접 업데이트
2. 신규 데이터 임포트
3. Source 테이블 정리

이 작업들을 해야 함.

---

## 작업 순서 (제안)

- [ ] 1. 매칭된 12,330개에 wikidata_id/wikipedia_url 직접 업데이트
- [ ] 2. Events/Locations wikidata_id 0개 문제 해결 (Wikidata API 조회)
- [ ] 3. Wikipedia 추출 데이터 중 신규 항목 임포트 여부 결정
- [ ] 4. 데이터 품질 분류 (A/B/C/D 등급)
