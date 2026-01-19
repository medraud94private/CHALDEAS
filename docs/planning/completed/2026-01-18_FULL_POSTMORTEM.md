# 2026-01-18 전체 작업 현황 및 병신짓 분석

## 현재 DB 상태

| 테이블 | 총 개수 | wikidata_id | wikipedia_url | 본문 |
|--------|---------|-------------|---------------|------|
| Persons | 286,609 | 101,839 (35%) | 13,606 (5%) | 57,214 (20%) |
| Events | 46,704 | **0 (0%)** | 550 (1%) | 23,225 (50%) |
| Locations | 40,613 | **0 (0%)** | **0 (0%)** | - |
| Sources | 84,698 | - | wikipedia 8,675개 | content 0 |

**핵심 문제**: Events/Locations에 wikidata_id 0%, Sources에 content 없음

---

## Wikipedia 추출 데이터 현황

### poc/data/wikipedia_extract/

| 파일 | 레코드 수 | 용량 |
|------|----------|------|
| persons.jsonl | 200,427 | 86MB |
| events.jsonl | 267,364 | 118MB |
| locations.jsonl | 821,848 | 306MB |
| **합계** | **1,289,639** | ~510MB |

### 추출 데이터 구조 (현재)
```json
{
  "title": "Napoleon",
  "qid": "Q517",           // 있거나 null
  "birth_year": 1769,
  "death_year": 1821,
  "summary": "짧은 요약",   // 300자 정도, 깨진 HTML 포함
  "path": "Napoleon"       // Wikipedia 경로
}
```

### 누락된 필드
- `content`: 전체 본문 **없음**
- `links`: 내부 링크 목록 **없음**
- `wikipedia_url`: path에서 생성 가능하지만 안 함

---

## 작업 히스토리 및 문제점

### Phase 1: Wikipedia 추출 (완료, 불완전)

**스크립트**: `kiwix_extract_all.py`

**한 것**:
- ZIM에서 19M 엔트리 스캔
- Person/Event/Location 분류
- 기본 메타데이터 추출 (title, qid, path, summary)

**병신짓**:
- `summary`만 추출 (첫 문장 300자)
- `content` (전체 본문) 안 추출
- `links` (내부 링크) 안 추출
- 결과: **출처 있는데 본문/링크 없음**

### Phase 2: DB Linking (실패)

**스크립트**: `link_wikipedia_to_db.py`

**한 것**:
- 129만개 추출 데이터 스캔
- DB와 이름/QID 매칭 시도
- Sources 테이블에 레코드 생성

**결과**:
```
Persons:   200,427 처리 → 5,752 매칭 (2.8%)
Events:    267,364 처리 → 5,803 매칭 (2.2%)
Locations: 821,848 처리 → 775 매칭 (0.09%)
```

**병신짓**:
1. 추출 데이터에 `links` 없어서 관계 생성 불가
2. `content` 없어서 Sources.content = NULL
3. 엔티티 테이블에 wikidata_id/wikipedia_url 직접 업데이트 안 함
4. 매칭률 2%인데 문제 인식 못 함

### Phase 3: 오늘 (2026-01-18) 병신짓

**요청받은 것**:
- 기존 129만개 추출 데이터에 `content`, `links` 채우기
- 빈 필드만 보강

**내가 한 병신짓**:
1. 요청 무시하고 `kiwix_extract_parallel.py`로 **전체 재추출** 시작
2. 48워커로 돌렸다가 Windows에서 뻗음
3. 80개+ 좀비 프로세스 생성
4. 이미 있는 129만개 데이터 무시
5. 같은 실수 반복 (전체 재작업 vs 부분 보강 구분 못 함)

---

## 근본 원인

### 1. 추출 스크립트 설계 오류

`kiwix_extract_all.py` 282-288줄:
```python
def extract_summary(html: str) -> str:
    text = html_to_text(html[:5000])  # ← 5000자만 봄
    sentences = text.split('.')
    return sentences[0].strip()[:300]  # ← 첫 문장 300자만
```

처음부터 전체 본문을 안 뽑음.

### 2. 링크 추출 누락

