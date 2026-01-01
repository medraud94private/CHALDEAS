# Entity Linking 작업 계획서

> 작성일: 2025-12-31
> 목표: 인물(Persons) ↔ 사건(Events) ↔ 장소(Locations) 관계 연결

---

## 1. 현재 데이터 현황

### 1.1 테이블별 데이터

| 테이블 | 레코드 수 | 임베딩 | 비고 |
|--------|----------|--------|------|
| events | 10,921 | 완료 | 대부분 전투/전쟁 |
| persons | 59,902 | 완료 | Pantheon 데이터 |
| locations | 34,313 | 완료 | Pleiades + Topostext |

### 1.2 관계 테이블 (현재 비어있음)

| 테이블 | 현재 레코드 | 용도 |
|--------|------------|------|
| event_persons | 0 | 사건 참여 인물 |
| event_locations | 0 | 사건 발생 장소 |
| person_relationships | 0 | 인물 간 관계 |

### 1.3 각 테이블의 주요 필드

**events:**
- title, description, date_start, date_end
- primary_location_id (FK, 현재 NULL)
- category_id (FK, 현재 대부분 NULL)

**persons:**
- name, biography, birth_year, death_year
- birth_place, death_place (텍스트, 좌표 아님)
- occupation

**locations:**
- name, latitude, longitude
- type, country, region

---

## 2. Entity Linking이란?

### 2.1 목표

```
"Battle of Thermopylae" (사건)
    ├── 참여자: Leonidas I, Xerxes I (인물)
    └── 장소: Thermopylae (장소)

"Alexander the Great" (인물)
    ├── 참여 사건: Battle of Gaugamela, Siege of Tyre (사건)
    ├── 출생지: Pella (장소)
    └── 사망지: Babylon (장소)
```

### 2.2 왜 기계적 매칭이 어려운가?

1. **이름 불일치**:
   - Events: "Battle of Thermopylae"
   - Persons: "Leonidas I" (description에 Thermopylae 언급 있을 수도 있고 없을 수도)
   - 단순 문자열 매칭 불가

2. **관계 정보 부재**:
   - 현재 데이터에 "누가 어떤 사건에 참여했는지" 명시적 정보 없음
   - Wikidata에서 가져온 events에 participant 필드 없음

3. **좌표 매칭의 한계**:
   - Events에 좌표 있음 (12,756개)
   - Locations에 좌표 있음
   - 하지만 같은 좌표라고 반드시 관련 있는 것은 아님
   - 예: 로마에서 일어난 사건 수백 개 → 모두 "Rome" location에 연결?

---

## 3. 가능한 접근 방법

### 3.1 방법 A: Wikidata SPARQL 쿼리 (권장)

**개요**: Wikidata에서 직접 관계 데이터 쿼리

```sparql
# 사건의 참여자 조회
SELECT ?event ?eventLabel ?participant ?participantLabel
WHERE {
  ?event wdt:P31 wd:Q178561.  # instance of battle
  ?event wdt:P710 ?participant.  # participant
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
}
```

**장점**:
- 정확한 관계 데이터
- 무료
- 대량 쿼리 가능

**단점**:
- 우리 DB의 이벤트 ↔ Wikidata ID 매핑 필요
- 모든 이벤트가 Wikidata에 있지 않음

**작업량**: 스크립트 작성 2-3시간

---

### 3.2 방법 B: LLM 기반 추출

**개요**: GPT로 description에서 관계 추출

```python
prompt = """
Event: Battle of Thermopylae
Description: The Battle of Thermopylae was fought in 480 BCE...

Extract:
- Participants (people): [list]
- Location: [place name]
"""
```

**장점**:
- 유연함, description만 있으면 가능
- 우리 데이터 기준으로 작동

**단점**:
- 비용: ~10,000 events × $0.001 = ~$10
- 정확도 검증 필요
- 추출된 이름 → DB 인물/장소 매칭 추가 필요

**작업량**: 스크립트 작성 1시간 + 실행 2-3시간

---

### 3.3 방법 C: 좌표 근접 매칭 (event ↔ location만)

**개요**: 이벤트 좌표와 가장 가까운 location 연결

```python
# 이벤트 좌표에서 1km 이내 location 찾기
SELECT l.id, l.name
FROM locations l
WHERE ST_Distance(
  ST_Point(event_lng, event_lat),
  ST_Point(l.longitude, l.latitude)
) < 1000  -- meters
```

**장점**:
- 단순, 빠름
- 비용 없음

**단점**:
- person 연결 불가
- 정확도 낮음 (같은 도시의 다른 사건들)

**작업량**: 1시간

---

### 3.4 방법 D: FGO 서번트 중심 수동 큐레이션

**개요**: FGO 서번트 ~300명 기준으로 주요 관계만 수동 입력

**장점**:
- 가장 정확
- 프로젝트 목적에 맞음 (FGO 중심)

**단점**:
- 시간 소요 (서번트당 10분 × 300 = 50시간)
- 스케일 안 됨

---

## 4. 권장 실행 계획

### Phase 1: 기반 작업 (1-2시간)

1. **Wikidata ID 매핑 확인**
   - 현재 events 테이블에 wikidata_id 있는지 확인
   - 없으면 이름 기반으로 매핑 시도

2. **event_locations 좌표 매칭**
   - 이벤트 좌표 → 가장 가까운 location 연결
   - 정확도 낮지만 일단 연결은 됨

### Phase 2: Wikidata 관계 가져오기 (2-3시간)

1. **SPARQL 쿼리로 participant 데이터 수집**
   ```
   Battle ID → Participant IDs
   ```

2. **Participant ID → 우리 DB persons 매칭**
   - Wikidata ID 또는 이름 기반

3. **event_persons 테이블 채우기**

### Phase 3: LLM 보강 (선택)

- Wikidata에 없는 이벤트들
- Description 기반 추출

---

## 5. 즉시 실행 가능한 작업

### 5.1 event_locations 채우기 (좌표 기반)

```sql
-- events 테이블에 좌표 데이터 있는지 확인
SELECT COUNT(*) FROM events WHERE primary_location_id IS NULL;

-- wikidata 원본에서 좌표 가져와서 매칭
```

**예상 결과**: ~12,000개 event ↔ location 연결

### 5.2 Wikidata 관계 수집 스크립트

```python
# collect_wikidata_relations.py
# - SPARQL로 battle participant 조회
# - 결과를 JSON으로 저장
# - DB에 import
```

---

## 6. 결론

| 방법 | 정확도 | 비용 | 시간 | 커버리지 |
|------|--------|------|------|----------|
| Wikidata SPARQL | 높음 | $0 | 3h | 중간 |
| LLM 추출 | 중간 | $10 | 3h | 높음 |
| 좌표 매칭 | 낮음 | $0 | 1h | event↔location만 |
| 수동 큐레이션 | 최고 | $0 | 50h+ | 낮음 |

**권장 순서**:
1. 좌표 매칭으로 event↔location 연결 (즉시)
2. Wikidata SPARQL로 event↔person 연결 (오늘)
3. 나머지는 LLM 또는 수동 (나중에)

---

## 7. 다음 단계

이 문서 검토 후 진행 방향 결정:

- [ ] Phase 1 실행 (좌표 매칭)
- [ ] Phase 2 실행 (Wikidata SPARQL)
- [ ] 또는 다른 작업으로 전환
