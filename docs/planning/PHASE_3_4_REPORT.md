# Phase 3-4 POC 보고서: Person Story 검증

**작성일**: 2026-01-08
**작성자**: Claude Code
**상태**: POC 완료, 다음 단계 대기

---

## 1. 배경 및 방향 전환

### 기존 접근 (Bottom-up)
```
NER 추출 → 매칭/중복제거 → 엔리치먼트 → 임포트 → 체인 생성
```

**문제점**:
- 매칭 정확도 저조 (AI 검증 후 3/44만 승인, **93% 거부**)
- 엔리치먼트 비용 부담 (9,518개 고아 이벤트)
- 최종 목표(Historical Chain)와의 연결 불명확

### 변경된 접근 (Top-down)
```
체인 생성 먼저 시도 → 필요한 데이터만 선별적 보강
```

**장점**:
- 핵심 기능(Person Story 등) 먼저 검증
- 비용 효율적 (필요한 데이터만 처리)
- 빠른 피드백 루프

---

## 2. Person Story POC 결과

### 테스트 대상: 알렉산더 대왕

| 항목 | 값 |
|-----|---|
| Person ID | 22 |
| 생몰년 | BC 356 ~ BC 323 |
| 모델 | gemma2:9b-instruct-q4_0 |
| 처리 시간 | ~15초 |

### 3단계 이벤트 분류 시스템

| 카테고리 | 조건 | 용도 | 건수 |
|---------|------|------|-----|
| **direct_period** | 직접 언급 + 시대 맞음 | 최우선 (핵심 이벤트) | 26개 |
| **direct_other** | 직접 언급 + 시대 안맞음 | 참조 (후대 기록/아티클) | 24개 |
| **context_only** | 언급 없음 + 시대/공간 맞음 | 참조 (동시대 배경) | 13개 |

### LLM 선별 Key Events

gemma2가 26개 중 선별한 핵심 전투:

| 순위 | 이벤트 | 연도 | 평가 |
|-----|--------|-----|------|
| 1 | Battle of the Granicus | BC 334 | 정확 - 첫 대규모 전투 |
| 2 | Battle of Issus | BC 333 | 정확 - 다리우스 첫 패배 |
| 3 | Battle of Gaugamela | BC 331 | 정확 - 페르시아 결정타 |
| 4 | Siege of Tyre | BC 332 | 정확 - 전략적 중요성 |
| 5 | Battle of the Hydaspes | BC 326 | 정확 - 동방 최대 전투 |

**평가**: 역사학적으로 합의된 알렉산더 5대 전투와 완벽 일치

### 생성된 Life Phases

```
1. Early Life (356-336 BCE): 아리스토텔레스 교육, 리더십 형성
2. Conquest of Persia (336-330 BCE): 그라니코스→이소스→가우가멜라
3. Eastern Expansion (330-327 BCE): 중앙아시아, 인도 정복
4. Return to Babylon (327-323 BCE): 귀환, 바빌론 정착, 사망
```

**평가**: 표준 역사서술과 일치

---

## 3. 발견된 데이터 품질 문제

### 문제 1: 이벤트 vs 아티클 혼재

`events` 테이블에 두 가지 다른 유형의 데이터가 혼재:

| 유형 | 예시 | date_start 의미 |
|-----|------|----------------|
| **실제 이벤트** | Battle of Gaugamela | 사건 발생일 (-331) |
| **아티클/기사** | "Alexander the Great as a God" | 기사 주제의 시대 (-356~-323) |

**영향**:
- 연도 범위 쿼리만으로는 관련 이벤트 필터링 불가
- date_start가 "주제의 시대"로 입력된 경우 다수

### 문제 2: 중복 이벤트

동일 이벤트가 여러 건으로 등록:
- Siege of Tyre: ID 31064, 9932, 10821 (3건 중복)
- Battle of Chaeronea: ID 4546, 101, 3055, 57 (4건 중복)

### 해결 방향