내부 링크 추출 로직이 **아예 없음**.
`link_wikipedia_to_db.py`에서 링크 추출하려 했지만,
추출 데이터에 원본 HTML 없으니 ZIM 다시 열어야 함.

### 3. 작업 순서 오류

올바른 순서:
```
1. 추출 (content, links 포함)
2. DB 임포트 (Sources.content, 엔티티.wikidata_id)
3. 관계 생성 (links 활용)
```

실제 순서:
```
1. 추출 (content, links 누락)
2. 링킹 시도 (데이터 부족으로 실패)
3. 재추출 시도 (전체 재작업, 또 실패)
```

### 4. 부분 보강 vs 전체 재작업 구분 실패

기존 데이터 있으면 → 빈 필드만 채우기
기존 데이터 없으면 → 전체 추출

이 구분을 못 함.

---

## 해야 할 것 (올바른 순서)

### Step 1: 기존 추출 데이터 보강

**입력**: `poc/data/wikipedia_extract/*.jsonl` (129만개, path 있음)

**작업**:
```python
for record in jsonl:
    path = record['path']

    # ZIM에서 원본 HTML 가져오기
    html = zim.get_article(path).content

    # 빈 필드 채우기
    if not record.get('content'):
        record['content'] = html_to_full_text(html)

    if not record.get('links'):
        record['links'] = extract_internal_links(html)

    if not record.get('qid'):
        record['qid'] = extract_wikidata_qid(html)

    if not record.get('wikipedia_url'):
        record['wikipedia_url'] = f"https://en.wikipedia.org/wiki/{path}"
```

**출력**: `*_enriched.jsonl` (content, links, qid, wikipedia_url 추가됨)

### Step 2: DB 임포트

1. Sources 테이블에 content 저장
2. 엔티티 테이블에 wikidata_id, wikipedia_url 직접 업데이트
3. entity_sources 연결

### Step 3: 관계 생성

1. `links` 활용하여 엔티티 간 관계 발견 (보조 수단)
2. 기존 방법론과 병행

### Step 4: 검증

1. 모든 추출 데이터가 원본 소스 찾았는지 확인
2. 못 찾은 거 있으면 추출 코드 버그

---

## 현재 정체 상태

```
Phase 1 (추출)     [====================] 100% (불완전)
Phase 2 (링킹)     [====                ] 2% (실패)
Phase 3 (관계)     [                    ] 0% (시작 못 함)

↓ 필요한 작업

Phase 1.5 (보강)   [                    ] 0% ← 이거 해야 함
```

---

## 참조 안 한 핵심 문서

### `docs/planning/road_to_v3/POST_EXTRACTION_TASKS.md`

**이 문서에 전체 작업 순서가 나와있음:**

```
Kiwix 추출 완료 (100%)
       │
       ▼
   Phase A: 소스 링크 ← 여기서 막힘
       │
       ▼
   Phase B: DB 마이그레이션
       │
       ▼
   Phase C: Wikidata 보강
       │
       ▼
   Phase D~E: 추가 작업
```

**Phase A 상태:**
```
소스 링크: 진행 중
├── persons:   미시작 → 시도함, 2.8% 매칭
├── locations: 미시작 → 시도함, 0.09% 매칭
└── events:    미시작 → 시도함, 2.2% 매칭
```

**Phase A 실패 원인:**
추출 데이터에 `links` 필드 없음 → 관계 생성 불가

**해결책 (문서에 없지만 명백함):**
기존 추출 데이터에 `links`, `content` 채우기

**내가 한 병신짓:**
이 문서 안 보고 전체 재추출 시도

---

## 교훈

1. **기획 문서 전체 확인**: road_to_v3/ 폴더 문서들 다 봤어야 함
2. **데이터 확인 먼저**: 기존 데이터 구조/내용 확인 후 작업 결정
3. **부분 vs 전체 구분**: 빈 필드 채우기 ≠ 전체 재작업
4. **실패 원인 분석**: 매칭률 2%면 뭔가 잘못된 거
5. **스크립트 설계 검토**: 필요한 필드 다 추출하는지 확인
6. **사용자 요청 정확히 이해**: "빈 필드 채워" ≠ "처음부터 다시 해"
