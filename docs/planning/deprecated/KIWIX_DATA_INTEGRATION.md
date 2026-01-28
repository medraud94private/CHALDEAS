# Kiwix Offline Data Integration

> **Status**: Planning
> **Date**: 2026-01-15
> **Source**: https://download.kiwix.org/zim/

---

## Overview

Kiwix ZIM 아카이브를 활용하여 오프라인 Wikipedia/Wikisource 데이터를 CHALDEAS에 통합.
이미지 불필요, 영어만 대상.

---

## Target Datasets

| Dataset | File | Size | Purpose |
|---------|------|------|---------|
| **Wikipedia EN** | `wikipedia_en_all_nopic_2025-08.zim` | 43 GB | 인물/사건/장소 문서 |
| **Wikisource EN** | `wikisource_en_all_nopic_2025-11.zim` | 11 GB | 역사 원문/1차 사료 |
| **Wikipedia EN mini** | `wikipedia_en_all_mini_2025-12.zim` | 11 GB | 테스트용 (top 문서) |

**Total**: ~54 GB (nopic 버전 기준)

### 제외
- Gutenberg (206 GB) - 너무 큼, 나중에 고려
- 이미지 포함 버전 - 불필요

---

## Integration Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  ZIM Files (Offline Wikipedia/Wikisource)                       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  ZIM Parser (kiwix-tools / zimlib)                              │
│  - Extract articles as HTML/text                                │
│  - Extract metadata (title, categories, links)                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  Article Classifier                                              │
│  - Person? → persons enrichment                                  │
│  - Event? → events enrichment                                    │
│  - Location? → locations enrichment                              │
│  - Other? → sources 테이블에 저장                                │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  Entity Matching                                                 │
│  - Wikipedia title → DB entity 매칭                              │
│  - 매칭됨: 메타데이터 보강                                        │
│  - 미매칭: 검토 큐 또는 신규 생성                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Data Value

### Wikipedia
| Category | Expected Articles | Use Case |
|----------|------------------|----------|
| Biographies | ~1.8M | persons 테이블 보강 |
| Historical Events | ~500K | events 테이블 보강 |
| Locations | ~1.5M | locations 테이블 보강 |
| History Articles | ~200K | 소스 문서로 활용 |

### Wikisource
| Content Type | Use Case |
|--------------|----------|
| Historical Documents | 1차 사료 |
| Treaties/Laws | 역사적 문서 원문 |
| Letters/Speeches | 인물 관련 원문 |
| Old Books | 역사 서적 |

---

## Implementation Plan

### Phase 1: Setup & Download
```bash
# 다운로드 디렉토리 준비
mkdir -p data/kiwix

# Wikipedia mini (테스트용)
wget -c https://download.kiwix.org/zim/wikipedia/wikipedia_en_all_mini_2025-12.zim \
     -O data/kiwix/wikipedia_en_mini.zim

# Wikipedia full nopic
wget -c https://download.kiwix.org/zim/wikipedia/wikipedia_en_all_nopic_2025-08.zim \
     -O data/kiwix/wikipedia_en_nopic.zim

# Wikisource
wget -c https://download.kiwix.org/zim/wikisource/wikisource_en_all_nopic_2025-11.zim \
     -O data/kiwix/wikisource_en_nopic.zim
```

### Phase 2: ZIM Parsing Setup
```bash
# kiwix-tools 설치 (Windows)
# Option A: Chocolatey
choco install kiwix-tools

# Option B: 수동 다운로드
# https://download.kiwix.org/release/kiwix-tools/

# Python library
pip install libzim
```

### Phase 3: Article Extraction Script
```python
# poc/scripts/extract_kiwix_articles.py
from libzim.reader import Archive

def extract_articles(zim_path, output_dir, category_filter=None):
    """
    ZIM 파일에서 문서 추출
    - category_filter: 'biography', 'event', 'location' 등
    """
    zim = Archive(zim_path)

    for entry in zim.entries:
        if entry.is_redirect:
            continue

        title = entry.title
        content = entry.get_item().content.decode('utf-8')

        # HTML → Text 변환
        text = html_to_text(content)

        # 분류
        category = classify_article(title, text)

        # 저장
        save_article(title, text, category, output_dir)
```

### Phase 4: Entity Matching
```python
# poc/scripts/match_kiwix_to_db.py
def match_wikipedia_to_persons(article_title, article_text):
    """
    Wikipedia 문서를 DB persons와 매칭
    """
    # 1. 제목으로 직접 매칭
    person = db.query(Person).filter(
        Person.name.ilike(article_title)
    ).first()

    if person:
        # 메타데이터 보강
        enrich_person_from_wikipedia(person, article_text)
        return "matched"

    # 2. Wikidata QID로 매칭 (있으면)
    qid = extract_wikidata_qid(article_text)
    if qid:
        person = db.query(Person).filter(
            Person.wikidata_id == qid
        ).first()
        if person:
            enrich_person_from_wikipedia(person, article_text)
            return "matched_by_qid"

    return "not_matched"
```

---

## Checklist

### Phase 1: Download
- [ ] 다운로드 디렉토리 생성
- [ ] Wikipedia mini 다운로드 (11 GB, 테스트용)
- [ ] Wikipedia nopic 다운로드 (43 GB)
- [ ] Wikisource nopic 다운로드 (11 GB)

### Phase 2: Parsing
- [ ] libzim 설치
- [ ] ZIM 읽기 테스트
- [ ] Article 추출 스크립트 작성
- [ ] HTML → Text 변환 로직

### Phase 3: Classification
- [ ] Biography 분류기 (Infobox person 등)
- [ ] Event 분류기 (Infobox event/battle/war)
- [ ] Location 분류기 (Infobox settlement/country)

### Phase 4: Integration
- [ ] DB 매칭 로직
- [ ] 메타데이터 보강 로직
- [ ] 신규 엔티티 처리

---

## Storage Requirements

| Item | Size |
|------|------|
| ZIM files | ~65 GB |
| Extracted text | ~20 GB (추정) |
| DB 증가 | ~5 GB (추정) |
| **Total** | **~90 GB** |

---

## Timeline

| Phase | Task | Parallel With |
|-------|------|---------------|
| 1 | Download | Wikidata 매칭 (현재 진행 중) |
| 2 | Parser setup | - |
| 3 | Test with mini | - |
| 4 | Full extraction | Track A enrichment |
| 5 | DB integration | - |

---

## Notes

### ZIM Format
- MediaWiki 기반 압축 포맷
- 각 문서는 HTML로 저장됨
- 메타데이터: 제목, 카테고리, 내부 링크 포함
- `libzim` Python 라이브러리로 직접 접근 가능

### Wikipedia Infobox Categories
```
{{Infobox person}} → Person
{{Infobox military conflict}} → Event (battle/war)
{{Infobox civilian attack}} → Event
{{Infobox treaty}} → Event
{{Infobox settlement}} → Location
{{Infobox country}} → Location
```

### Parallel Execution
Wikidata 매칭과 병행 가능:
- Wikidata: API 기반, 네트워크 의존
- Kiwix: 로컬 파일, 디스크 I/O 의존
- 서로 다른 리소스 사용 → 동시 진행 가능
