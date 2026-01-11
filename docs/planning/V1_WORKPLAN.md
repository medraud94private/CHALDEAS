# V1 작업 계획

**작성일**: 2026-01-10
**최종 수정**: 2026-01-11

---

## 프로젝트 현황 요약

### 비용 총계
| Phase | 내용 | 비용 |
|-------|------|------|
| Phase 1 | V0 이벤트 엔리치먼트 | $39.52 |
| Phase 2 | NER 이벤트 + Reconciliation | $157.42 |
| Phase 3 | Locations + Persons 엔리치먼트 | $69.51 |
| Phase 7 | Historical Chain 분류 | $0.85 |
| Phase 8 | UI/UX 개선 (FGO 스타일) | $0.00 |
| **Total** | | **$267.30** |

### DB 현황 (2026-01-11)
```
Events: 48,513개
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

Event Connections: 113,830개
├── person: 36,905개
├── location: 20,442개
└── causal: 56,483개
```

---

## 완료된 작업 (Archive)

### Phase 1-3: 데이터 엔리치먼트 ✅
- [x] V0 이벤트 엔리치먼트
- [x] NER 이벤트 + Reconciliation
- [x] Locations + Persons 엔리치먼트
- **완료일**: 2026-01-10
- **비용**: $266.45

### Phase 4: V1 API 구현 ✅
- [x] Globe API (`/api/v1/globe/*`)
- [x] Search API (`/api/v1/search/*`)
- [x] Detail API (`/api/v1/events`, `/persons`, `/locations`)
- [x] Statistics API (`/api/v1/stats/*`)
- [x] Explore API (`/api/v1/explore/*`)
- **완료일**: 2026-01-08

### Phase 5: Frontend 연동 ✅
- [x] Globe 데이터 연결
- [x] 검색 및 필터 UI
- [x] 상세 패널 (EventDetail, Chat, Explore)
- [x] 타임라인 슬라이더
- **완료일**: 2026-01-08

### Phase 6: 데이터 품질 검증 ✅
- [x] 이상치 탐지 (좌표 0개, 연도 3개 OCR 오류)
- [x] 커버리지 분석
- [x] 품질 평가: **양호**
- **완료일**: 2026-01-10

### Phase 7: Historical Chain ✅
- [x] CP-7.1: 테이블 생성 및 체인 추출 (113,830개)
- [x] CP-7.2: 강도 계산 공식 구현
- [x] CP-7.3: 자동 검증 (71,969개 auto_verified)
- [x] CP-7.4: LLM 연결 유형 분류 (1,029개, $0.85)
- [x] CP-7.5: Chain API 구현 (CRUD + 탐색)
- **완료일**: 2026-01-11
- **비용**: $0.85

### Phase 8: UI/UX 개선 ✅
- [x] CP-8.1: 이벤트 카드 개선 (WHO/WHERE 메타데이터)
- [x] CP-8.2: 4대 요소 그리드 (WHEN/WHERE/WHO/WHAT)
- [x] CP-8.3: 상세 패널 탭 구조 (Overview/Connections)
- [x] CP-8.4: ChainPanel 재설계 (탭 기반 탐색)
- [x] CP-8.5: 사이드바 Chain 통계 섹션
- [x] CP-8.6: FGO 스타일 애니메이션
- **완료일**: 2026-01-11
- **비용**: $0 (프론트엔드 작업)
- **문서**: `docs/planning/PHASE8_UI_IMPROVEMENT.md`

---

## 진행 중 작업

*현재 진행 중인 작업 없음*

---

## 완료된 추가 작업

### Phase 9: Globe 연결선 시각화 ✅
- [x] CP-9.1: react-globe.gl arcs 연결선 구현
- [x] CP-9.2: 레이어별 색상 차별화 (Person: 금색, Location: 녹색, Causal: 핑크)
- [x] CP-9.3: 연결 강도에 따른 선 두께 (0.5~2.5)
- [x] CP-9.4: 이벤트 선택 시 연결선 표시 (API: `/globe/arcs/{event_id}`)
- [x] CP-9.5: 대시 애니메이션 + 호버 라벨
- [x] CP-9.6: Chain 네비게이션 (Prev/Next) 구현
- **완료일**: 2026-01-11
- **비용**: $0 (프론트엔드)

---

## 향후 작업 (Backlog)

