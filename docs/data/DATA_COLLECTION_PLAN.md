# CHALDEAS 데이터 수집 마스터 플랜

> Last Updated: 2025-12-31
> 목표: FGO 기반 + 역사 대학원생 수준의 종합 역사 데이터베이스 구축

---

## Phase 1: 완료된 수집 (현재)

### 기본 데이터 (~2GB)

| 소스 | 내용 | 상태 |
|------|------|------|
| Pleiades | 고대 장소 좌표 | ✅ 완료 |
| Wikidata | 이벤트/도시/인물 | ✅ 완료 |
| DBpedia | 이벤트/장소/인물 | ✅ 완료 |
| ToposText | 8,068개 고대 장소 | ✅ 완료 |
| Pantheon | 59,902명 역사 인물 | ✅ 완료 |

### 고전 텍스트 (~1GB)

| 소스 | 내용 | 상태 |
|------|------|------|
| Perseus | 그리스/로마 카탈로그 | ✅ 완료 |
| CText | 중국 고전 20종 | ✅ 완료 |
| Latin Library | 라틴 메타데이터 | ✅ 완료 |
| Augustana | 475종 그리스/라틴 | ✅ 완료 |

### 신화/종교 (~500MB)

| 소스 | 내용 | 상태 |
|------|------|------|
| Theoi | 736명 그리스 신화 | ✅ 완료 |
| Sacred-Texts | 961종 종교/신화 | ✅ 완료 |

### FGO 특화 (~100MB)

| 소스 | 내용 | 상태 |
|------|------|------|
| Atlas Academy | 385명 서번트 | ✅ 완료 |
| Gamepress | 427명 서번트 로어 | ✅ 완료 |
| Wikipedia | 372개 서번트 위키 | ✅ 완료 |

---

## Phase 2: 진행 중 (~6GB)

| 소스 | 내용 | 상태 | 예상 용량 |
|------|------|------|-----------|
| Gutenberg (역사) | 12,148권 역사 텍스트 | 🔄 ~22% | ~6GB |

---

## Phase 3: 역사 대학원생 필수 자료 (우선순위 높음)

### 3.1 Primary Sources - 1차 사료

| 소스 | URL | 내용 | 예상 용량 | 우선순위 |
|------|-----|------|-----------|----------|
| **Yale Avalon Project** | avalon.law.yale.edu | 법/역사/외교 원문 (Magna Carta ~ 현대) | ~500MB | ⭐⭐⭐ |
| **Fordham Sourcebooks** | sourcebooks.fordham.edu | 고대/중세/근대 1차 사료 | ~1GB | ⭐⭐⭐ |
| **EuroDocs** | eudocs.lib.byu.edu | 유럽 역사 문서 | ~300MB | ⭐⭐ |
| **JSTOR Primary Sources** | jstor.org | 학술 1차 사료 (제한적) | 메타만 | ⭐⭐ |

### 3.2 Reference Works - 참고 자료

| 소스 | URL | 내용 | 예상 용량 | 우선순위 |
|------|-----|------|-----------|----------|
| **World History Encyclopedia** | worldhistory.org | 역사 백과사전 | ~2GB | ⭐⭐⭐ |
| **Stanford Encyclopedia of Philosophy** | plato.stanford.edu | 철학 백과사전 | ~1GB | ⭐⭐⭐ |
| **Encyclopedia Britannica (1911)** | Public Domain | 역사적 백과사전 | ~500MB | ⭐⭐ |
| **Catholic Encyclopedia** | newadvent.org | 종교/역사 | ~300MB | ⭐⭐ |

### 3.3 Period-Specific Sources - 시대별 자료

| 시대 | 소스 | 내용 | 예상 용량 |
|------|------|------|-----------|
| 고대 | Perseus (확장) | 그리스/로마 전문 | ~2GB |
| 중세 | Fordham Medieval | 중세 유럽 | ~1GB |
| 르네상스 | Encyclopaedia Britannica 1911 | 르네상스 항목 | ~200MB |
| 근대 | Avalon Project | 근대 문서 | ~500MB |
| 동아시아 | CText (확장) | 추가 중국 고전 | ~1GB |

