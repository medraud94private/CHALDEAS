# Future Plan - 미래 계획 인덱스

**작성일**: 2026-01-28
**목적**: 당장 구현하지 않지만 나중에 진행할 계획들

---

## V3 로드맵 (road_to_v3 통합)

| 파일 | 설명 | 우선순위 |
|------|------|---------|
| [README.md](./README.md) | V3 전체 로드맵 | 참조 |
| [UNIFIED_HISTORICAL_UNIT.md](./UNIFIED_HISTORICAL_UNIT.md) | Event/Period 통합 모델 | 중 |
| [DATA_INGESTION_PIPELINE.md](./DATA_INGESTION_PIPELINE.md) | V3 데이터 진입 파이프라인 | 중 |
| [MULTIVERSE_DATA_MODEL.md](./MULTIVERSE_DATA_MODEL.md) | 역사+창작물 통합 (Universe) | 낮음 |
| [SYSTEM_GAPS_AND_SOLUTIONS.md](./SYSTEM_GAPS_AND_SOLUTIONS.md) | 검색, 성능, 품질관리 | 중 |
| [POST_EXTRACTION_TASKS.md](./POST_EXTRACTION_TASKS.md) | 추출 후 작업 체크리스트 | 참조 |
| [WIKIDATA_AUTO_ENRICHMENT.md](./WIKIDATA_AUTO_ENRICHMENT.md) | Wikidata 자동 보강 | 중 |
| [PERIOD_EXTRACTION_PLAN.md](./PERIOD_EXTRACTION_PLAN.md) | 시대/기간 추출 | 중 |

---

## 큐레이션 시스템

| 파일 | 설명 | 우선순위 |
|------|------|---------|
| [CURATION_AND_FGO_MASTER_PLAN.md](./CURATION_AND_FGO_MASTER_PLAN.md) | 큐레이션 & FGO 마스터 플랜 | 높음 (보류) |
| [CURATION_SYSTEM.md](./CURATION_SYSTEM.md) | AI 큐레이터 시스템 | 높음 (보류) |
| [OPEN_CURATION_VISION.md](./OPEN_CURATION_VISION.md) | 오픈 큐레이션 비전 | 중 |

---

## FGO 연동

| 파일 | 설명 | 우선순위 |
|------|------|---------|
| [FGO_DATA_LAYER_AND_SOURCES.md](./FGO_DATA_LAYER_AND_SOURCES.md) | FGO 데이터 레이어 | 중 |
| [FGO_MINI_CHALDEAS.md](./FGO_MINI_CHALDEAS.md) | FGO 미니 프로젝트 | 낮음 |
| [FGO_SERVANT_BOOK_MAPPING.md](./FGO_SERVANT_BOOK_MAPPING.md) | 서번트-책 매핑 | 중 |

---

## 스토리 & 시각화

| 파일 | 설명 | 우선순위 |
|------|------|---------|
| [STORY_CURATION_SYSTEM.md](./STORY_CURATION_SYSTEM.md) | 스토리 큐레이션 | 중 |
| [STORY_IMPLEMENTATION.md](./STORY_IMPLEMENTATION.md) | 스토리 구현 | 중 |
| [GLOBE_VISUALIZATION_V2.md](./GLOBE_VISUALIZATION_V2.md) | Globe V2 시각화 | 낮음 |

---

## Wikidata/데이터 파이프라인

| 파일 | 설명 | 우선순위 |
|------|------|---------|
| [WIKIDATA_ENRICHMENT_ROADMAP.md](./WIKIDATA_ENRICHMENT_ROADMAP.md) | Wikidata 보강 로드맵 | 중 |
| [WIKIDATA_FACTGRID_EXPANSION.md](./WIKIDATA_FACTGRID_EXPANSION.md) | Wikidata FactGrid 확장 | 낮음 |
| [WIKIDATA_PIPELINE.md](./WIKIDATA_PIPELINE.md) | Wikidata 파이프라인 | 중 |

---

## V2 (사용자 데이터)

| 파일 | 설명 | 우선순위 |
|------|------|---------|
| [FGO_DATA_ENHANCEMENT.md](./FGO_DATA_ENHANCEMENT.md) | FGO 데이터 강화 | 중 |
| [USER_DATA_CONTRIBUTION.md](./USER_DATA_CONTRIBUTION.md) | 사용자 데이터 기여 | 낮음 |
| [USER_DATA_PIPELINE_DESIGN.md](./USER_DATA_PIPELINE_DESIGN.md) | 사용자 데이터 파이프라인 | 낮음 |

---

## 이번 대개선에 통합된 항목

다음 항목들은 `event_hierarchy/`에 통합됨:

| 원본 | 통합 위치 |
|------|----------|
| `HIERARCHICAL_LOCATION_SYSTEM.md` | `event_hierarchy/10_LOCATION_HIERARCHY.md` |
| `UNIFIED_HISTORICAL_UNIT.md` 일부 | `event_hierarchy/01_SCHEMA.md` |
| `PERIOD_EXTRACTION_PLAN.md` 일부 | `event_hierarchy/00_OVERVIEW.md` (Level 0-1) |

---

## 우선순위 정의

| 레벨 | 설명 |
|------|------|
| 높음 | 핵심 기능, 사용자 요청 많음 |
| 중 | 유용하지만 급하지 않음 |
| 낮음 | Nice to have |
| 보류 | 대규모 작업, 시간 필요 |
