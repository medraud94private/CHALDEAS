# CHALDEAS 데이터 품질 보고서

**생성일**: 2026-01-07
**목적**: 지오코딩 재작업 전 데이터 현황 파악

---

## 1. 데이터 파이프라인 요약

```
76,023개 원본 문서 (World History Encyclopedia 등)
    ↓ NER 추출 (GPT-5-nano Batch API, ~$47)
595,146개 텍스트 멘션
    ↓ 엔티티 집계
330,657개 엔티티 (persons, locations, events, polities, periods)
    ↓ 필터링 (최소 멘션 수 기준)
10,428개 이벤트 → DB 임포트
    ↓ 위치 매칭 (단순 문자열 매칭 - 문제 발생)
2,823개 이벤트에 위치 할당 (대부분 잘못됨)
```

---

## 2. 현재 데이터 현황

### 2.1 핵심 테이블

| 테이블 | 레코드 수 | 비고 |
|--------|-----------|------|
| sources | 76,023 | 원본 문서 |
| events | 10,428 | 역사적 사건 |
| persons | 285,750 | 인물 |
| locations | 34,409 | 장소 (100% 좌표 있음, Pleiades) |
| polities | 9 | 정치체/국가 |
| periods | 61 | 시대 구분 |
| text_mentions | 595,146 | 엔티티-문서 연결 |

### 2.2 이벤트 출처 분석

| 출처 | 이벤트 수 | 비율 | 신뢰도 |
|------|-----------|------|--------|
| NER 추출 (URL 없음) | 9,871 | 94.7% | **낮음** |
| Wikipedia | 363 | 3.5% | 높음 |
| World History Encyclopedia | 194 | 1.9% | 높음 |
| **합계** | **10,428** | 100% | - |

### 2.3 이벤트 위치 현황

| 항목 | 수량 | 비율 |
|------|------|------|
| 위치 할당됨 | 2,823 | 27.1% |
| 위치 없음 | 7,605 | 72.9% |
| **의심스러운 위치** | 869 | 8.3% |

**의심스러운 위치 정의**: 5개 이상 이벤트가 할당되고, 연도 범위가 500년 이상인 위치
- 예: "Vasio" (프랑스) - 79개 이벤트, BC 491 ~ AD 2022 (2513년 span)
- 예: "Thia" (터키) - 18개 이벤트, BC 512 ~ AD 1915 (2427년 span)

### 2.4 이벤트 연도 분포

| 시대 | 이벤트 수 | 비율 |
|------|-----------|------|
| BC 3000 이전 | 4 | 0.0% |
| BC 3000~1000 | 15 | 0.1% |
| BC 1000~0 | 482 | 4.6% |
| AD 0~500 | 370 | 3.5% |
| AD 500~1000 | 303 | 2.9% |
| AD 1000~1500 | 1,246 | 12.0% |
| AD 1500~1800 | 2,266 | 21.7% |
| AD 1800~1900 | 2,158 | 20.7% |
| AD 1900~2000 | 2,343 | 22.5% |
| AD 2000+ | 1,241 | 11.9% |

**참고**: 고대 이벤트(BC)가 전체의 4.7%에 불과. 근현대 편중.

### 2.5 카테고리 분포

| 카테고리 | 이벤트 수 | 비율 |
|----------|-----------|------|
| battle | 5,553 | 53.3% |
| war | 1,438 | 13.8% |
| science | 1,412 | 13.5% |
| politics | 1,106 | 10.6% |
| (NULL) | 600 | 5.8% |
| culture | 227 | 2.2% |
| civilization | 59 | 0.6% |
| religion | 17 | 0.2% |
| discovery | 16 | 0.2% |

**문제**: `philosophy` 카테고리가 UI에 있지만 이벤트 0개

---

## 3. 위치 매칭 문제 상세

### 3.1 현재 매칭 로직 (문제 있음)

```python
# poc/scripts/import_entities_to_db.py:276-282
loc_names = ev.get('locations_involved', [])  # NER이 추출한 위치명
for loc_name in loc_names:
    if loc_name.lower() in location_ids:  # 단순 문자열 매칭
        primary_location_id = location_ids[loc_name.lower()]
        break
```

### 3.2 문제 사례

| 이벤트 | 현재 위치 | 실제 위치 |
|--------|-----------|-----------|
| Battle of Thermopylae | Vasio (프랑스) | Thermopylae (그리스) |
| Battle of Carrhae | Thia (터키 북동부) | Harran (터키 남동부) |
| Battle of Mathias Point | Thia (터키) | Virginia (미국) |
| Mongol invasion of China | Vasio (프랑스) | China/Mongolia |

### 3.3 의심스러운 위치 Top 10

| 위치명 | 타입 | 이벤트 수 | 연도 범위 |
|--------|------|-----------|-----------|
| Vasio | settlement | 79 | BC 491 ~ AD 2022 |
| Kish | island | 61 | AD 426 ~ 1920 |
| Gari | settlement | 47 | AD 756 ~ 1939 |
| Obelisk of Theodosius | monument | 41 | BC 509 ~ AD 2022 |
| Isin | settlement | 39 | AD 1328 ~ 1921 |
| Orthe | unknown | 38 | AD 240 ~ 1974 |
| Roman forum of London | forum | 31 | BC 1300 ~ AD 2019 |
| Damascus | settlement | 30 | AD 531 ~ 2025 |
| Afri | label | 24 | BC 205 ~ AD 2011 |
| Gent | settlement | 24 | BC 260 ~ AD 1994 |

---

## 4. 제안: LLM 기반 지오코딩

### 4.1 대상 이벤트

| 구분 | 수량 | 처리 방식 |
|------|------|-----------|
| Wikipedia URL 있음 | 557 | Wikipedia API로 좌표 추출 (무료) |
| 설명 100자 이상 | 854 | LLM 지오코딩 |
| 제목만 있음 | 나머지 | LLM 지오코딩 (낮은 우선순위) |

### 4.2 비용 예상

| 모델 | 토큰/요청 | 총 토큰 | 비용 |
|------|-----------|---------|------|
| gpt-4o-mini | ~800 | ~8.3M | ~$2 |
| gpt-4o-mini (Batch) | ~800 | ~8.3M | ~$1 |
| gpt-5-nano | ~800 | ~8.3M | ~$10-15 |

### 4.3 출력 형식

```json
{
  "event_id": 12345,
  "location_name": "Thermopylae",
  "modern_name": "Thermopylae, Greece",
  "latitude": 38.7967,
  "longitude": 22.5367,
  "confidence": "high",
  "location_type": "battlefield",
  "reasoning": "Famous battle site in central Greece"
}
```

---

## 5. 권장 작업 순서

1. **즉시**: 의심스러운 869개 이벤트의 `primary_location_id` NULL 처리
2. **Phase 1**: Wikipedia URL 있는 557개 이벤트 좌표 추출 (무료)
3. **Phase 2**: 나머지 이벤트 LLM 지오코딩 (~$2-15)
4. **Phase 3**: 검증 및 수동 보정

---

## 6. 다음 단계

- [ ] 의심스러운 위치 데이터 정리
- [ ] Wikipedia API 좌표 추출 스크립트 작성
- [ ] LLM 지오코딩 배치 스크립트 작성
- [ ] 결과 검증 및 적용
