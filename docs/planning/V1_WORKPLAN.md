# V1 작업 계획

**작성일**: 2026-01-10
**최종 수정**: 2026-01-10

---

## 현재 상태

### 완료된 작업
- [x] Phase 1: V0 이벤트 엔리치먼트 ($39.52)
- [x] Phase 2: NER 이벤트 엔리치먼트 + Reconciliation ($157.42)
- [x] Phase 3: Locations + Persons 엔리치먼트 ($69.51)
- **총 비용**: $266.45

### DB 현황
```
Events: 48,513개 (활성)
├── V0 기존: 10,428개
├── NER 신규: 38,085개
└── Source 연결: 81.6%

Locations: 40,613개
├── 좌표: 100%
├── country: 90.6%
└── region: 90.7%

Persons (mention >= 3): 21,963명
├── birth_year: 55.7%
├── death_year: 56.1%
└── role: 100%
```

---

## Phase 4: V1 API 구현

### CP-4.1 Globe API ✅ (이미 구현됨)
- [x] `/api/v1/globe/markers` - 마커 조회 (type, 연도, bounds 필터)
- [x] `/api/v1/globe/markers/stats` - 마커 통계
- [x] `/api/v1/globe/markers/density` - 시대별 밀도 (히트맵)
- [x] `/api/v1/globe/clusters` - 줌아웃용 클러스터
- [x] `/api/v1/globe/connections/{type}/{id}` - 엔티티 연결

### CP-4.2 Search API ✅ (이미 구현됨)
- [x] `/api/v1/search` - 통합 검색 (events, persons, locations)
- [x] `/api/v1/search/basic` - BM25 키워드 검색
- [x] `/api/v1/search/advanced` - AI 기반 고급 검색
- [x] `/api/v1/search/date-location` - 시공간 검색

### CP-4.3 Detail API ✅ (이미 구현됨)
- [x] `/api/v1/events` - 이벤트 목록
- [x] `/api/v1/persons` - 인물 목록
- [x] `/api/v1/locations` - 위치 목록
- [ ] 상세 조회 엔드포인트 추가 (/{id} 라우트)
- [ ] 연관 데이터 조회 기능 보강

### CP-4.4 Statistics API ✅
- [x] `/api/v1/globe/markers/stats` - 기본 마커 통계
- [x] `/api/v1/stats/overview` - 전체 DB 통계
- [x] `/api/v1/stats/timeline` - 연도별 분포
- [x] `/api/v1/stats/geography` - 지역별 분포
- [x] `/api/v1/stats/categories` - 카테고리별 분포
- [x] `/api/v1/stats/enrichment` - 엔리치먼트 현황

---

## Phase 5: Frontend 연동

### CP-5.1 Globe 데이터 연결
- [ ] Globe API 호출 연동
- [ ] 마커 클러스터링 (대량 데이터 처리)
- [ ] 연도 필터 슬라이더 연동
- [ ] 테스트: 성능 (10K+ 마커)

### CP-5.2 검색 UI
- [ ] 검색창 + 자동완성
- [ ] 필터 패널 (연도, 지역, 타입)
- [ ] 검색 결과 목록
- [ ] 결과 클릭 시 Globe 이동

### CP-5.3 상세 패널
- [ ] 이벤트 상세 패널
- [ ] 인물 상세 패널
- [ ] 위치 상세 패널
- [ ] 연관 항목 네비게이션

---

## Phase 6: 데이터 품질 검증

### CP-6.1 샘플링 검토
- [ ] 이벤트 100개 랜덤 샘플링 → 정확도 검증
- [ ] 인물 50명 랜덤 샘플링 → birth/death 정확도
- [ ] 위치 50개 랜덤 샘플링 → country/region 정확도
- [ ] 오류율 측정 및 문서화

### CP-6.2 이상치 탐지
- [ ] 연도 범위 이상 (< -5000 또는 > 2030)
- [ ] 좌표 이상 (lat > 90, lon > 180)
- [ ] 중복 데이터 탐지
- [ ] 수정 스크립트 작성

### CP-6.3 커버리지 분석
- [ ] 시대별 이벤트 분포 분석
- [ ] 지역별 커버리지 분석
- [ ] 데이터 공백 식별 → 추가 수집 계획

---

## Phase 7: Historical Chain 생성

### CP-7.1 Person Story
- [ ] 주요 인물 선정 (mention >= 50)
- [ ] 생애 이벤트 타임라인 생성
- [ ] LLM 기반 스토리 생성
- [ ] 테스트: 3명 파일럿

### CP-7.2 Place Story
- [ ] 주요 장소 선정 (이벤트 >= 100)
- [ ] 장소 역사 타임라인 생성
- [ ] LLM 기반 스토리 생성
- [ ] 테스트: 3곳 파일럿

### CP-7.3 Era Story
- [ ] 시대 구분 정의
- [ ] 시대별 주요 이벤트/인물/장소 집계
- [ ] LLM 기반 시대 개요 생성

### CP-7.4 Causal Chain
- [ ] 인과관계 추출 로직
- [ ] 이벤트 간 연결 그래프
- [ ] 시각화 데이터 생성

---

## 우선순위 및 순서

```
Phase 4 (V1 API) → Phase 5 (Frontend) → Phase 6 (품질검증) → Phase 7 (Chain)
```

### 예상 소요
| Phase | 예상 작업량 | 비용 |
|-------|-----------|------|
| Phase 4 | API 10개 | $0 |
| Phase 5 | 컴포넌트 5개 | $0 |
| Phase 6 | 검증 스크립트 | $0 |
| Phase 7 | LLM 생성 | ~$20-50 |

---

## 변경 이력

| 날짜 | 내용 |
|-----|------|
| 2026-01-10 | 문서 생성, Phase 4-7 계획 수립 |
| 2026-01-10 | Phase 4 검토: 대부분 이미 구현됨, Stats API 추가 |
