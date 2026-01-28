# 책 데이터 통합 현황 및 개선 계획

> 작성일: 2026-01-27
> 상태: 진행 중

---

## 1. 현재 데이터 현황

### 1.1 DB 통계

| 테이블 | 레코드 수 | 설명 |
|--------|-----------|------|
| persons | 275,351 | 역사 인물 |
| locations | 40,613 | 장소 |
| events | 46,704 | 사건 |
| sources | 88,903 | 출처 (책, 문서) |
| text_mentions | 715,402 | 엔티티-출처 연결 |
| entity_aliases | 9,917 | 별명/이형 |

### 1.2 text_mentions 분포

| entity_type | 수량 | 비율 |
|-------------|------|------|
| person | 491,060 | 68.6% |
| location | 113,424 | 15.9% |
| event | 72,674 | 10.2% |
| period | 38,232 | 5.3% |
| polity | 12 | 0.0% |

### 1.3 sources 분포

| type | 수량 | 설명 |
|------|------|------|
| document | 76,023 | Wikidata/기타 문서 |
| digital_archive | 8,675 | 디지털 아카이브 |
| wikipedia | 4,095 | 위키피디아 |
| **gutenberg** | **105** | **구텐베르크 책** |
| primary | 4 | 1차 사료 |
| book | 1 | 책 |

### 1.4 처리 현황

| 단계 | 완료 | 진행 중 | 대기 |
|------|------|---------|------|
| Gutenberg ZIM 다운로드 | ✅ 80,000권 | - | - |
| LLM 엔티티 추출 | 166권 | 108권 | ~79,700권 |
| Context 역추적 | 166권 | 자동화 | - |
| DB 매칭 | 166권 | 자동화 | - |
| text_mentions 생성 | 51,849개 | 자동화 | - |

---

## 2. 현재 구현 상태

### 2.1 Backend

#### 모델 (구현됨 ✅)

```
backend/app/models/
├── person.py           # Person 모델
├── event.py            # Event 모델
├── location.py         # Location 모델
├── source.py           # Source 모델
└── v1/
    └── text_mention.py # TextMention, EntityAlias 모델 ✅
```

#### API (일부 구현)

| 엔드포인트 | 상태 | 설명 |
|-----------|------|------|
| GET /api/v1/persons | ✅ | 인물 목록 |
| GET /api/v1/persons/{id} | ✅ | 인물 상세 |
| GET /api/v1/persons/{id}/events | ✅ | 인물 관련 이벤트 |
| GET /api/v1/persons/{id}/relations | ✅ | 관련 인물 |
| **GET /api/v1/persons/{id}/sources** | ❌ | **인물 언급된 책** |
| **GET /api/v1/sources** | ❌ | **책 목록** |
| **GET /api/v1/sources/{id}** | ❌ | **책 상세** |
| **GET /api/v1/sources/{id}/persons** | ❌ | **책에 언급된 인물** |

### 2.2 Frontend

#### 컴포넌트 (일부 구현)

| 컴포넌트 | 상태 | 설명 |
|----------|------|------|
| EventDetailPanel | ✅ | 이벤트 상세 |
| WikiPanel | ✅ | 위키피디아 정보 |
| **SourcePanel** | ❌ | **출처(책) 표시 패널** |
| **BookList** | ❌ | **인물 관련 책 목록** |
| **MentionContext** | ❌ | **언급 context 표시** |

### 2.3 데이터 파이프라인

#### 구현됨 ✅

```
tools/book_extractor/
├── server.py           # Book Extractor v2 (8200 포트)
├── entity_matcher.py   # 엔티티 매칭
└── index.html          # 웹 UI

poc/scripts/cleanup/
├── extract_book_contexts.py  # Context 추출
├── match_books_local.py      # 로컬 DB 매칭
└── wikidata_search.py        # Wikidata 검색
```

#### 자동화 ✅

