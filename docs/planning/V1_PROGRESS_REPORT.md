# CHALDEAS V1 Progress Report

## 작업 완료일: 2026-01-07

---

## 1. 완료된 작업 요약

### 1.1 NER 배치 처리 (이전 세션)
- **소스**: Project Gutenberg, British Library 등 76,000+ 문서
- **모델**: GPT-5-nano (Batch API)
- **비용**: ~$47 (일회성)
- **결과**: 555,211개 엔티티 추출

### 1.2 V1 DB 스키마 구현
새로 생성된 테이블:
| 테이블 | 용도 |
|--------|------|
| `polities` | 정치체 (제국, 왕국, 왕조 등) |
| `historical_chains` | 역사의 고리 (큐레이션 단위) |
| `chain_segments` | 체인 내 개별 세그먼트 |
| `text_mentions` | 엔티티-문서 연결 |
| `entity_aliases` | 엔티티 별칭 |
| `import_batches` | 임포트 이력 |

기존 테이블 확장:
- `persons`: role, era, certainty, mention_count, avg_confidence 추가
- `sources`: document_id, content (원문) 추가

### 1.3 데이터 임포트

#### 엔티티 임포트 (aggregated → DB)
| 엔티티 | 임포트 수 |
|--------|----------|
| Persons | 285,750 |
| Locations | 34,409 |
| Events | 10,428 |
| Polities | 9 |
| Periods | 61 |
| **합계** | **330,657** |

#### 원문 및 멘션 임포트
| 항목 | 수량 |
|------|------|
| Sources (원문 문서) | 76,023 |
| Text Mentions (연결) | 595,146 |

#### DB 사이즈
- **전체**: 1.6 GB
- persons 테이블이 가장 큼 (~580 MB)

### 1.4 Explore API 구현

```
GET /api/v1/explore/stats              # 전체 통계
GET /api/v1/explore/persons            # 인물 목록 (필터, 정렬, 페이지네이션)
GET /api/v1/explore/locations          # 장소 목록
GET /api/v1/explore/events             # 사건 목록
GET /api/v1/explore/polities           # 정치체 목록
GET /api/v1/explore/periods            # 시대 목록
GET /api/v1/explore/sources            # 원문 목록
GET /api/v1/explore/sources/{id}       # 원문 상세 (전문 포함)
GET /api/v1/explore/sources/{id}/entities    # 문서 내 엔티티
GET /api/v1/explore/entity/{type}/{id}/sources  # 엔티티 출처
GET /api/v1/explore/top-mentioned      # 가장 많이 언급된 엔티티
```

### 1.5 프론트엔드 UI 구현

**ExplorePanel 컴포넌트** (`frontend/src/components/explore/`)
- 6개 탭: Persons, Locations, Events, Polities, Periods, Sources
- 검색, 필터, 정렬, 페이지네이션
- 통계 요약 표시
- 오른쪽 하단 빨간색 ⋮⋮⋮ 버튼으로 접근

---

## 2. 현재 데이터 품질 현황

### 2.1 Persons 분포
```
certainty 분포:
- fact: 142,146 (50%)
- legendary: 111,762 (39%)
- mythological: 28,611 (10%)
- probable: 3,231 (1%)

era 분포 (상위):
- (empty): 188,619
- Unknown: 57,214
- 19th century: 8,162
- 18th century: 1,965
- Medieval: 3,329
```

### 2.2 Locations 분포
```
type 분포 (상위):
- settlement: 11,832
- villa: 2,171
- river: 1,277
- station: 1,274
- fort: 1,132
```

### 2.3 데이터 품질 이슈
1. **좌표 부재**: 대부분의 locations에 lat/lon 없음
2. **연대 부재**: 많은 persons에 birth_year/death_year 없음
3. **era 미분류**: 188,619개 인물의 era가 빈 값
4. **중복 가능성**: 같은 인물이 다른 이름으로 여러 번 등록

---

## 3. 파일 구조

```
backend/
├── app/
│   ├── api/v1_new/
│   │   ├── __init__.py
│   │   └── explore.py          # Explore API (신규)
│   ├── models/v1/
│   │   ├── polity.py           # Polity 모델 (신규)
│   │   ├── chain.py            # Historical Chain 모델 (신규)
│   │   └── text_mention.py     # Text Mention 모델 (신규)

frontend/
├── src/
│   ├── components/
│   │   └── explore/
│   │       ├── ExplorePanel.tsx   # 메인 컴포넌트 (신규)
│   │       └── ExplorePanel.css   # 스타일 (신규)

poc/
├── scripts/
│   ├── import_to_v1_db.py              # 엔티티 임포트 스크립트
│   └── import_sources_and_mentions.py  # 원문/멘션 임포트 스크립트
├── data/
│   └── integrated_ner_full/
│       ├── aggregated/           # 집계된 엔티티 JSON
│       ├── minimal_batch_*.jsonl       # 배치 입력 (원문)
│       └── minimal_batch_*_output.jsonl # 배치 출력 (NER 결과)
```

---

## 4. 실행 방법

### 백엔드
```bash
cd backend
python -m uvicorn app.main:app --port 8100
```

### 프론트엔드
```bash
cd frontend
npm run dev -- --port 5200
```

### 접속
- Frontend: http://localhost:5200
- API Docs: http://localhost:8100/docs
- Entity Explorer: 오른쪽 하단 ⋮⋮⋮ 버튼

---

## 5. 다음 단계 (Phase 2)

→ `V1_GLOBE_INTEGRATION_PLAN.md` 참조
