# V1 Pipeline 실패 보고서

**Date**: 2026-01-08
**Status**: 문제 분석 완료, 해결 필요

---

## 1. 비용 요약

| 단계 | 작업 | 비용 | 결과 |
|------|------|------|------|
| NER 추출 | 76,023 문서 → GPT-5-nano | ~$47 | 124,990 이벤트 추출 |
| 엔리치먼트 | 10,428 이벤트 → GPT-5.1-chat | ~$40 | 메타데이터 수정 |
| **총계** | | **~$87** | |

---

## 2. 문제점

### 2.1 데이터 흐름 (의도)

```
Source Documents (76,023)
    ↓ NER 추출 (GPT-5-nano, $47)
Events/Persons/Locations 추출
    ↓ 임포트
DB에 저장 + 연결
    ↓ 엔리치먼트 ($40)
품질 개선된 데이터
```

### 2.2 실제로 일어난 일

```
Source Documents (76,023)
    ↓ NER 추출 (GPT-5-nano, $47)
124,990 이벤트 추출됨
    ↓
    ↓ ← ⚠️ 여기서 문제 발생
    ↓
┌─────────────────────────────────────────────────────────────┐
│ import_sources_and_mentions.py                               │
│                                                              │
│ 로직:                                                        │
│   1. DB에 이미 있는 이벤트 목록 로드 (10,428개)               │
│   2. NER 추출 이벤트와 정확히 같은 이름만 매칭               │
│   3. 매칭 안 되면 → 무시 (continue)                          │
│                                                              │
│ 결과:                                                        │
│   - 매칭된 이벤트: 910개 (0.7%)                              │
│   - 버려진 이벤트: 124,080개 (99.3%) ← $47 낭비             │
└─────────────────────────────────────────────────────────────┘
    ↓
DB Events: 10,428개 (출처 불명, 2025-12-31 임포트)
    - Wikipedia URL 있음: 557개
    - URL 없음: 9,871개
    - Source 연결: 910개만
    ↓ 엔리치먼트 ($40)
메타데이터 수정됨 (좌표, 연도 등)
    ↓
BUT: 소스 연결은 여전히 910개만
```

### 2.3 숫자 비교

| 항목 | NER 추출 | DB 저장 | 연결됨 |
|------|----------|---------|--------|
| Events | 124,990 | 10,428 | 910 |
| Persons | 465,338 | 285,750 | 232,623 |
| Locations | 442,957 | 38,244 | - |

### 2.4 근본 원인

**import_sources_and_mentions.py (line 260-262)**:
```python
entity_id = entity_map.get(name.lower())
if not entity_id:
    continue  # ← NER 결과를 DB에 추가하지 않고 그냥 무시!
```

**문제**:
1. DB의 events는 **별도 출처**(Wikipedia 등)에서 미리 채워져 있었음
2. NER 추출 결과는 **새 이벤트로 추가되지 않음**
3. 단순 이름 매칭으로 **대부분 연결 실패**
4. **$47 어치 NER 결과의 99%가 버려짐**

---

## 3. 엔리치먼트는 유효한가?

### 유효함:
- 10,428개 이벤트의 메타데이터는 수정됨
- 좌표, 연도, 카테고리 정확도 향상
- 테르모필레 → 그리스로 수정 등

### 문제:
- 그러나 이 10,428개가 **어디서 왔는지 불명확**
- 소스 문서와의 연결이 부실 (910개만)
- NER로 추출한 풍부한 데이터를 활용하지 못함

---

## 4. aggregated 데이터 상태

```
poc/data/integrated_ner_full/aggregated/
├── events.json      91,977건 (dedup 후)
├── persons.json     (미확인)
├── locations.json   (미확인)
└── periods.json     (미확인)
```

NER 추출 후 aggregation 과정에서 일부 데이터 손실 가능:
```json
// 샘플 - 너무 짧은 이름
"Battle"
"revolution"
"Treaty"
```

---

## 5. 해결 방안

### Option A: NER 결과 재임포트 (권장)

1. **NER 원본 데이터 사용** (minimal_batch_*_output.jsonl)
2. **이벤트를 DB에 직접 추가** (기존 무시하던 것들)
3. **중복 제거** 로직 추가
4. **Source 연결 생성**

```python
# 수정된 로직
for event in ner_extracted_events:
    existing = find_similar_event(event)  # fuzzy match
    if existing:
        link_to_source(existing, source_id)
    else:
        new_event = create_event(event)  # 새로 생성!
        link_to_source(new_event, source_id)
```

**예상 비용**: $0 (이미 추출된 데이터 활용)
**예상 결과**:
- Events: 10,428 → ~50,000+ (중복 제거 후)
- Source 연결: 910 → ~100,000+

### Option B: 기존 데이터 버리고 Track B로 재시작

1. events 테이블 초기화
2. Track B 파이프라인으로 처음부터 재처리
3. 76,023 문서 다시 처리

**예상 비용**: ~$50-80 (Track B 비용)
**문제**: 이미 쓴 $47 완전 버림

### Option C: 하이브리드

1. 기존 10,428 이벤트 유지 (엔리치먼트 적용됨)
2. NER 원본에서 추가 이벤트만 임포트
3. fuzzy matching으로 중복 방지

---

## 6. 권장 조치

### 즉시 해야 할 것

1. **Option A 진행**: NER 결과 재임포트
   - 이미 돈 쓴 데이터 살리기
   - 추가 비용 없음

2. **임포트 스크립트 수정**:
   ```python
   # AS-IS: 없으면 무시
   if not entity_id:
       continue

   # TO-BE: 없으면 새로 생성
   if not entity_id:
       entity_id = create_new_event(item, source_id)
   ```

3. **중복 제거 로직 추가**:
   - 이름 유사도 + 연도 + 위치로 판단
   - 95% 이상 유사 → 병합
   - 50% 미만 → 새로 생성

### 체크포인트

- [ ] CP-FIX-1: NER 원본 데이터 분석 (event 구조 확인)
- [ ] CP-FIX-2: 재임포트 스크립트 작성
- [ ] CP-FIX-3: 중복 제거 로직 구현
- [ ] CP-FIX-4: 테스트 임포트 (1개 배치)
- [ ] CP-FIX-5: 전체 재임포트
- [ ] CP-FIX-6: 결과 검증

---

## 7. 교훈

1. **임포트 전 데이터 검증 필수**
   - 추출 건수 vs 임포트 건수 비교
   - 연결 성공률 확인

2. **정확 매칭 대신 fuzzy 매칭**
   - 역사적 이벤트는 표기법이 다양함
   - "Battle of Marathon" = "Marathon, Battle of" = "마라톤 전투"

3. **파이프라인 설계 시 데이터 흐름 명확히**
   - 어디서 오는 데이터인지
   - 어디로 가는 데이터인지
   - 연결은 어떻게 되는지

---

## 8. 현재 상태 요약

| 항목 | 상태 |
|------|------|
| NER 비용 ($47) | ⚠️ 99% 낭비됨 |
| 엔리치먼트 비용 ($40) | ✅ 유효 (메타데이터 수정됨) |
| Source 연결 | ❌ 910/10,428 (8.7%) |
| 해결책 | Option A 권장 (재임포트) |