- 추출 완료 → Context 추출 → DB 매칭 → text_mentions 생성
- Book Extractor에서 후처리 자동 실행

---

## 3. 필요한 개선 사항

### 3.1 Backend API 추가 (우선순위: 높음)

#### 3.1.1 Sources API

```python
# backend/app/api/v1/sources.py

@router.get("")
async def list_sources(
    type: Optional[str] = None,  # gutenberg, wikipedia, etc.
    limit: int = 50,
    offset: int = 0,
):
    """책/출처 목록 조회"""

@router.get("/{source_id}")
async def get_source(source_id: int):
    """책 상세 정보"""

@router.get("/{source_id}/persons")
async def get_source_persons(source_id: int):
    """책에 언급된 인물 목록"""

@router.get("/{source_id}/mentions")
async def get_source_mentions(source_id: int):
    """책의 모든 엔티티 언급 (context 포함)"""
```

#### 3.1.2 Person Sources API

```python
# backend/app/api/v1/persons.py에 추가

@router.get("/{person_id}/sources")
async def get_person_sources(person_id: int):
    """인물이 언급된 책 목록 (context 포함)"""
    return {
        "person_id": person_id,
        "sources": [
            {
                "source_id": 123,
                "title": "The Lives of the Twelve Caesars",
                "type": "gutenberg",
                "mention_count": 47,
                "contexts": [
                    {"text": "Julius Caesar was a Roman general...", "confidence": 0.9}
                ]
            }
        ]
    }
```

### 3.2 Frontend 컴포넌트 추가 (우선순위: 중간)

#### 3.2.1 SourcePanel 컴포넌트

```tsx
// frontend/src/components/source/SourcePanel.tsx

interface SourcePanelProps {
  personId: number;
}

export function SourcePanel({ personId }: SourcePanelProps) {
  // 인물이 언급된 책 목록 표시
  // 각 책의 context snippet 표시
  // 클릭 시 책 상세 페이지로 이동
}
```

#### 3.2.2 BookDetailPage 컴포넌트

```tsx
// frontend/src/pages/BookDetailPage.tsx

// 책 정보 표시
// 언급된 인물/장소/사건 목록
// 원문 context snippets
```

### 3.3 검색 기능 확장 (우선순위: 중간)

현재 검색은 persons/events/locations만 검색. sources도 추가 필요.

```python
# backend/app/api/v1/search.py 수정

@router.get("")
async def search(
    q: str,
    type: Optional[str] = None,  # person, event, location, source
):
    # sources 검색 추가
    if type in [None, "source"]:
        sources = search_sources(q)
```

### 3.4 데이터 품질 개선 (우선순위: 낮음)

1. **매칭률 개선**: 현재 44.7% → 목표 60%+
   - 흔한 이름(Richard, John 등) 특별 처리
   - context 기반 disambiguation 강화

2. **Wikidata 보강**: 나머지 ~90,000 persons
   - 한글명 추가
   - 생몰년 보강

3. **검토 큐**: 낮은 신뢰도 매칭 수동 검토

---

## 4. 구현 계획

### Phase 1: Backend API (1-2일)

| 작업 | 파일 | 예상 시간 |
|------|------|----------|
| Sources API 생성 | `backend/app/api/v1/sources.py` | 2시간 |
| Source Service 생성 | `backend/app/services/source_service.py` | 2시간 |
| Source Schema 생성 | `backend/app/schemas/source.py` | 1시간 |
| Person Sources 추가 | `backend/app/api/v1/persons.py` | 1시간 |
| 라우터 등록 | `backend/app/api/v1/router.py` | 30분 |
| 테스트 | - | 1시간 |

### Phase 2: Frontend 컴포넌트 (2-3일)

