# Story 기능 구현

> **작성일**: 2026-01-12
> **상태**: 인프라 완료 / 콘텐츠 미구현
> **목표**: Person Story 기능 MVP 구현 (잔 다르크 쇼케이스)

---

## ⚠️ 현재 상태 명확화

| 구분 | 상태 | 설명 |
|------|------|------|
| **UI 인프라** | ✅ 완료 | StoryModal, StoryGlobe, CSS |
| **API 인프라** | ✅ 완료 | /story/person/{id} 엔드포인트 |
| **내러티브 콘텐츠** | ❌ 미구현 | 큐레이터 AI가 작성하는 스토리 텍스트 |
| **출처 인용** | ❌ 미구현 | 1차 사료 연결 |
| **Curator AI** | ❌ 미구현 | 스토리 생성 파이프라인 |

**현재 UI는 DB의 raw event 데이터만 보여줌. 실제 "스토리"는 없음.**

→ 콘텐츠 시스템 설계: `docs/planning/STORY_CURATION_SYSTEM.md`

---

## 구현 원칙

- 기존 코드 간섭 최소화
- 새 파일/폴더로 독립적 구현
- 단계별 체크리스트 완료 후 다음 단계 진행

---

## Phase 1: Backend API

### 1.1 Story 라우터 생성

- [ ] `backend/app/api/v1/story.py` 생성
- [ ] `GET /api/v1/story/person/{person_id}` 엔드포인트
- [ ] 응답 스키마 정의

**응답 구조:**
```json
{
  "person": {
    "id": 85,
    "name": "Joan of Arc",
    "name_ko": "잔 다르크",
    "birth_year": 1412,
    "death_year": 1431
  },
  "nodes": [
    {
      "order": 0,
      "event_id": 123,
      "title": "Birth at Domrémy",
      "title_ko": "도미레미 출생",
      "year": 1412,
      "location": {
        "name": "Domrémy",
        "lat": 48.44,
        "lng": 5.67
      },
      "node_type": "birth"
    }
  ],
  "map_view": {
    "center": { "lat": 48.5, "lng": 2.5 },
    "zoom": 6
  }
}
```

### 1.2 라우터 등록

- [ ] `backend/app/api/v1/__init__.py`에 story 라우터 추가
- [ ] `backend/app/main.py`에서 라우터 등록 확인

### 1.3 테스트

- [ ] API 직접 호출 테스트 (`/api/v1/story/person/85`)
- [ ] 잔 다르크 데이터 확인

---

## Phase 2: Frontend 컴포넌트

### 2.1 Story 컴포넌트 폴더 구조

- [ ] `frontend/src/components/story/` 폴더 생성
- [ ] `StoryModal.tsx` - 메인 모달 컨테이너
- [ ] `StoryMap.tsx` - 지도 위 노드 표시
- [ ] `StoryPanel.tsx` - 현재 노드 정보 패널
- [ ] `StoryControls.tsx` - 재생/이전/다음 컨트롤
- [ ] `story.css` - 스타일

### 2.2 API 연동

- [ ] `frontend/src/api/story.ts` - API 호출 함수
- [ ] React Query 또는 fetch 사용

### 2.3 StoryModal 구현

- [ ] 풀스크린 모달 레이아웃
- [ ] ESC 키로 닫기
- [ ] 배경 클릭으로 닫기

### 2.4 StoryMap 구현

- [ ] react-globe.gl 또는 별도 맵 사용
- [ ] 노드 마커 표시
- [ ] 노드 간 연결선
- [ ] 현재 노드 하이라이트

### 2.5 StoryControls 구현

- [ ] 이전/다음 버튼
- [ ] 자동 재생 버튼
- [ ] 진행 표시 (● ○ ○ ★ ○)

---

## Phase 3: 연결

### 3.1 진입점 추가

- [ ] 인물 상세 패널에 "Story 보기" 버튼 추가
- [ ] 버튼 클릭 시 StoryModal 열기

### 3.2 상태 관리

- [ ] Story 모달 열림/닫힘 상태
- [ ] 현재 선택된 인물 ID 전달

---

## Phase 4: 검증

- [ ] 잔 다르크 Story 전체 흐름 테스트
- [ ] 다른 인물 (나폴레옹 등) 테스트
- [ ] 모바일 반응형 확인

---

## 현재 진행 상황

| 단계 | 상태 | 비고 |
|------|------|------|
| Phase 1.1 | ✅ 완료 | `backend/app/api/v1/story.py` 생성 |
| Phase 1.2 | ✅ 완료 | `router.py`에 등록 |
| Phase 1.3 | ✅ 완료 | 문법 검증 완료 |
| Phase 2.1 | ✅ 완료 | Story 컴포넌트 폴더 생성 |
| Phase 2.2 | ✅ 완료 | API 클라이언트에 storyApi 추가 |
| Phase 2.3 | ✅ 완료 | StoryModal.tsx 구현 |
| Phase 2.4 | ✅ 완료 | StoryGlobe.tsx - react-globe.gl 지도 통합 |
| Phase 3.1 | ✅ 완료 | PersonDetailView에 버튼 추가 |
| Phase 4 | ✅ 완료 | 프론트엔드 빌드 테스트 통과 |

### 생성된 파일

**Backend:**
- `backend/app/api/v1/story.py` - Story API
  - `GET /api/v1/story/person/{person_id}` - Person Story
  - `GET /api/v1/story/person/{person_id}/check` - 데이터 유무 확인

**Frontend:**
- `frontend/src/components/story/StoryModal.tsx` - 풀스크린 스토리 모달
- `frontend/src/components/story/StoryGlobe.tsx` - 3D 지구본 지도 (react-globe.gl)
- `frontend/src/components/story/story.css` - 스토리 스타일
- `frontend/src/components/story/index.ts` - export

**수정된 파일:**
- `backend/app/api/v1/router.py` - story 라우터 등록
- `frontend/src/api/client.ts` - storyApi 추가
- `frontend/src/components/detail/PersonDetailView.tsx` - Story 버튼 + 모달 추가
- `frontend/src/components/detail/EntityDetailView.css` - 버튼 스타일 추가

---

## 참고

- 기획서: `docs/planning/JOAN_OF_ARC_SHOWCASE.md`
- Person Chain 파이프라인: `poc/scripts/build_event_chains.py`
