# CHALDEAS 수장고 대량 다운로드 작업 로그

> 저작권 문제 없는 역사/철학/문학사/과학사 데이터 수집 프로젝트

## 목표

CHALDEAS 수장고(Storage/Library)에 저작권 문제 없는 퍼블릭 도메인 자료를 최대한 수집하여 Historical Chain 생성에 활용

---

## 수집 대상 소스 및 진행 상황

### 1. 구조화된 데이터 (JSON/RDF)

| 소스 | 라이선스 | 수집기 | 상태 | 비고 |
|------|----------|--------|------|------|
| **Wikidata** | CC0 | `wikidata.py` | 기존 | SPARQL 쿼리 방식 |
| **DBpedia** | CC BY-SA | `dbpedia.py` | 기존 | SPARQL 쿼리 방식 |
| **DBpedia Events** | CC BY-SA | `dbpedia.py` | 기존 | 이벤트 특화 |
| **Pleiades** | CC BY-SA | `pleiades.py` | 기존 | 고대 지명 |

### 2. 텍스트 아카이브

| 소스 | 라이선스 | 수집기 | 상태 | 비고 |
|------|----------|--------|------|------|
| **Project Gutenberg** | Public Domain | `gutenberg.py` | 기존 (개선 필요) | 60,000+ 책 |
| **Open Library** | CC0 | `open_library.py` | **완료** | Internet Archive |
| **British Library** | CC0 (Public Domain Mark) | `british_library.py` | **신규 생성** | 49,455권 (1510-1900) |
| **Perseus Digital Library** | CC BY-SA | `perseus.py` | 기존 | 그리스/로마 원전 |
| **Sacred Texts Archive** | Public Domain | `sacred_texts.py` | 기존 | 종교/신화 |
| **Chinese Text Project** | CC BY-NC | `ctext.py` | 기존 | 동양 고전 |
| **Latin Library** | Public Domain | `latin_library.py` | 기존 | 라틴어 원전 |
| **Bibliotheca Augustana** | 학술용 | `bibliotheca_augustana.py` | 기존 | 고전 텍스트 |

### 3. 백과사전/레퍼런스

| 소스 | 라이선스 | 수집기 | 상태 | 비고 |
|------|----------|--------|------|------|
| **1911 Britannica** | Public Domain | `britannica_1911.py` | 기존 | Wikisource |
| **Stanford Encyclopedia** | 저작권 있음 | `stanford_encyclopedia.py` | 기존 | 읽기만 무료 |
| **World History Encyclopedia** | CC BY-NC-SA | `worldhistory.py` | 기존 | 비상업적 |

### 4. 역사/신화 특화

| 소스 | 라이선스 | 수집기 | 상태 | 비고 |
|------|----------|--------|------|------|
| **Theoi Project** | Public Domain (번역) | `theoi.py` | 기존 | 그리스 신화 |
| **ToposText** | CC BY-NC | `topostext.py` | 기존 | 고대 지명 |
| **MIT Pantheon** | CC BY | `pantheon.py` | 기존 | 역사적 인물 |
| **Yale Avalon Project** | Public Domain | `avalon.py` | 기존 | 1차 사료 |
| **Fordham Sourcebooks** | 학술용 | `fordham.py` | 기존 | 중세/고대 사료 |

### 5. FGO 특화

| 소스 | 라이선스 | 수집기 | 상태 | 비고 |
|------|----------|--------|------|------|
| **Atlas Academy** | 게임 데이터 | `atlas_academy.py` | 기존 | 서번트 정보 |
| **FGO Gamepress** | 팬 콘텐츠 | `fgo_gamepress.py` | 기존 | 서번트 로어 |
| **Wikipedia (Servants)** | CC BY-SA | `wikipedia.py` | 기존 | 역사 인물 정보 |

### 6. 지역별 특화

| 소스 | 라이선스 | 수집기 | 상태 | 비고 |
|------|----------|--------|------|------|
| **Arthurian Legends** | Mixed | `arthurian.py` | 기존 | 아서왕 전설 |
| **Russian History** | CC BY-SA | `russian_history.py` | 기존 | 동유럽 |
| **Mesoamerican** | CC BY-SA | `mesoamerican.py` | 기존 | 아즈텍/마야/잉카 |
| **Indian Mythology** | CC BY-SA | `indian_mythology.py` | 기존 | 인도 신화 |

---

## 작업 로그

### 2026-01-02

#### 14:00 - 프로젝트 시작
- 목표: 저작권 문제 없는 역사/철학/문학/과학사 데이터 대량 수집
- 현재 시스템 분석 완료
- 기존 수집기 24개 확인

#### 14:10 - Open Library 수집기 생성
- 파일: `data/scripts/collectors/open_library.py`
- 기능:
  - Search API로 주제별 검색 (역사, 철학, 신화 등)
  - Bulk dump 다운로드 및 처리 (선택적)
  - 역사적 주제 필터링