현재 3단계 분류로 우회 해결:
1. **직접 언급 + 시대 매칭**으로 1차 필터
2. 아티클은 자동으로 `direct_other`로 분류
3. 향후 `article` vs `event` 구분 필드 추가 검토

---

## 4. 엔리치먼트 모델 추적 시스템

### 추가된 필드 (Migration 002)

**events 테이블**:
```sql
enriched_by VARCHAR(100)      -- 모델명 (예: gemma2:9b, gpt-5.1)
enriched_at TIMESTAMP         -- 처리 일시
enrichment_version VARCHAR(50) -- 파이프라인 버전 (예: v1.0, v2.0)
```

**persons 테이블**:
```sql
enriched_by VARCHAR(100)
enriched_at TIMESTAMP
enrichment_version VARCHAR(50)
```

**locations 테이블**:
```sql
geocoded_by VARCHAR(100)      -- 지오코딩 서비스 (예: pleiades, gpt-5.1)
geocoded_at TIMESTAMP
```

**인덱스**:
- `idx_events_enriched_by`: 모델별 조회
- `idx_events_enrichment_version`: 버전별 조회

### 활용 시나리오

1. **모델 비교**: gemma2 vs gpt-5.1 결과 품질 비교
2. **점진적 개선**: 저비용 모델 → 고품질 모델 업그레이드
3. **버전 관리**: v1.0 → v2.0 파이프라인 변경 추적

---

## 5. 로컬 LLM 비교

| 모델 | 상태 | 속도 | 품질 | 비고 |
|-----|------|-----|-----|------|
| **gemma2:9b-instruct-q4_0** | 정상 | ~15초/건 | 양호 | 추천 |
| qwen3:8b | 실패 | - | - | thinking mode 이슈, 빈 응답 |
| gpt-5-nano (API) | 미테스트 | - | - | 비용 발생 |

---

## 6. 파일 목록

### 신규 생성

| 파일 | 설명 |
|-----|------|
| `poc/scripts/generate_person_story.py` | Person Story POC 스크립트 |
| `poc/data/stories/alexander_the_great_story.json` | 알렉산더 테스트 결과 |
| `backend/alembic/versions/002_add_enrichment_tracking.py` | 엔리치먼트 추적 마이그레이션 |

### 수정

| 파일 | 변경 내용 |
|-----|----------|
| `docs/logs/V1_WORKLOG.md` | Session 4 작업 로그 추가 |

---

## 7. 다음 단계 (Place/Era Story 구현 전 필요사항)

### 필수 작업

1. **공통 스토리 생성기 기반 구조 설계**
   - Person/Place/Era Story 공통 인터페이스
   - 이벤트 분류 로직 일반화

2. **SQLAlchemy 모델 V1 필드 정합성 확인**
   - locations, events 모델에 누락된 필드 확인
   - enrichment 필드 모델 반영

3. **중복 이벤트 처리 방안**
   - 동일 이벤트 그룹핑 로직
   - 대표 이벤트 선정 기준

### 선택 작업

4. **다른 인물 테스트** (나폴레옹, 카이사르)
   - 범용성 검증
   - 분류 로직 튜닝

5. **아티클 vs 이벤트 구분 필드 추가**
   - `is_article` 또는 `content_type` 필드
   - 기존 데이터 분류

---

## 8. 결론

### 검증된 사항

- **Top-down 접근 유효**: 체인 생성이 가능함을 확인
- **3단계 분류 효과적**: 데이터 품질 문제 우회
- **gemma2 사용 가능**: 로컬 모델로 충분한 품질
- **엔리치먼트 추적 준비 완료**: 향후 개선 시 비교 가능

### 다음 우선순위

```
1. 공통 기반 설계 → 2. Place Story 구현 → 3. Era Story 구현 → 4. API 통합
```

---

## 변경 이력

| 날짜 | 내용 |
|-----|------|
| 2026-01-08 | 초안 작성 |