| 작업 | 파일 | 예상 시간 |
|------|------|----------|
| API 클라이언트 | `frontend/src/api/sources.ts` | 1시간 |
| SourcePanel | `frontend/src/components/source/SourcePanel.tsx` | 3시간 |
| BookDetailPage | `frontend/src/pages/BookDetailPage.tsx` | 4시간 |
| 라우팅 추가 | `frontend/src/App.tsx` | 30분 |
| PersonDetail 통합 | 기존 컴포넌트 수정 | 2시간 |

### Phase 3: 검색 확장 (1일)

| 작업 | 파일 | 예상 시간 |
|------|------|----------|
| 검색 API 수정 | `backend/app/api/v1/search.py` | 2시간 |
| 검색 UI 수정 | `frontend/src/components/search/*` | 2시간 |

---

## 5. 예상 결과 (구현 후)

### 5.1 사용 시나리오

**시나리오 1: 인물 상세 페이지**
```
Napoleon Bonaparte 페이지
├── 기본 정보 (생몰년, biography)
├── 관련 이벤트
├── 관련 인물
└── 📚 언급된 책 (NEW)
    ├── A Life of Napoleon Bonaparte (47회 언급)
    │   └── "Napoleon led his army across the Alps..."
    ├── The History of France (23회 언급)
    └── ...
```

**시나리오 2: 책 상세 페이지**
```
The Lives of the Twelve Caesars 페이지
├── 책 정보 (저자, 출판년도)
├── 언급된 인물 (89명)
│   ├── Julius Caesar (47회)
│   ├── Augustus (35회)
│   └── ...
├── 언급된 장소 (23개)
└── 언급된 사건 (15개)
```

**시나리오 3: 검색**
```
검색: "caesar"

결과:
├── 인물: Julius Caesar, Augustus Caesar...
├── 이벤트: Assassination of Caesar...
└── 📚 책: The Lives of the Twelve Caesars... (NEW)
```

### 5.2 쿼리 예시

```sql
-- 나폴레옹이 언급된 책들
SELECT s.title, COUNT(*) as mentions
FROM text_mentions tm
JOIN sources s ON tm.source_id = s.id
JOIN persons p ON tm.entity_id = p.id
WHERE tm.entity_type = 'person'
  AND p.wikidata_id = 'Q517'
GROUP BY s.id
ORDER BY mentions DESC;

-- 특정 책에 언급된 인물들
SELECT p.name, COUNT(*) as mentions,
       array_agg(DISTINCT tm.mention_text) as aliases
FROM text_mentions tm
JOIN persons p ON tm.entity_id = p.id
WHERE tm.entity_type = 'person'
  AND tm.source_id = 123
GROUP BY p.id
ORDER BY mentions DESC;
```

---

## 6. 리스크 및 대응

| 리스크 | 확률 | 영향 | 대응 |
|--------|------|------|------|
| 대량 데이터 로딩 성능 | 중 | 중 | 페이지네이션, 인덱스 최적화 |
| context 텍스트 인코딩 | 낮 | 낮 | UTF-8 검증 |
| 매칭 오류 표시 | 중 | 낮 | 신뢰도 점수 표시, 필터링 |

---

## 7. 관련 문서

| 문서 | 설명 |
|------|------|
| [MASTER_PLAN.md](MASTER_PLAN.md) | 전체 프로젝트 계획 |
| [CLEANUP_REPORT_20260127.md](CLEANUP_REPORT_20260127.md) | 정리 작업 결과 |
| [BOOK_CONTEXT_TRACKING_PLAN.md](BOOK_CONTEXT_TRACKING_PLAN.md) | Context 추적 기획 |

---

## 8. 체크리스트

### 즉시 가능 (데이터 준비됨)
- [ ] Sources API 생성
- [ ] Person sources 엔드포인트 추가
- [ ] 기본 SourcePanel 컴포넌트

### 추가 데이터 필요
- [ ] 더 많은 책 추출 (현재 108권 진행 중)
- [ ] Wikidata 보강 계속

### 향후 개선
- [ ] 검색 확장
- [ ] 책 상세 페이지
- [ ] 검토 큐 UI
