# CHALDEAS 계획 문서 인덱스

> 최종 업데이트: 2026-01-02

---

## 읽기 순서 (V1 기준)

### 1. 핵심 컨셉
| 문서 | 설명 |
|------|------|
| [HISTORICAL_CHAIN_CONCEPT.md](./HISTORICAL_CHAIN_CONCEPT.md) | "역사의 고리" 4가지 큐레이션 유형 |
| [METHODOLOGY.md](./METHODOLOGY.md) | 학술 참고자료 (CIDOC-CRM, Braudel 등) |

### 2. 시스템 설계
| 문서 | 설명 |
|------|------|
| [V1_ARCHITECTURE.md](./V1_ARCHITECTURE.md) | **핵심** - Ingestion/Query 레이어 분리 |
| [V1_PIPELINE.md](./V1_PIPELINE.md) | 텍스트 처리 파이프라인 상세 |
| [SYSTEM_OVERVIEW.md](./SYSTEM_OVERVIEW.md) | 유저 경험, 새 책 추가, 충돌 처리, 부트스트랩 |

### 3. 실행 계획
| 문서 | 설명 |
|------|------|
| [V1_WORKPLAN.md](./V1_WORKPLAN.md) | 체크포인트별 작업 계획 |
| [COST_ESTIMATION.md](./COST_ESTIMATION.md) | AI 호출 비용 산정 |
| [MODELS.md](./MODELS.md) | 사용 AI 모델 목록 |

---

## 문서 상태

### V1 문서 (현행)
| 문서 | 상태 | 설명 |
|------|------|------|
| V1_ARCHITECTURE.md | ✅ 현행 | Ingestion/Query 분리 아키텍처 |
| V1_PIPELINE.md | ✅ 현행 | NER + Chain 생성 파이프라인 |
| V1_WORKPLAN.md | ✅ 현행 | 체크포인트별 작업 |
| SYSTEM_OVERVIEW.md | ✅ 현행 | 사용자 설명용 종합 문서 |
| HISTORICAL_CHAIN_CONCEPT.md | ✅ 현행 | 핵심 컨셉 정의 |
| METHODOLOGY.md | ✅ 현행 | 학술 배경 |
| COST_ESTIMATION.md | ✅ 현행 | 비용 산정 |
| MODELS.md | ✅ 현행 | AI 모델 목록 |

### V0 문서 (레거시 - 참고용)
| 문서 | 상태 | 설명 |
|------|------|------|
| REDESIGN_PLAN.md | 📦 아카이브 | V1 초기 계획 (V1_ARCHITECTURE로 대체) |
| AI_PIPELINE.md | 📦 아카이브 | 기존 AI 파이프라인 (V1_PIPELINE으로 대체) |
| DATA_SOURCES.md | ⚠️ 참고용 | 데이터 소스 목록 (여전히 유효) |
| LOCATION_RESOLUTION.md | ⚠️ 참고용 | 위치 해상도 로직 (여전히 유효) |
| VISUALIZATION_FEATURES.md | ⚠️ 참고용 | 시각화 기능 (프론트엔드 참고) |
| FUTURE_FEATURES.md | 📦 아카이브 | 미래 기능 (V1에서 재검토) |

---

## 핵심 개념 요약

### 레이어 분리
```
┌─────────────────┐     ┌─────────────────┐
│ INGESTION       │     │ QUERY           │
│ (정보 수집)      │     │ (질문 응답)      │
│                 │     │                 │
│ • 오프라인 배치  │     │ • 실시간 요청    │
│ • Ollama (무료) │     │ • 캐시 활용      │
│ • 품질 우선     │     │ • 속도 우선      │
└────────┬────────┘     └────────┬────────┘
         │                       │
         └───────┬───────────────┘
                 ▼
         ┌─────────────┐
         │  DATABASE   │
         └─────────────┘
```

### 4가지 체인 유형
| 유형 | 예시 |
|------|------|
| person_story | "소크라테스의 생애" |
| place_story | "로마의 2000년" |
| era_story | "르네상스 시대" |
| causal_chain | "로마 멸망의 원인" |

### Braudel의 시간 스케일
| 스케일 | 기간 | 예시 |
|--------|------|------|
| événementielle | 일~년 | 마라톤 전투 |
| conjuncture | 수십년~세기 | 르네상스 |
| longue durée | 수세기~천년 | 지중해 무역 문화 |

---

## 관련 로그

- [../logs/V1_WORKLOG.md](../logs/V1_WORKLOG.md) - 작업 로그

---

## 정리 기록

### 2026-01-02
- INDEX.md 생성
- V1 문서 8개 현행으로 지정
- V0 문서 6개 아카이브/참고용으로 지정
- REDESIGN_PLAN.md → V1_ARCHITECTURE.md로 대체됨
- AI_PIPELINE.md → V1_PIPELINE.md로 대체됨