- 상태: **완료**

#### 14:20 - 마스터 대량 다운로드 스크립트 생성
- 파일: `data/scripts/bulk_download.py`
- 기능:
  - 모든 소스 통합 다운로드
  - 3가지 모드: quick(테스트), normal(기본), full(최대)
  - 진행 상황 자동 저장
  - 우선순위 기반 다운로드 순서
- 상태: **완료**

#### 14:25 - collect_all.py 업데이트
- Open Library 수집기 추가
- 상태: **완료**

#### 완료된 작업
- [x] 현재 데이터 수집 시스템 분석
- [x] Open Library 수집기 생성
- [x] 마스터 대량 다운로드 스크립트 생성
- [x] collect_all.py 업데이트

#### 14:30 - Quick 모드 테스트 실행
- 완료된 소스:
  - Wikidata: 완료 (이벤트, 인물, 도시)
  - DBpedia: 완료 (이벤트, 장소, 인물)
  - Pleiades: 완료 (고대 지명)
  - ToposText: 완료 (고대 지명)
  - Pantheon: 완료 (역사적 인물)
  - Gutenberg: 500개 완료
  - Open Library: 2,000개 완료
- 상태: **부분 완료**

---

## 현재 수장고 현황 (2026-01-02 기준)

**총 데이터 크기: ~1.87 GB**

| 소스 | 파일 수 | 크기 | 상태 |
|------|---------|------|------|
| Pleiades | 3 | 1,407 MB | 완료 |
| Atlas Academy | 10 | 235 MB | 완료 |
| Pantheon | 3 | 136 MB | 완료 |
| Gutenberg | 1 | 32 MB | 카탈로그 |
| Stanford Encyclopedia | 3 | 13 MB | 인덱스 |
| Wikidata | 3 | 8 MB | 완료 |
| Indian Mythology | 4 | 8 MB | 완료 |
| DBpedia | 3 | 5 MB | 완료 |
| Mesoamerican | 4 | 4 MB | 완료 |
| Russian History | 3 | 4 MB | 완료 |
| World History | 3 | 3 MB | 완료 |
| ToposText | 2 | 3 MB | 완료 |
| Fordham | 3 | 2 MB | 완료 |
| Avalon | 3 | 2 MB | 완료 |
| Open Library | 2 | 1 MB | 신규 |
| Arthurian | 3 | 1 MB | 완료 |
| Perseus | 1 | 1 MB | 카탈로그 |
| Britannica 1911 | 3 | 1 MB | 완료 |
| CText | 20 | <1 MB | 동양고전 |

#### 20:07 - Full 모드 대량 수집 시작
- 명령어: `python data/scripts/bulk_download.py --all --full`
- 진행 상황:

| 소스 | 상태 | 수집 데이터 |
|------|------|-------------|
| Wikidata | **완료** | 이벤트 16,343 + 인물 5,261 + 도시 4,680 = 26,284 |
| DBpedia | **완료** | 이벤트 8,190 + 장소 4,953 + 인물 1,491 = 14,634 |
| Pleiades | **완료** | 고대 지명 34,313개 |
| ToposText | **완료** | 고대 지명 8,068개 |
| Pantheon | **완료** | 역사적 인물 59,902명 |
| Gutenberg | **완료** | 10,000개 텍스트 |
| Open Library | **완료** | 10,000개 책 메타데이터 |
| Perseus | 진행 중 | 그리스/로마 원전 2,482개 |
| Sacred Texts | 대기 | 종교/신화 텍스트 |
| ... | ... | ... |

#### 22:53 - Full 모드 대량 수집 완료!

**최종 결과:**
- 총 파일: **12,135개**
- 총 데이터: **8.06 GB**
- 완료된 소스: **22개**
- 소요 시간: ~2시간 46분

| 소스 | 파일 수 | 크기 | 내용 |
|------|---------|------|------|
| **Gutenberg** | 12,032 | 6.39 GB | 역사/철학 텍스트 |
| **Pleiades** | 3 | 1.41 GB | 고대 지명 34,313개 |
| **Atlas Academy** | 10 | 236 MB | FGO 서번트 데이터 |
| **Pantheon** | 3 | 137 MB | 역사적 인물 59,902명 |
| **Stanford Encyclopedia** | 3 | 13 MB | 철학 백과 인덱스 |
| **ToposText** | 3 | 10 MB | 고대 지명 8,068개 |
| **Wikidata** | 3 | 9 MB | 이벤트/인물/도시 26,284개 |
| **Indian Mythology** | 4 | 8 MB | 인도 신화 |
| **Arthurian** | 13 | 5 MB | 아서왕 전설 |
| **Open Library** | 2 | 5 MB | 책 메타데이터 10,000+ |
| **DBpedia** | 3 | 5 MB | 이벤트/장소/인물 14,634개 |
| **Mesoamerican** | 4 | 5 MB | 아즈텍/마야/잉카 |
| **Russian History** | 3 | 4 MB | 러시아/동유럽 |
| **World History** | 3 | 3 MB | 세계사 백과 |
| **Avalon** | 3 | 2 MB | 1차 사료 |
| **Fordham** | 3 | 2 MB | 중세/고대 사료 |
| **Britannica 1911** | 3 | 2 MB | 1911 브리태니커 2,000개 |
| **Perseus** | 2 | 2 MB | 그리스/로마 원전 2,482개 |
| 기타 | - | <1 MB | CText, Theoi, Sacred Texts 등 |

