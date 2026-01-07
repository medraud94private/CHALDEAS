# Integrated NER Pipeline Design

**날짜**: 2026-01-05
**상태**: 설계 중

---

## 1. 개요

### 기존 방식 (2-Phase)
```
문서 → spaCy NER → 2M 엔티티 (노이즈 포함)
                 → Phase 2: 3-Tier 필터링 → LLM 검증
                 → 비용: ~$190
```

### 새 방식 (Integrated)
```
문서 → LLM 직접 NER (Structured Output)
     → 유효한 엔티티 + 년도/시대 정보
     → 비용: ~$35 (Batch API)
```

---

## 2. 비용 비교

| 항목 | 기존 방식 | 새 방식 |
|------|----------|---------|
| Phase 1 (NER) | spaCy (무료) | LLM ($35) |
| Phase 2 (검증) | LLM ($190) | 불필요 ($0) |
| **Total** | **~$190** | **~$35** |
| 절감률 | - | **82%** |

---

## 3. 핵심 설계

### 3.1 Structured Output Schema

```python
from pydantic import BaseModel
from typing import List, Optional

class ExtractedPerson(BaseModel):
    name: str                    # "Alexander the Great"
    role: Optional[str]          # "king", "philosopher", "general"
    birth_year: Optional[int]    # -356 (BCE는 음수)
    death_year: Optional[int]    # -323
    era: Optional[str]           # "Classical Antiquity"
    confidence: float            # 0.0 ~ 1.0

class ExtractedLocation(BaseModel):
    name: str                    # "Alexandria"
    location_type: Optional[str] # "city", "region", "country"
    modern_name: Optional[str]   # "Alexandria, Egypt"
    coordinates: Optional[tuple] # (31.2, 29.9)
    confidence: float

class ExtractedEvent(BaseModel):
    description: str             # "Battle of Gaugamela"
    year: Optional[int]          # -331
    year_precision: str          # "exact", "circa", "century", "unknown"
    persons_involved: List[str]  # ["Alexander", "Darius III"]
    locations_involved: List[str] # ["Gaugamela"]
    confidence: float

class DocumentExtraction(BaseModel):
    source_id: str
    persons: List[ExtractedPerson]
    locations: List[ExtractedLocation]
    events: List[ExtractedEvent]
    document_era: Optional[str]  # 문서 전체의 시대
    document_period: Optional[tuple]  # (start_year, end_year)
```

### 3.2 모델 폴백 전략

```
┌─────────────────┐
│   gpt-5-nano    │  $0.10/1M tokens (가장 저렴)
│   (1차 시도)     │
└────────┬────────┘
         │ 실패 시
         ▼
┌─────────────────┐
│   gpt-5-mini    │  $0.40/1M tokens
│   (2차 시도)     │
└────────┬────────┘
         │ 실패 시
         ▼
┌─────────────────────┐
│ gpt-5.1-chat-latest │  $2.50/1M tokens (가장 정확)
│   (3차 시도)         │
└─────────────────────┘
```

**폴백 조건**:
1. JSON 파싱 실패
2. Schema 불일치
3. 빈 결과 (문서에 내용이 있는데 추출 0개)
4. Confidence 평균 < 0.3

### 3.3 프롬프트 설계

```python
EXTRACTION_PROMPT = """
You are a historical entity extraction expert.
Extract persons, locations, and events from this historical document.

RULES:
1. Only extract clear, identifiable entities
2. Skip abbreviations, titles alone (Mr, Dr, St), partial names
3. For persons: include role/occupation if mentioned
4. For dates: use negative numbers for BCE (e.g., -490 for 490 BCE)
5. For uncertain dates: use year_precision field
6. Confidence: 1.0 = explicitly stated, 0.5 = inferred, 0.3 = uncertain

DOCUMENT:
{document_text}

Extract all historical entities following the schema.
"""
```

### 3.4 Batch API 처리 흐름

```
1. 문서 준비
   ├── 116,000개 문서 로드
   ├── 청크 분할 (문서 > 4000 tokens 시)
   └── JSONL 배치 파일 생성

2. Batch 제출
   ├── gpt-5-nano로 1차 처리
   ├── 24시간 이내 완료
   └── 50% 비용 할인

3. 결과 처리
   ├── 성공: 결과 저장
   ├── 실패: 폴백 모델로 재시도
   └── 최종 실패: 수동 검토 큐

4. 후처리
   ├── 엔티티 중복 제거 (이름 정규화)
   ├── 링킹 (같은 엔티티 병합)
   └── DB 저장
```

