# CHALDEAS V1 Work Log

## 2026-01-11

### Session 5: Phase 7 Historical Chain 구현 완료

#### 핵심 개념 정립
- **Historical Chain ≠ Story 생성**: 이벤트 간 연결 그래프
- **소스 기반 연결**: 같은 소스가 언급하는 이벤트들이 연결됨
- **다층 방향성 그래프**: Person, Location, Causal, Thematic 레이어
- **시간 기반 방향성**: 후대 사건은 전대에 영향 불가

#### 완료 작업

1. **CP-7.1: 테이블 생성 및 체인 추출**
   - `event_connections` 테이블 생성 (마이그레이션 003)
   - `connection_sources` 테이블 생성
   - Person 체인: 36,905개 연결
   - Location 체인: 20,442개 연결
   - Causal 체인: 56,483개 연결
   - **총 113,830개 연결**

2. **CP-7.2: 강도 계산 공식**
   ```python
   source_factor = n * (1 + ln(n))^1.5
   # 1개 → 1.0, 5개 → 14.0, 10개 → 38.0, 50개 → 340.0
   ```
   - 기본 강도: person=10, location=5, causal=1, thematic=0.5
   - 자동 검증: strength >= 30 → auto_approved

3. **CP-7.3: 자동 검증**
   - auto_verified: 71,969개
   - unverified: 41,124개 (weak connections)

4. **CP-7.4: LLM 연결 유형 분류**
   - 대상: Causal 체인 중 strength >= 10 (1,029개)
   - 모델: gpt-5.1-chat-latest (100% 성공률)
   - 비용: ~$0.85
   - 분류 결과:
     - related: 381 (37%)
     - concurrent: 261 (25%)
     - follows: 210 (20%)
     - part_of: 113 (11%)
     - leads_to: 62 (6%)
     - causes: 2 (0.2%)

5. **CP-7.5: Chain API 구현**
   - CRUD: GET/POST/PUT/DELETE `/api/v1/chains/`
   - 이벤트별: `/api/v1/chains/event/{id}/connections`
   - 인물 체인: `/api/v1/chains/person/{id}`
   - 장소 체인: `/api/v1/chains/location/{id}`
   - 그래프 탐색: `/api/v1/chains/traverse`
   - 통계: `/api/v1/chains/stats`

#### 파일 변경
```
backend/alembic/versions/003_event_connections.py (신규)
backend/app/api/v1_new/chains.py (신규)
backend/app/api/v1_new/__init__.py (수정)
backend/app/main.py (수정)
poc/scripts/build_event_chains.py (신규)
poc/scripts/classify_connections.py (신규)
poc/scripts/test_connection_classify.py (신규)
docs/planning/PHASE7_HISTORICAL_CHAIN.md (전면 개정)
```

#### 비용 요약
- LLM 분류: $0.85
- **Phase 7 총 비용: $0.85**
- **프로젝트 누적 비용: $267.30** ($266.45 + $0.85)

---

## 2026-01-08

### Session 4: Person Story POC 및 데이터 품질 분석

#### 방향 전환
- 기존: Bottom-up (매칭 → 엔리치먼트 → 임포트)
- 변경: Top-down (체인 생성 먼저 시도 → 필요한 데이터만 보강)

#### 완료 작업

1. **데이터 품질 문제 발견**
   - events 테이블에 실제 이벤트와 아티클(기사)이 혼재
   - date_start가 "기사 주제의 시대"로 잘못 입력된 경우 다수
   - 연도 범위 쿼리만으로는 관련 이벤트 필터링 불가

2. **Person Story Generator POC** (`poc/scripts/generate_person_story.py`)
   - 3단계 이벤트 분류 구현:
     - `direct_period`: 직접 언급 + 시대 맞음 (최우선)
     - `direct_other`: 직접 언급 + 시대 안맞음 (참조-후대)
     - `context_only`: 언급 없지만 시대/공간 맞음 (참조-동시대)
   - gemma2:9b-instruct-q4_0 모델로 스토리 생성
   - 알렉산더 대왕 테스트 성공

3. **엔리치먼트 모델 추적 필드 추가** (마이그레이션 002 - 적용 완료)
   - `events`: enriched_by, enriched_at, enrichment_version
   - `persons`: enriched_by, enriched_at, enrichment_version
   - `locations`: geocoded_by, geocoded_at
   - 인덱스: idx_events_enriched_by, idx_events_enrichment_version

4. **로컬 LLM 테스트**
   - qwen3:8b: 빈 응답 문제 (thinking mode 이슈)
   - gemma2:9b: 정상 동작, 품질 양호, 속도 ~15초/건