---

### 2026-01-02 (계속)

#### 추가 수집 소스: British Library

**British Library Digitised Books Dataset**

| 항목 | 내용 |
|------|------|
| 크기 | 11 GB (압축) |
| 내용 | 49,455권 (65,227 볼륨), 2,500만+ 페이지 |
| 기간 | 1510년 ~ 1900년 |
| 형식 | JSON (OCR 텍스트) |
| 라이선스 | CC Public Domain Mark 1.0 |
| 주제 | 역사, 철학, 문학, 지리, 시 등 |

**수집기 생성**: `data/scripts/collectors/british_library.py`

#### 00:45 - British Library 수집 완료!

| 항목 | 결과 |
|------|------|
| 다운로드 | 10.59 GB (압축) |
| 추출 파일 | 63,985개 JSON 파일 |
| 추출 크기 | 42 GB |
| 소요 시간 | ~1시간 30분 |

---

## 현재 수장고 현황 (2026-01-03 업데이트)

**총 데이터 크기: ~50 GB**

| 소스 | 파일 수 | 크기 | 상태 |
|------|---------|------|------|
| **British Library** | 63,985 | 42 GB | **신규 완료** |
| Gutenberg | 12,032 | 6.39 GB | 완료 |
| Pleiades | 3 | 1.41 GB | 완료 |
| Atlas Academy | 10 | 236 MB | 완료 |
| Pantheon | 3 | 137 MB | 완료 |
| 기타 (22개 소스) | - | ~500 MB | 완료 |

---

## 수집 명령어

```bash
# 전체 수집 (기존)
python data/scripts/collect_all.py --source all

# 개별 소스 수집
python data/scripts/collect_all.py --source gutenberg --limit 5000
python data/scripts/collect_all.py --source wikidata
python data/scripts/collect_all.py --source perseus

# 대량 다운로드 (추가 예정)
python data/scripts/bulk_download.py --all
python data/scripts/bulk_download.py --source gutenberg --full
```

---

## 데이터 현황

### 현재 수집된 데이터 (`data/raw/`)

```
data/raw/
├── wikidata/          # 이벤트, 인물, 도시
├── dbpedia/           # 이벤트, 장소, 인물
├── pleiades/          # 고대 지명
├── perseus/           # 그리스/로마 원전 목록
├── ctext/             # 동양 고전 (논어, 맹자 등 20+)
├── gutenberg/         # 역사/철학 텍스트
├── theoi/             # 그리스 신화 인물
├── sacred_texts/      # 종교/신화 텍스트
├── pantheon/          # MIT 역사적 인물
├── wikipedia/         # 서번트 관련 인물
├── avalon/            # 1차 사료
├── fordham/           # 중세/고대 사료
├── worldhistory/      # 세계사 백과
├── stanford_encyclopedia/  # 철학 백과
├── britannica_1911/   # 1911 브리태니커
├── arthurian/         # 아서왕 전설
├── russian_history/   # 러시아/동유럽
├── mesoamerican/      # 메소아메리카
├── indian_mythology/  # 인도 신화
└── open_library/      # (추가 예정)
```

---

## 라이선스 요약

| 라이선스 | 상업적 사용 | 수정 | 출처 표기 | 해당 소스 |
|----------|-------------|------|-----------|-----------|
| **CC0** | O | O | 불필요 | Wikidata |
| **Public Domain** | O | O | 불필요 | Gutenberg, Sacred Texts, 1911 Britannica |
| **CC BY** | O | O | 필요 | Pantheon |
| **CC BY-SA** | O | O (동일 조건) | 필요 | DBpedia, Perseus, Wikipedia |
| **CC BY-NC** | X | O | 필요 | CText, ToposText |
| **CC BY-NC-SA** | X | O (동일 조건) | 필요 | World History Encyclopedia |

---

## 참고 링크

- [Project Gutenberg](https://www.gutenberg.org/)
- [Open Library](https://openlibrary.org/)
- [Wikidata Dumps](https://dumps.wikimedia.org/wikidatawiki/entities/)
- [DBpedia Downloads](https://downloads.dbpedia.org/)
- [Perseus Digital Library](https://www.perseus.tufts.edu/)
- [Internet Sacred Text Archive](https://sacred-texts.com/)
