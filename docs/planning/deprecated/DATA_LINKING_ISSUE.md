# 데이터 연결 문제: NER 파이프라인 오류

> **발견일**: 2026-01-12
> **상태**: 심각 - 해결 필요
> **영향**: Person Story 데이터 품질 문제

---

## 핵심 문제: NER False Positives

`text_mentions` 테이블에 **잘못된 인물-이벤트 연결**이 대량으로 존재.

### 예시: Joan of Arc (ID 85)

NER이 "Joan of Arc"를 찾았다고 기록한 이벤트들:

| 이벤트 | 연도 | 실제 내용 |
|--------|------|-----------|
| Battle of Ankokuji | 1542 | 일본 전투 |
| Jay's Treaty | 1794 | 미국 조약 |
| Battle of White Bird Canyon | 1877 | 미국 원주민 전쟁 |
| Battle of Bruyères | 1944 | WW2 프랑스 |
| Hartford Circus Fire | 1944 | 미국 서커스 화재 |
| Hoyvík Agreement | 2005 | 페로 제도 협정 |

**잔 다르크(1412-1431)와 전혀 무관한 이벤트들!**

### 원인 분석

1. NER 모델(gpt-5-nano)이 "Joan" 또는 "Arc" 단어만으로 매칭
2. 문맥 검증 없이 저장
3. `confidence` 값이 0.3~1.0으로 부정확

---

## 문제 요약 (기존)

잔 다르크(Joan of Arc, ID 85)에 대해:
- `events` 테이블: 관련 이벤트 12개 존재
- `persons` 테이블: 인물 레코드 존재
- `event_persons` 테이블: **연결 0개**
- `event_connections` (person layer): **연결 0개**

Chain builder는 `event_persons`를 기반으로 작동하므로, 여기 연결이 없으면 Story 데이터도 없음.

---

## 영향받는 인물

현재 `event_persons`에 연결이 없는 인물 중 유명인:

| 인물 | ID | event_persons | 비고 |
|------|-----|---------------|------|
| Joan of Arc | 85 | 0 | 첫 쇼케이스 대상 |
| (추가 확인 필요) | | | |

### 정상 작동 인물

| 인물 | ID | event_connections |
|------|-----|-------------------|
| Napoleon | 26 | 902개 |
| Louis XIV | 124686 | 503개 |
| Elizabeth | 532 | 466개 |

---

## 원인 분석

### 가능한 원인

1. **NER 파이프라인 누락**: 이벤트 텍스트에서 "Joan of Arc" 추출 실패
2. **이름 변형 문제**: "Jeanne d'Arc", "La Pucelle" 등 변형 미처리
3. **Import 순서**: 인물보다 이벤트가 먼저 임포트되어 연결 못 함

### 확인 방법

```sql
-- 잔 다르크 관련 이벤트 확인
SELECT id, title, date_start
FROM events
WHERE title ILIKE '%joan%arc%'
   OR title ILIKE '%siege%orleans%'
   OR title ILIKE '%maid%orleans%';

-- event_persons에 있는지 확인
SELECT * FROM event_persons WHERE person_id = 85;
```

---

## 해결 방안

### 방안 1: 수동 연결 (즉시 적용 가능)

```sql
-- 잔 다르크 이벤트 수동 연결
INSERT INTO event_persons (event_id, person_id, role)
SELECT e.id, 85, 'subject'
FROM events e
WHERE (e.title ILIKE '%joan of arc%'
    OR e.title ILIKE '%siege of orleans%'
    OR e.title ILIKE '%maid of orleans%'
    OR e.title ILIKE '%jeanne d%arc%')
  AND NOT EXISTS (
    SELECT 1 FROM event_persons ep
    WHERE ep.event_id = e.id AND ep.person_id = 85
  );
```

### 방안 2: NER 재실행 (전체 데이터)

`poc/scripts/run_ner_pipeline.py` 실행하여 모든 이벤트에서 인물 추출

### 방안 3: 별칭 기반 자동 연결 스크립트

```python
# 인물 별칭 목록
PERSON_ALIASES = {
    85: ["Joan of Arc", "Jeanne d'Arc", "La Pucelle", "Maid of Orleans"],
    26: ["Napoleon", "Bonaparte", "Napoleon I"],
    # ...
}

# 이벤트 제목/설명에서 별칭 검색하여 자동 연결
```

---

## 즉시 해결: 잔 다르크 수동 연결

```sql
-- 1. 연결할 이벤트 확인
SELECT id, title, date_start
FROM events
WHERE title ILIKE '%joan%'
   OR title ILIKE '%orleans%siege%'
   OR title ILIKE '%orleans%liberation%'
   OR title ILIKE '%reims%coronation%1429%'
   OR title ILIKE '%rouen%execution%'
ORDER BY date_start;

-- 2. event_persons에 삽입
INSERT INTO event_persons (event_id, person_id, role)
VALUES
  (EVENT_ID_1, 85, 'subject'),
  (EVENT_ID_2, 85, 'subject'),
  ...;

-- 3. Chain builder 재실행 (person layer만)
-- python poc/scripts/build_event_chains.py --person-only --person-id 85
```

---

## 장기 해결: 인물-이벤트 자동 연결 파이프라인

### 새 스크립트 필요: `poc/scripts/link_persons_to_events.py`

**기능:**
1. persons 테이블에서 인물 이름 + 별칭 로드
2. events 테이블에서 제목/설명 검색
3. 매칭되면 event_persons에 삽입
4. 신뢰도 점수 부여

**우선순위 인물:**
- 쇼케이스 대상 (잔 다르크, 나폴레옹, 알렉산더 등)
- FGO 서번트 목록
- 역사적 중요 인물 500인

---

## 다음 작업

1. [ ] 잔 다르크 이벤트 수동 연결
2. [ ] Chain builder 재실행 (person_id=85만)
3. [ ] Story UI에서 데이터 확인
4. [ ] `link_persons_to_events.py` 스크립트 작성
5. [ ] 주요 인물 100명 자동 연결
