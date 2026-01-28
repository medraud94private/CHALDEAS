# Period/Era 추출 및 계층화 계획

## 개요

Wikipedia/Wikidata에서 역사적 시대(Period)와 정치체(Polity)를 추출하여
시간-공간 범위 개념을 구현.

---

## 현재 상태

### 기존 모델 (V1)
- `Period`: Braudel 시간 척도, 계층 구조 지원
- `Polity`: 제국/왕국 등 정치체, 시간적 유효성

### Kiwix 추출 결과 (검증됨)
```
Bronze Age (Q11761)     → period
Iron Age (Q11764)       → period, 1100 BC-150 AD
Classical antiquity     → period
Middle Ages (Q12554)    → period
Renaissance (Q4692)     → period
Roman Empire (Q2277)    → polity
Byzantine Empire        → polity
```

---

## 추출 전략

### 1. Period 분류 조건 (kiwix_extract_all.py 확장)

```python
# ===== PERIOD/ERA =====
def is_period(html: str, title: str) -> bool:
    html_lower = html[:50000].lower()
    title_lower = title.lower()

    # 타이틀 패턴
    period_title_patterns = [
        r'.*\s+age$',           # Bronze Age, Iron Age
        r'.*\s+period$',        # Hellenistic period
        r'.*\s+era$',           # Victorian era
        r'.*\s+antiquity$',     # Classical antiquity
        r'.*\s+ages$',          # Middle Ages
    ]
    for pat in period_title_patterns:
        if re.match(pat, title_lower):
            return True

    # 본문 키워드
    period_keywords = [
        'was a period', 'is a period',
        'was an era', 'is an era',
        'historical period', 'archaeological period',
        'prehistoric period', 'cultural period',
    ]
    for kw in period_keywords:
        if kw in html_lower:
            return True

    return False
```

### 2. Wikidata 보강 쿼리

```sparql
# Period 상세 정보 조회
SELECT ?period ?periodLabel ?start ?end ?partOf ?partOfLabel WHERE {
  VALUES ?period { wd:Q11761 wd:Q11764 wd:Q12554 wd:Q4692 }  # QIDs

  OPTIONAL { ?period wdt:P580 ?start. }      # start time
  OPTIONAL { ?period wdt:P582 ?end. }        # end time
  OPTIONAL { ?period wdt:P361 ?partOf. }     # part of (hierarchy)

  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,ko". }
}
```

### 3. 계층 구조 예시

```
Human History
├── Prehistory
│   ├── Stone Age
│   │   ├── Paleolithic
│   │   ├── Mesolithic
│   │   └── Neolithic
│   ├── Bronze Age (Q11761)
│   │   ├── Early Bronze Age
│   │   ├── Middle Bronze Age
│   │   └── Late Bronze Age
│   └── Iron Age (Q11764)
├── Ancient History
│   ├── Classical Antiquity (Q486761)
│   │   ├── Archaic Greece
│   │   ├── Classical Greece
│   │   └── Hellenistic period
│   └── Late Antiquity
├── Post-Classical
│   ├── Middle Ages (Q12554)
│   │   ├── Early Middle Ages
│   │   ├── High Middle Ages
│   │   └── Late Middle Ages
│   └── Islamic Golden Age
└── Modern History
    ├── Renaissance (Q4692)
    ├── Early Modern
    └── Contemporary
```

---

## 공간 범위 개념

### 문화권/문명 매핑

```
Period                  Spatial Scope
------                  -------------
Bronze Age              Mediterranean, Near East, East Asia (분리)
Classical Antiquity     Mediterranean (Greece, Rome)
Middle Ages             Europe, Islamic World, East Asia (분리)
Renaissance             Western Europe (Italy 중심)
```

### Polity-Period 연결

```python
# Period와 Polity 연결
period_polity_map = {
    'Classical Antiquity': [
        {'polity': 'Roman Republic', 'role': 'major'},
        {'polity': 'Roman Empire', 'role': 'major'},
        {'polity': 'Ptolemaic Egypt', 'role': 'major'},
    ],
    'Middle Ages': [
        {'polity': 'Byzantine Empire', 'role': 'major'},
        {'polity': 'Holy Roman Empire', 'role': 'major'},
        {'polity': 'Abbasid Caliphate', 'role': 'major'},
    ]
}
```

---

## 구현 단계

### Phase 1: Period 추출 스크립트 확장

```python
# kiwix_extract_all.py에 period 분류 추가
def classify_entity(html: str, title: str) -> Optional[str]:
    # ... existing code ...

    # ===== PERIOD =====
    if is_period(html, title):
        return 'period'

    # ===== POLITY =====
    if is_polity(html, title):
        return 'polity'
```

### Phase 2: Wikidata 보강
- QID 기반 P580/P582 시간 정보 조회
- P361 (part of) 계층 구조 구축
- P17/P131 지리적 범위 연결

### Phase 3: DB 스키마 연결
- `periods` 테이블에 추출 데이터 임포트
- `polities` 테이블에 추출 데이터 임포트
- `period_locations` 연결 테이블 (공간 범위)

### Phase 4: Globe 시각화 연동
- 줌 레벨별 Period/Location 표시
- 시대 선택 시 해당 기간 이벤트 필터링

---

## 예상 추출량

| 엔티티 | 예상 수량 | 소스 |
|--------|----------|------|
| Period (시대) | ~500개 | Kiwix 분류 |
| Polity (정치체) | ~2,000개 | Kiwix 분류 |
| Period-Location 연결 | ~1,500개 | Wikidata P17/P131 |
| Period 계층 | ~300개 | Wikidata P361 |

---

## 의존성

- [x] Period 모델 존재 (v1)
- [x] Polity 모델 존재 (v1)
- [ ] Kiwix 추출 완료 (진행 중)
- [ ] kiwix_extract_all.py 확장
- [ ] Wikidata 보강 스크립트 작성

---

## Wikidata 활용 가능 속성

| Property | 설명 | 용도 |
|----------|------|------|
| P580 | start time | 시작 연도 |
| P582 | end time | 종료 연도 |
| P361 | part of | 계층 (Bronze Age → Prehistory) |
| P17 | country | 관련 국가 |
| P131 | located in | 지리적 범위 |
| P279 | subclass of | 상위 개념 |
| P527 | has part | 하위 시대 |
| P155 | follows | 선행 시대 |
| P156 | followed by | 후행 시대 |