### Phase 10: Person/Location 상세 뷰
- [ ] CP-10.1: Person 타임라인 뷰 (인물의 생애 이벤트)
- [ ] CP-10.2: Location 역사 뷰 (장소의 역사적 이벤트)
- [ ] CP-10.3: 연결된 인물/장소 그래프
- [ ] CP-10.4: 관련 이벤트 필터링
- **예상 비용**: $0 (기존 API 활용)
- **우선순위**: 높음

### Phase 11: UI 고도화
- [ ] CP-11.1: 필터 UI 개선 (고급 필터 접기/펼치기)
- [ ] CP-11.2: 반응형 디자인 (모바일/태블릿)
- [ ] CP-11.3: 키보드 네비게이션 (방향키 탐색)
- [ ] CP-11.4: 다크/라이트 모드 토글
- [ ] CP-11.5: 접근성 개선 (ARIA, 고대비)
- **예상 비용**: $0
- **우선순위**: 중간

### Phase 12: Curation System
- [ ] CP-12.1: 관리자 대시보드 UI
- [ ] CP-12.2: Pending 연결 검토 워크플로우 (41,124개)
- [ ] CP-12.3: 수동 연결 추가/수정/삭제
- [ ] CP-12.4: 연결 품질 리포트
- [ ] CP-12.5: LLM 추천 기반 큐레이션 보조
- **예상 비용**: $0~5 (LLM 추천 시)
- **우선순위**: 중간

### Phase 13: Story Generation
- [ ] CP-13.1: Person Story 생성 (인물 중심 내러티브)
- [ ] CP-13.2: Place Story 생성 (장소 중심 내러티브)
- [ ] CP-13.3: Era Story 생성 (시대 종합 내러티브)
- [ ] CP-13.4: 스토리 캐싱 및 재생성 시스템
- **예상 비용**: $10~30 (LLM 생성)
- **우선순위**: 낮음

### Phase 14: Advanced Features
- [ ] CP-14.1: 벡터 검색 (pgvector) 개선
- [ ] CP-14.2: AI 채팅 개선 (SHEBA 고도화)
- [ ] CP-14.3: 다국어 지원 확대 (한국어/일본어/중국어)
- [ ] CP-14.4: 실시간 협업 기능
- **예상 비용**: $5~20
- **우선순위**: 낮음

### Phase 15: 배포 및 운영
- [ ] CP-15.1: GCP Cloud Run 배포
- [ ] CP-15.2: CI/CD 파이프라인 (GitHub Actions)
- [ ] CP-15.3: 모니터링 및 로깅 (Cloud Monitoring)
- [ ] CP-15.4: 백업 및 복구 전략
- [ ] CP-15.5: CDN 및 성능 최적화
- **예상 비용**: $20~50/월 (운영)
- **우선순위**: 중간

---

## 기술 부채 (Tech Debt)

### 높은 우선순위
- [ ] OCR 오류 날짜 3건 수정 (6000, 4883, 4876)
- [ ] Causal 연결 55,454개 미분류 (strength < 10)
- [ ] API 에러 핸들링 강화

### 중간 우선순위
- [ ] Alembic 마이그레이션 정리
- [ ] API 문서 자동 생성 (OpenAPI)
- [ ] 테스트 코드 작성

### 낮은 우선순위
- [ ] 코드 리팩토링 (중복 제거)
- [ ] 로깅 시스템 개선
- [ ] 성능 최적화

---

## 참고 문서

| 문서 | 설명 |
|-----|------|
| `docs/logs/V1_WORKLOG.md` | 작업 로그 |
| `docs/logs/UI_IMPROVEMENT_LOG.md` | UI 개선 로그 |
| `docs/planning/PHASE7_HISTORICAL_CHAIN.md` | Phase 7 상세 설계 |
| `docs/planning/PHASE8_UI_IMPROVEMENT.md` | Phase 8 상세 설계 |
| `docs/concepts/HISTORICAL_CHAIN_CONCEPT.md` | 개념 설명 |
| `docs/architecture/V1_ARCHITECTURE.md` | 아키텍처 |

---

## 변경 이력

| 날짜 | 내용 |
|-----|------|
| 2026-01-10 | 문서 생성, Phase 4-7 계획 수립 |
| 2026-01-10 | Phase 4-6 완료 확인 |
| 2026-01-11 | Phase 7 완료, 향후 작업 정리, 기술 부채 추가 |
| 2026-01-11 | Phase 8 완료 (UI/UX 개선), Phase 9-15 상세 계획 추가 |