### 3.4 Geographic/Archaeological - 지리/고고학

| 소스 | 내용 | 상태 |
|------|------|------|
| Pleiades | 고대 지명 | ✅ 완료 |
| ToposText | 그리스/로마 지명 | ✅ 완료 |
| DARE (Digital Atlas of Roman Empire) | 로마 제국 지도 | 📋 계획 |
| Pelagios | 고대 세계 연결 데이터 | 📋 계획 |

**Phase 3 예상 총 용량: ~10GB**
**예상 임베딩 비용: ~$50 (small 모델)**

---

## Phase 4: 확장 계획 (중장기)

### 4.1 대용량 텍스트 소스

| 소스 | 수량 | 텍스트 용량 | PDF 포함 | 우선순위 |
|------|------|-------------|----------|----------|
| **Project Gutenberg (전체)** | 77,000권 | ~50GB | - | ⭐⭐⭐ |
| **Internet Archive (역사)** | ~100만권+ | ~500GB | 10TB+ | ⭐⭐ |
| **Open Library** | 3,000만 메타 | ~50GB | - | ⭐⭐ |
| **HathiTrust (public domain)** | ~600만권 | ~3TB | 30TB+ | ⭐ |

### 4.2 뉴스/신문 아카이브

| 소스 | 수량 | 용량 | 우선순위 |
|------|------|------|----------|
| **Library of Congress Newspapers** | 수백만 페이지 | ~100GB (텍스트) | ⭐⭐ |
| **Chronicling America** | 미국 역사 신문 | ~50GB | ⭐⭐ |
| **British Newspaper Archive** | 영국 신문 | 접근 제한 | ⭐ |

### 4.3 학술 자료

| 소스 | 수량 | 용량 | 우선순위 |
|------|------|------|----------|
| **Wikipedia 역사 문서** | ~200만개 | ~30GB | ⭐⭐⭐ |
| **CORE (학술 논문)** | ~2억개 | 수 TB | ⭐ |
| **arXiv (역사 관련)** | 제한적 | ~10GB | ⭐ |

### 4.4 특수 컬렉션

| 소스 | 내용 | 용량 |
|------|------|------|
| **Nuremberg Trials** | 전범 재판 기록 | ~5GB |
| **Napoleonic Wars Docs** | 나폴레옹 시대 | ~2GB |
| **WWI/WWII Archives** | 세계대전 자료 | ~20GB |
| **Cold War Documents** | 냉전 문서 | ~10GB |

---

## Phase 5: 장기 비전 (1TB+)

### 전체 아키텍처

```
Storage Tiers:

Tier 1 - Hot (SSD, 200GB):
  - 현재 수집 데이터
  - 임베딩 벡터 DB
  - 자주 조회되는 데이터

Tier 2 - Warm (HDD/NAS, 1TB):
  - Gutenberg 전체
  - Internet Archive 선별
  - Wikipedia 전체 역사 덤프

Tier 3 - Cold (Cloud/Archive, 10TB+):
  - HathiTrust 전체
  - 신문 아카이브
  - 학술 논문 전체
```

### 예상 비용

| 항목 | Phase 3 | Phase 4 | Phase 5 |
|------|---------|---------|---------|
| **저장 용량** | ~20GB | ~200GB | ~1TB+ |
| **임베딩 비용** | ~$50 | ~$500 | ~$2,500 |
| **총 투자** | ~$50 | ~$550 | ~$3,000 |

---

## 실행 계획

### 즉시 실행 (Phase 3)

