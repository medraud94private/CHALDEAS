# Wikidata 자동 보강 시스템

## 개요

기존 이벤트/유닛에 Wikidata 기반으로:
1. 시대(Period) 자동 연결
2. 날짜 정밀도 보강
3. 계층 구조 구축

---

## 1. 날짜 모델 확장

### 현재 문제

```sql
-- 현재: 년도만
year_start INTEGER  -- 1453
year_end INTEGER    -- NULL or 1453

-- 표현 불가:
-- "1453년 5월 29일"
-- "약 기원전 500년경"
-- "14세기 중반"
-- "1337년 ~ 1453년"
```

### 새 날짜 모델

```sql
-- historical_units 테이블 수정
ALTER TABLE historical_units ADD COLUMN date_start DATE;
ALTER TABLE historical_units ADD COLUMN date_end DATE;
ALTER TABLE historical_units ADD COLUMN date_start_precision VARCHAR(20);
ALTER TABLE historical_units ADD COLUMN date_end_precision VARCHAR(20);

-- precision 값:
-- 'day': 1453-05-29 (정확한 날짜)
-- 'month': 1453-05 (월까지)
-- 'year': 1453 (년도)
-- 'decade': 1450s (10년 단위)
-- 'century': 15th century (세기)
-- 'millennium': 2nd millennium BC
-- 'circa': 약 ~경 (대략)
-- 'before': ~이전
-- 'after': ~이후
```

### 표시 로직

```python
def format_date_display(
    date_val: date,
    precision: str,
    is_bce: bool = False
) -> str:
    year = abs(date_val.year)
    era = "BC" if is_bce else "AD"

    if precision == 'day':
        return f"{date_val.strftime('%B %d')}, {year} {era}"
        # "May 29, 1453 AD"
    elif precision == 'month':
        return f"{date_val.strftime('%B')} {year} {era}"
        # "May 1453 AD"
    elif precision == 'year':
        return f"{year} {era}"
        # "1453 AD"
    elif precision == 'decade':
        decade = (year // 10) * 10
        return f"{decade}s {era}"
        # "1450s AD"
    elif precision == 'century':
        century = (year // 100) + 1
        return f"{century}th century {era}"
        # "15th century AD"
    elif precision == 'circa':
        return f"c. {year} {era}"
        # "c. 1450 AD"
    elif precision == 'before':
        return f"before {year} {era}"
    elif precision == 'after':
        return f"after {year} {era}"
```

### BCE 처리

```python
# PostgreSQL에서 BCE 날짜 처리
# 방법 1: 음수 년도 유지 (기존)
year_start = -500  # 500 BC

# 방법 2: date 타입 + is_bce 플래그
date_start = '0500-01-01'
date_start_is_bce = True

# 방법 3: Julian Day Number (천문학적)
# 권장하지 않음 - 복잡함
```

---

## 2. Wikidata 자동 보강 스크립트

### 핵심 속성

```
P580: start time (시작 시점)
P582: end time (종료 시점)
P585: point in time (단일 시점)
P361: part of (소속 시대/상위 개념)
P31: instance of (유형)
P17: country (관련 국가)
P276: location (장소)
P710: participant (참가자)
```

### 자동 보강 스크립트