---

## 4. 추출 정보 상세

### 4.1 Person 추출 정보

| 필드 | 설명 | 예시 |
|------|------|------|
| name | 이름 | "Alexander the Great" |
| role | 역할/직업 | "King of Macedon" |
| birth_year | 출생년도 | -356 |
| death_year | 사망년도 | -323 |
| era | 시대 | "Hellenistic Period" |
| confidence | 확신도 | 0.9 |

### 4.2 Location 추출 정보

| 필드 | 설명 | 예시 |
|------|------|------|
| name | 이름 | "Alexandria" |
| location_type | 유형 | "city" |
| modern_name | 현대 이름 | "Alexandria, Egypt" |
| coordinates | 좌표 | (31.2, 29.9) |
| confidence | 확신도 | 0.95 |

### 4.3 Event 추출 정보

| 필드 | 설명 | 예시 |
|------|------|------|
| description | 설명 | "Battle of Gaugamela" |
| year | 년도 | -331 |
| year_precision | 정확도 | "exact" / "circa" / "century" |
| persons_involved | 관련 인물 | ["Alexander", "Darius III"] |
| locations_involved | 관련 장소 | ["Gaugamela"] |

### 4.4 Year Precision 값

| 값 | 의미 | 예시 |
|-----|------|------|
| exact | 정확한 년도 | "331 BCE" → -331 |
| circa | 대략 | "around 330 BCE" → -330 |
| decade | 10년 단위 | "330s BCE" → -335 |
| century | 세기 단위 | "4th century BCE" → -350 |
| period | 시대 | "Hellenistic period" → null |
| unknown | 불명 | "ancient times" → null |

---

## 5. 구현 계획

### Phase 1: 파일럿 (100개 문서)
- [ ] Structured Output 스키마 정의
- [ ] 프롬프트 최적화
- [ ] 폴백 로직 구현
- [ ] 품질 평가

### Phase 2: 소규모 테스트 (1,000개 문서)
- [ ] Batch API 테스트
- [ ] 비용/시간 측정
- [ ] 폴백 비율 확인

### Phase 3: 전체 적용 (116,000개 문서)
- [ ] Batch 분할 (API 한도 고려)
- [ ] 진행 상황 모니터링
- [ ] 결과 검증

---

## 6. 예상 결과

### 품질 향상
| 항목 | 기존 방식 | 새 방식 |
|------|----------|---------|
| 노이즈 비율 | ~40% | <5% |
| 년도 정보 | 없음 | 포함 |
| 시대 정보 | 없음 | 포함 |
| Context 활용 | 제한적 | 완전 |

### 비용/시간
| 항목 | 기존 방식 | 새 방식 |
|------|----------|---------|
| 비용 | ~$190 | ~$35 |
| 처리 시간 | 수일 | 24시간 (Batch) |
| 복잡도 | 높음 (3-Tier) | 낮음 (단일) |

---

## 7. 기존 방식 보존

기존 코드는 그대로 유지:
```
poc/scripts/phase2_pilot_*.py  # 3-Tier 파이프라인
poc/app/core/archivist.py      # 기존 NER
```

새 방식은 별도 디렉토리:
```
poc/scripts/integrated_ner/
├── schema.py              # Pydantic 스키마
├── extractor.py           # LLM 추출 로직
├── batch_processor.py     # Batch API 처리
├── fallback_handler.py    # 폴백 로직
└── pilot_test.py          # 파일럿 테스트
```

---

## 8. 리스크 및 대응

| 리스크 | 대응 |
|--------|------|
| LLM 환각 (없는 엔티티 생성) | Confidence 필터링, 후검증 |
| 긴 문서 처리 | 청크 분할, 중복 제거 |
| Batch API 실패 | 재시도 로직, 부분 저장 |
| 비용 초과 | 진행 중 비용 모니터링 |

---

## 9. 다음 단계

1. **즉시**: 100개 문서로 파일럿 테스트
2. **검증 후**: 1,000개 확대 테스트
3. **성공 시**: 전체 116,000개 적용
