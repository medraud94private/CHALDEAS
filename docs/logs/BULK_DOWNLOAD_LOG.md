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
| **Open Library** | CC0 | `open_library.py` | **신규 생성** | Internet Archive |
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

#### 다음 작업 (수동 실행 필요)
- [ ] `python data/scripts/bulk_download.py --all --quick` 실행 (테스트)
- [ ] `python data/scripts/bulk_download.py --all` 실행 (본격 수집)

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