```python
# poc/scripts/wikidata_enrich_units.py

import requests
from datetime import datetime
import re

WIKIDATA_API = "https://www.wikidata.org/w/api.php"
SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"

def get_wikidata_dates(qid: str) -> dict:
    """Wikidata에서 날짜 정보 조회"""
    query = f"""
    SELECT ?start ?end ?pointInTime ?precision WHERE {{
      OPTIONAL {{
        wd:{qid} p:P580 ?startStmt.
        ?startStmt psv:P580 ?startNode.
        ?startNode wikibase:timeValue ?start;
                   wikibase:timePrecision ?precision.
      }}
      OPTIONAL {{ wd:{qid} wdt:P582 ?end. }}
      OPTIONAL {{ wd:{qid} wdt:P585 ?pointInTime. }}
    }}
    """
    # ... execute query ...
    return {
        'start': start_date,
        'end': end_date,
        'precision': precision_level,
    }


def get_wikidata_period(qid: str) -> list:
    """이 아이템이 속한 시대/기간 조회"""
    query = f"""
    SELECT ?period ?periodLabel WHERE {{
      wd:{qid} wdt:P361 ?period.  # part of
      ?period wdt:P31/wdt:P279* wd:Q11514315.  # instance of historical period
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en,ko". }}
    }}
    """
    # Returns: ["Q12554" (Middle Ages), "Q486761" (Classical antiquity), ...]
    return periods


def enrich_historical_unit(db, unit_id: int, qid: str):
    """단일 유닛 보강"""

    # 1. 날짜 정보 보강
    dates = get_wikidata_dates(qid)
    if dates['start']:
        db.execute("""
            UPDATE historical_units
            SET date_start = %s,
                date_start_precision = %s
            WHERE id = %s AND date_start IS NULL
        """, (dates['start'], dates['precision'], unit_id))

    # 2. 시대 연결
    periods = get_wikidata_period(qid)
    for period_qid in periods:
        # 우리 DB에 해당 시대가 있는지 확인
        period = db.query("""
            SELECT id FROM historical_units
            WHERE wikidata_id = %s AND unit_type IN ('period', 'era', 'age')
        """, (period_qid,)).first()

        if period:
            # 관계 생성
            db.execute("""
                INSERT INTO historical_unit_relations
                (source_id, target_id, relation_type)
                VALUES (%s, %s, 'part_of')
                ON CONFLICT DO NOTHING
            """, (unit_id, period.id))


def batch_enrich(db, batch_size: int = 100):
    """wikidata_id가 있는 유닛들 일괄 보강"""

    units = db.query("""
        SELECT id, wikidata_id FROM historical_units
        WHERE wikidata_id IS NOT NULL
          AND (date_start_precision IS NULL OR NOT EXISTS (
              SELECT 1 FROM historical_unit_relations
              WHERE source_id = historical_units.id
                AND relation_type = 'part_of'
          ))
        LIMIT %s
    """, (batch_size,))

    for unit in units:
        try:
            enrich_historical_unit(db, unit.id, unit.wikidata_id)
            print(f"Enriched: {unit.id} ({unit.wikidata_id})")
        except Exception as e:
            print(f"Error {unit.id}: {e}")

        time.sleep(0.5)  # Rate limiting
```

### SPARQL 배치 쿼리 (효율적)

```sparql
# 여러 QID 한번에 조회
SELECT ?item ?start ?end ?precision ?period ?periodLabel WHERE {
  VALUES ?item { wd:Q12544 wd:Q2277 wd:Q486761 }  # Byzantine, Roman Empire, Classical antiquity

  OPTIONAL {
    ?item p:P580 ?startStmt.
    ?startStmt psv:P580 ?startNode.
    ?startNode wikibase:timeValue ?start;
               wikibase:timePrecision ?precision.
  }
  OPTIONAL { ?item wdt:P582 ?end. }
  OPTIONAL {
    ?item wdt:P361 ?period.
    ?period wdt:P31/wdt:P279* wd:Q11514315.
  }

  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
}
```

---

## 3. 이벤트 → 시대 자동 연결 로직

### 방법 1: 시간 기반 매칭

```python
def auto_link_to_period(unit_id: int, year_start: int, year_end: int):
    """시간 범위로 적절한 시대 찾기"""

    # 가장 좁은 범위의 시대 찾기
    period = db.query("""
        SELECT id, name, year_start, year_end,
               (year_end - year_start) as duration
        FROM historical_units
        WHERE unit_type IN ('period', 'era', 'age')
          AND year_start <= %s
          AND (year_end IS NULL OR year_end >= %s)
        ORDER BY duration ASC  -- 가장 좁은 범위 우선
        LIMIT 1
    """, (year_start, year_end or year_start))

    if period:
        create_relation(unit_id, period.id, 'part_of')
```

