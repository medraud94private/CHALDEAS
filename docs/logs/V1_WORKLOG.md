# CHALDEAS V1 Work Log

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