#### 파일 변경
```
poc/scripts/generate_person_story.py (신규) - Person Story POC
poc/data/stories/alexander_the_great_story.json (신규) - 테스트 결과
backend/alembic/versions/002_add_enrichment_tracking.py (신규) - 마이그레이션
docs/logs/V1_WORKLOG.md (수정) - 작업 로그
```

#### 발견 사항
- 알렉산더 직접 관련 이벤트: 26개
- gemma2가 선택한 Key Events: Granicus, Issus, Gaugamela, Tyre, Hydaspes
- Phase 3-4 (체인 생성) 기본 구조 동작 확인

#### 다음 작업
- [ ] 다른 인물로 Person Story 테스트 (나폴레옹, 카이사르 등)
- [ ] Place Story, Era Story 구현
- [ ] 엔리치먼트 시 모델 정보 저장하도록 스크립트 수정
- [ ] 아티클 vs 이벤트 구분 방안 검토

---

## 2026-01-07

### Session 1: DB 임포트 및 Explore UI

#### 완료 작업
1. **엔티티 DB 임포트**
   - aggregated NER 데이터 → PostgreSQL
   - 330,657개 엔티티 (persons, locations, events, polities, periods)

2. **원문 및 멘션 임포트**
   - 76,023개 원문 문서 → sources 테이블
   - 595,146개 엔티티-문서 연결 → text_mentions 테이블
   - DB 사이즈: 1.6GB

3. **Explore API 구현**
   - `/explore/stats`, `/explore/persons`, `/explore/locations` 등
   - `/explore/sources`, `/explore/sources/{id}` 원문 조회
   - `/explore/entity/{type}/{id}/sources` 엔티티 출처 조회

4. **Explore UI 구현**
   - ExplorePanel 컴포넌트 (6개 탭)
   - Sources 탭 추가 (원문 브라우징)
   - 검색, 필터, 페이지네이션

5. **문서 작성**
   - `docs/planning/V1_PROGRESS_REPORT.md` - 진행 상황 정리
   - `docs/planning/V1_GLOBE_INTEGRATION_PLAN.md` - Globe 연동 기획

#### 다음 작업 (Phase 2)
- Pleiades 데이터 임포트 (고대 지명 좌표)
- Geocoding 스크립트 작성
- Globe 마커 시스템 구현

#### 이슈
- CLAUDE.md 포트 혼동 해결 (Docker 5433 → Native 5432)
- Python 캐시로 인한 서버 reload 문제 → 프로세스 강제 종료 필요

---

## 이전 세션 (2026-01-06)

### NER 배치 처리
- 76,000+ 문서에서 555K 엔티티 추출
- GPT-5-nano Batch API 사용
- 비용: ~$47

### V1 스키마 설계
- `docs/planning/REDESIGN_PLAN.md` 작성
- polities, historical_chains, chain_segments, text_mentions 테이블 설계
- Alembic 마이그레이션 실행

### Session 2: Globe API 및 좌표 보강

#### 완료 작업
1. **Pleiades 좌표 매핑**: 34,409개 locations 100% 완료
2. **Globe API** (`backend/app/api/v1_new/globe.py`):
   - `/globe/markers`, `/globe/markers/stats`, `/globe/markers/density`
   - `/globe/clusters`, `/globe/connections/{type}/{id}`
3. **events ↔ locations 조인**: primary_location_id로 좌표 조회
4. **사이드바 버그 수정**: All Eras → currentYear ± 500년
5. **CLAUDE.md**: 체크리스트 규칙 추가

#### API 통계
- 총 마커: 37,232 (events 2,823 + locations 34,409)
- 연도 범위: -10000 ~ 6794

---

### Session 3: 프론트엔드 Globe 연동 및 DB 스키마 수정

#### 완료 작업
1. **GlobeContainer 리팩토링** (`frontend/src/components/globe/GlobeContainer.tsx`):
   - 새 Globe API (`/globe/markers`) 연동
   - GlobeMarker 인터페이스 추가
   - 카테고리 기반 색상 매핑
   - 마커 사이즈 0.5 → 0.8 조정

2. **DB 스키마 수정** (locations 테이블):
   - V1 컬럼 누락 수정: `hierarchy_level`, `modern_parent_id`, `historical_parent_id`, `valid_from`, `valid_until`
   - SQLAlchemy 모델과 DB 스키마 불일치로 인한 500 에러 해결

3. **버그 수정**:
   - `/events` API 500 에러 → locations 테이블 컬럼 추가로 해결
   - 마커 색상 회색 → 카테고리별 색상 매핑
   - 사이드바/우측 패널 연동 복구

#### 이슈
- Alembic 마이그레이션 파일에 locations V1 컬럼이 누락되어 있었음
- 수동으로 DB에 컬럼 추가 필요 (향후 마이그레이션 업데이트 권장)

#### 다음 작업
- Timeline-Globe 완전 동기화 테스트
- 마커 클릭 → 우측 패널 연동 확인

---
