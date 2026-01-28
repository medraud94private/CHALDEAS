# 2026-01-19 다음 단계

## 완료된 작업 (오늘)

### 1. 데이터 파이프라인 ✅
| 항목 | 수치 |
|------|------|
| Persons | 286,609 (connected: 222,418) |
| Events | 46,704 (connected: 43,214) |
| Locations | 40,613 (connected: 9,736) |
| Sources | 88,793 (with content: 87,961) |
| Total Relationships | 2,700,534 |

### 2. 관계 강도 시스템 ✅
- `connection_count` 컬럼 추가 (고아 필터링)
- `strength` 계산 및 API 노출
- 프론트엔드 강도 표시 (바 + 색상)

### 3. Compact DB 관리 ✅
- Full: 5,040 MB → Compact: 1,606 MB (68% 절감)
- `scripts/create-compact-db.py` 생성
- API 호환성 유지 (`include_orphans` 파라미터)

---

## 오늘 할 수 있는 작업

### Option A: 프로덕션 배포 🚀
**예상 작업**: 1-2시간
```
1. Compact DB 생성 실행
2. Cloud SQL에 덤프 업로드
3. Cloud Run 배포 확인
```
**효과**: 사용자에게 최신 데이터 제공

---

### Option B: Story Curation 시스템 📖
**예상 작업**: 4-6시간
```
1. Story 테이블 설계 (story_nodes, story_content)
2. Curator AI 파이프라인 (GPT-5-nano)
3. 1차 사료 인용 연동
4. StoryModal UI 연결
```
**효과**: "역사의 고리" 핵심 기능 구현

---

### Option C: Globe V2 개선 🌍
**예상 작업**: 3-4시간
```
1. 다중 좌표 이벤트 지원
2. 시간 기반 애니메이션
3. 지역 폴리곤 표시
```
**효과**: 시각적 임팩트 향상

---

### Option D: Timeline 성능 최적화 ⚡
**예상 작업**: 2-3시간
```
1. 가상화 스크롤 구현
2. 청크 로딩
3. 메모이제이션
```
**효과**: 대량 데이터 부드러운 스크롤

---

### Option E: 데이터 품질 개선 🔧
**예상 작업**: 2-3시간
```
1. Location 고아율 개선 (76% → 50% 목표)
2. 오탐 정리 (일반 명사 패턴)
3. 시대 기반 관계 분류
```
**효과**: 검색/탐색 품질 향상

---

## 추천 우선순위

1. **Option A (배포)** - 빠른 피드백
2. **Option B (Story)** - 핵심 가치
3. **Option D (Timeline)** - 사용성

## 관련 문서

- `STORY_CURATION_SYSTEM.md` - Story 설계
- `GLOBE_VISUALIZATION_V2.md` - Globe 개선
- `TIMELINE_PERFORMANCE.md` - 성능 최적화
- `DATABASE_SIZE_MANAGEMENT.md` - DB 관리