```bash
# 1. Yale Avalon Project
python data/scripts/collect_all.py --source avalon

# 2. Fordham Sourcebooks
python data/scripts/collect_all.py --source fordham

# 3. World History Encyclopedia
python data/scripts/collect_all.py --source worldhistory

# 4. Stanford Encyclopedia of Philosophy
python data/scripts/collect_all.py --source stanford_philosophy
```

### 다음 단계 (Phase 4)

```bash
# Gutenberg 전체
python data/scripts/collect_all.py --source gutenberg --limit 80000

# Wikipedia 역사 덤프
python data/scripts/collect_all.py --source wikipedia_history

# Internet Archive 선별
python data/scripts/collect_all.py --source internet_archive --category history
```

---

## Collector 개발 현황

### 완료된 Collectors (14개)

| Collector | 파일 |
|-----------|------|
| Pleiades | `collectors/pleiades.py` |
| Wikidata | `collectors/wikidata.py` |
| DBpedia | `collectors/dbpedia.py` |
| Perseus | `collectors/perseus.py` |
| CText | `collectors/ctext.py` |
| Gutenberg | `collectors/gutenberg.py` |
| Latin Library | `collectors/latin_library.py` |
| Augustana | `collectors/bibliotheca_augustana.py` |
| ToposText | `collectors/topostext.py` |
| Theoi | `collectors/theoi.py` |
| Sacred-Texts | `collectors/sacred_texts.py` |
| Atlas Academy | `collectors/atlas_academy.py` |
| Gamepress | `collectors/fgo_gamepress.py` |
| Pantheon | `collectors/pantheon.py` |
| Wikipedia | `collectors/wikipedia.py` |

### 개발 필요 Collectors

| Collector | 우선순위 | 상태 |
|-----------|----------|------|
| Yale Avalon | ⭐⭐⭐ | 📋 계획 |
| Fordham Sourcebooks | ⭐⭐⭐ | 📋 계획 |
| World History Encyclopedia | ⭐⭐⭐ | 📋 계획 |
| Stanford Encyclopedia | ⭐⭐⭐ | 📋 계획 |
| Internet Archive | ⭐⭐ | 📋 계획 |
| Open Library | ⭐⭐ | 📋 계획 |
| LoC Newspapers | ⭐⭐ | 📋 계획 |
| HathiTrust | ⭐ | 📋 계획 |
| CORE | ⭐ | 📋 계획 |

---

## 품질 기준

### 역사 대학원생 기준 필수 자료

- [ ] 고대사: 헤로도토스, 투키디데스, 타키투스, 리비우스
- [ ] 중세사: 성경, 교부 문헌, 중세 연대기
- [ ] 동양사: 사기, 한서, 삼국지, 논어, 도덕경
- [ ] 철학: 플라톤, 아리스토텔레스, 칸트, 헤겔
- [ ] 종교: 성경, 코란, 불경, 베다
- [ ] 법/정치: 마그나 카르타, 독립선언문, 인권선언
- [ ] 지리: 고대 지명, 역사 지도 데이터

---

## 임베딩 전략

### 모델 선택

| 용도 | 모델 | 비용 |
|------|------|------|
| 기본 검색 | text-embedding-3-small | $0.02/1M |
| 고품질 검색 | text-embedding-3-large | $0.13/1M |
| 로컬/무료 | sentence-transformers | 무료 |

### 청킹 전략

```
역사 텍스트 최적화:
- 청크 크기: 1000 tokens
- 오버랩: 200 tokens
- 메타데이터: 시대, 지역, 인물, 사건 태깅
```

---

## 참고 자료

### 주요 소스 URL

- Yale Avalon: https://avalon.law.yale.edu/
- Fordham Sourcebooks: https://sourcebooks.fordham.edu/
- World History Encyclopedia: https://www.worldhistory.org/
- Stanford Encyclopedia: https://plato.stanford.edu/
- Internet Archive: https://archive.org/
- Open Library: https://openlibrary.org/
- HathiTrust: https://www.hathitrust.org/
- Library of Congress: https://www.loc.gov/
- CORE: https://core.ac.uk/
