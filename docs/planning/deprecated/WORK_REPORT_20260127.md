# 작업 보고서 (2026-01-27)

> 작성: Claude Code
> 시간: 오후 세션

---

## 1. 완료된 작업

### 1.1 백엔드 API 구현 (8100)

| API | 엔드포인트 | 상태 | 설명 |
|-----|-----------|------|------|
| Sources API | `/api/v1/sources` | ✅ 완료 | 75,151개 소스 조회 |
| | `/api/v1/sources/{id}` | ✅ 완료 | 소스 상세 (멘션 통계 포함) |
| | `/api/v1/sources/{id}/persons` | ✅ 완료 | 소스에 언급된 인물들 |
| | `/api/v1/sources/{id}/mentions` | ✅ 완료 | 멘션 컨텍스트 |
| Person Sources | `/api/v1/persons/{id}/sources` | ✅ 완료 | 인물이 언급된 책들 |
| Story API | `/api/v1/story/person/{id}` | ✅ 완료 | 인물 스토리 → 지도 노드 |

**새로 생성된 파일:**
- `backend/app/api/v1/sources.py`
- `backend/app/api/v1/story.py`
- `backend/app/services/source_service.py`

**수정된 파일:**
- `backend/app/api/v1/router.py` - persons, sources 라우터 추가
- `backend/app/api/v1/persons.py` - sources 엔드포인트 추가
- `backend/app/schemas/source.py` - 새 스키마 추가

### 1.2 문서 정리

**deprecated로 이동 (17개):**
- 날짜별 작업 계획 (2026-01-19_*.md)
- 완료된 파이프라인 문서 (WIKIDATA_*, WIKIPEDIA_*)
- 통합된 문서 (DATABASE_SIZE_MANAGEMENT, V1_WORKPLAN 등)

**유지 (18개 핵심 문서):**
- MASTER_PLAN.md (최상위)
- PIPELINE_GUIDE.md
- BOOK_INTEGRATION_STATUS.md
- CLEANUP_REPORT_20260127.md
- 기타 활성 문서

### 1.3 MASTER_PLAN.md 업데이트

추가된 섹션:
- **현재 시스템 아키텍처** - API 구조도
- **LLM 파이프라인** - gpt-5-nano 기반 추출 플로우
- **파이프라인 스크립트 위치**
- **문서 구조** - 카테고리별 정리

### 1.4 DB 현황 확인

| 테이블 | 개수 | 비고 |
|--------|------|------|
| sources | 88,903 | gutenberg: 105, document: 76,023 |
| text_mentions | - | 청크별 저장됨 |
| persons | 275,343 | QID 있음: 91,596 (33%) |

---

## 2. 진행 중인 작업

### 2.1 Book Extractor (8200)

```
상태: 실행 중
현재 책: The life and times of Cleopatra, Queen of Egypt
진행: 51/310 청크
남은 책: 102권
모델: Ollama (llama3.1:8b-instruct-q4_0)
```

**자동화 설정:**
- `auto_context: true` - 추출 후 컨텍스트 자동 생성
- `auto_db_match: true` - DB 자동 저장 (gutenberg 타입)

---

## 3. 다음 작업 (우선순위순)

### 3.1 프론트엔드 Sources UI [높음]

**목표:** 인물 상세 패널에 "관련 책" 탭 추가

```
PersonDetailPanel
├── 기본 정보 탭 (기존)
├── 관계 탭 (기존)
└── 📚 관련 책 탭 [NEW]
    ├── 언급된 책 목록
    ├── 멘션 수
    └── 컨텍스트 미리보기
```

**구현 항목:**
1. `frontend/src/components/detail/PersonSourcesTab.tsx` 생성
2. PersonDetailPanel에 탭 추가
3. API 연동 (`/api/v1/persons/{id}/sources`)

### 3.2 책 탐색 페이지 [중간]

**목표:** 전체 소스(책) 브라우징 UI

```
/sources (또는 /books)
├── 소스 목록 (페이지네이션)
├── 타입 필터 (gutenberg, document)
├── 검색
└── 소스 클릭 → 상세 모달
    ├── 책 정보
    ├── 언급된 인물 목록
    └── 멘션 컨텍스트
```

### 3.3 Story UI 개선 [중간]

**목표:** `/api/v1/story/person/{id}` 활용한 지도 시각화

- 인물 선택 → 생애 이벤트 노드로 표시
- 지도 위 경로 연결
- 타임라인 연동

### 3.4 Book Extractor 완료 후 검증 [낮음]

- 102권 추출 완료 확인
- DB에 gutenberg 타입으로 저장됐는지 확인
- text_mentions 청크 검증

---

## 4. 서버 현황

| 포트 | 서비스 | 상태 |
|------|--------|------|
| 5200 | Frontend (dev) | - |
| 8100 | Backend API | ✅ 실행 중 |
| 8200 | Book Extractor | ✅ 실행 중 (추출 작업 진행) |
| 11434 | Ollama | ✅ 실행 중 |
| 5432 | PostgreSQL | ✅ 실행 중 |

---

## 5. 주요 발견사항

1. **소스 타입 불일치**: 기존 데이터는 `document` 타입, 새 추출은 `gutenberg` 타입
   - 향후 타입 통일 또는 매핑 필요할 수 있음

2. **LLM 파이프라인 확인**: NER이 아닌 LLM(gpt-5-nano, Ollama) 기반
   - book_extractor는 Ollama 로컬 모델 사용
   - 서버 파이프라인은 OpenAI API 사용

3. **자동화 완성**: 책 추출 → 컨텍스트 → DB 저장까지 자동화됨

---

## 6. 다음 세션 시작 시

```bash
# 1. 서버 상태 확인
curl http://localhost:8100/docs  # Backend
curl http://localhost:8200/api/queue/status  # Book Extractor

# 2. Book Extractor 작업 완료 확인
# 브라우저: http://localhost:8200

# 3. Frontend 개발 시작
cd frontend && npm run dev -- --port 5200
```