### 방법 2: Wikidata P361 기반

```python
def link_via_wikidata(unit_id: int, qid: str):
    """Wikidata 'part of' 관계 활용"""
    periods = get_wikidata_period(qid)

    for period_qid in periods:
        # DB에서 해당 시대 찾기
        period = find_by_wikidata_id(period_qid)
        if period:
            create_relation(unit_id, period.id, 'part_of')
```

### 방법 3: 하이브리드

```python
def smart_link_to_period(unit):
    # 1. Wikidata 있으면 그거 먼저
    if unit.wikidata_id:
        linked = link_via_wikidata(unit.id, unit.wikidata_id)
        if linked:
            return

    # 2. 없으면 시간 기반 매칭
    auto_link_to_period(unit.id, unit.year_start, unit.year_end)
```

---

## 4. 실행 계획

### Phase 1: 스키마 확장

```sql
-- 날짜 정밀도 컬럼 추가
ALTER TABLE historical_units ADD COLUMN date_start DATE;
ALTER TABLE historical_units ADD COLUMN date_end DATE;
ALTER TABLE historical_units ADD COLUMN date_start_precision VARCHAR(20) DEFAULT 'year';
ALTER TABLE historical_units ADD COLUMN date_end_precision VARCHAR(20) DEFAULT 'year';
ALTER TABLE historical_units ADD COLUMN date_start_is_bce BOOLEAN DEFAULT FALSE;
ALTER TABLE historical_units ADD COLUMN date_end_is_bce BOOLEAN DEFAULT FALSE;
```

### Phase 2: 기존 데이터 변환

```python
# year_start/year_end → date_start/date_end 변환
UPDATE historical_units
SET
    date_start = MAKE_DATE(ABS(year_start), 1, 1),
    date_start_is_bce = (year_start < 0),
    date_start_precision = 'year',
    date_end = CASE WHEN year_end IS NOT NULL
               THEN MAKE_DATE(ABS(year_end), 1, 1)
               ELSE NULL END,
    date_end_is_bce = (year_end < 0),
    date_end_precision = 'year'
WHERE year_start IS NOT NULL;
```

### Phase 3: Wikidata 보강 실행

```bash
# 배치 실행 (체크포인트 지원)
python poc/scripts/wikidata_enrich_units.py --batch-size 100 --resume
```

### Phase 4: 시대 자동 연결

```bash
python poc/scripts/auto_link_periods.py --method hybrid
```

---

## 5. 예상 결과

### Before
```
Battle of Crécy (1346)
- year_start: 1346
- year_end: NULL
- 시대 연결: 없음
```

### After
```
Battle of Crécy (1346)
- date_start: 1346-08-26
- date_start_precision: 'day'
- date_end: 1346-08-26
- date_end_precision: 'day'
- relations:
  - part_of: Hundred Years' War
  - part_of: Late Middle Ages
  - part_of: Medieval period
```

---

## 6. Wikidata Precision 매핑

```python
WIKIDATA_PRECISION_MAP = {
    0: 'billion_years',
    1: '100_million_years',
    3: 'million_years',
    4: '100000_years',
    5: '10000_years',
    6: 'millennium',
    7: 'century',
    8: 'decade',
    9: 'year',
    10: 'month',
    11: 'day',
}

# 우리 시스템으로 변환
def convert_precision(wikidata_precision: int) -> str:
    if wikidata_precision >= 11:
        return 'day'
    elif wikidata_precision == 10:
        return 'month'
    elif wikidata_precision == 9:
        return 'year'
    elif wikidata_precision == 8:
        return 'decade'
    elif wikidata_precision == 7:
        return 'century'
    else:
        return 'millennium'
```
