# CHALDEAS Data Collection Status

> Last Updated: 2025-12-31

## Overview

CHALDEAS는 역사 대학원생 수준의 종합 역사 데이터베이스를 구축합니다.
이 문서는 데이터 수집 현황과 재시작 방법을 정리합니다.

---

## Collection Status Summary

| Phase | Status | 완료 | 진행중 | 대기 |
|-------|--------|------|--------|------|
| Phase 1 | ✅ 완료 | 14개 | - | - |
| Phase 2 | 🔄 진행중 | - | 1개 | - |
| Phase 3 | ✅ 완료 | 4개 | - | - |
| Phase 4+ | 📋 계획 | - | - | 10+ |

---

## Phase 1: 기본 데이터 (✅ 완료)

### 위치/지리 데이터

| Source | Command | Data | Size | Status |
|--------|---------|------|------|--------|
| Pleiades | `--source pleiades` | 고대 장소 좌표 | 1.4GB | ✅ 완료 |
| Wikidata | `--source wikidata` | 이벤트/도시/인물 | 8.2MB | ✅ 완료 |
| DBpedia | (별도 스크립트) | 이벤트/장소/인물 | 4.8MB | ✅ 완료 |
| ToposText | `--source topostext` | 고대 장소 8,068개 | ~10MB | ✅ 완료 |

### 고전 텍스트

| Source | Command | Data | Size | Status |
|--------|---------|------|------|--------|
| Perseus | `--source perseus` | 그리스/로마 고전 카탈로그 | 1MB | ✅ 완료 |
| CText | `--source ctext` | 중국 고전 20종 | ~2MB | ✅ 완료 |
| Latin Library | `--source latin_library` | 라틴 텍스트 메타데이터 | 184KB | ✅ 완료 |
| Augustana | `--source augustana` | 그리스/라틴 고전 475종 | ~500KB | ✅ 완료 |

### 신화/종교

| Source | Command | Data | Size | Status |
|--------|---------|------|------|--------|
| Theoi | `--source theoi` | 그리스 신화 736명 | ~2MB | ✅ 완료 |
| Sacred-Texts | `--source sacred_texts` | 종교/신화 961종 | ~1MB | ✅ 완료 |

### FGO 특화

| Source | Command | Data | Size | Status |
|--------|---------|------|------|--------|
| Atlas Academy | `--source atlas_academy` | FGO 서번트 385명 | ~50MB | ✅ 완료 |
| Gamepress | `--source gamepress` | FGO 서번트 427명 | ~1MB | ✅ 완료 |
| Pantheon | `--source pantheon` | 역사 인물 59,902명 | ~30MB | ✅ 완료 |
| Wikipedia | `--source wikipedia` | FGO 서번트 위키 372개 | ~5MB | ✅ 완료 |

---

## Phase 2: 대규모 텍스트 (🔄 진행중)

| Source | Command | Target | Current | Progress | Status |
|--------|---------|--------|---------|----------|--------|
| Gutenberg (역사) | `--source gutenberg --limit 15000` | 12,148권 | ~4,563권 | ~37% | 🔄 진행중 |

---

## Phase 3: 역사 대학원생 필수 자료 (🔄 진행중)

### 1차 사료

| Source | Command | Data | Status | Notes |
|--------|---------|------|--------|-------|
| Yale Avalon | `--source avalon` | 법/역사/외교 707개 문서 | ✅ 완료 | 100개 상세 수집 |
| Fordham Sourcebooks | `--source fordham` | 고대/중세/근대 180개 | ✅ 완료 | 일부 서버 500 에러 |

### 참고 자료

| Source | Command | Data | Status | Notes |
|--------|---------|------|--------|-------|
| World History Encyclopedia | `--source worldhistory` | 역사 503개 문서 | ✅ 완료 | 200개 상세 수집 |
| Stanford Encyclopedia | `--source stanford_encyclopedia` | 철학 1,847개 엔트리 | ✅ 완료 | 200개 상세 수집 |

---

## Phase 3.5: FGO 커버리지 확장 (🆕 신규)

> FGO 특이점/이문대 커버리지 확장을 위한 추가 데이터

| Source | Command | 내용 | 예상 용량 | Status |
|--------|---------|------|-----------|--------|
| Arthurian | `--source arthurian` | 아서왕 전설 (카멜롯/아발론) | ~5MB | 📋 대기 |
| Russian History | `--source russian_history` | 러시아/동유럽사 (LB1) | ~3MB | 📋 대기 |
| Mesoamerican | `--source mesoamerican` | 아즈텍/마야/잉카 (LB7) | ~5MB | 📋 대기 |
| Indian Mythology | `--source indian_mythology` | 인도 신화/역사 (LB4) | ~5MB | 📋 대기 |

### FGO 커버리지 매핑

| 특이점/이문대 | 주요 데이터 소스 |
|--------------|-----------------|
| 오를레앙 (1431) | gutenberg, fordham |
| 셉템 (60AD) | theoi, fordham, gutenberg |
| 카멜롯 (1273) | **arthurian** ✨ |
| 바빌로니아 (-2600) | sacred_texts, theoi |
| 아나스타시아 (LB1) | **russian_history** ✨ |
| 괴터데머룽 (LB2) | theoi, sacred_texts |
| SIN (LB3) | ctext |
| 유가 크셰트라 (LB4) | **indian_mythology** ✨ |
| 아틀란티스/올림포스 (LB5) | theoi |
| 아발론 르 페 (LB6) | **arthurian** ✨ |
| 나우이 믹틀란 (LB7) | **mesoamerican** ✨ |

---

## Phase 4+: 확장 계획 (📋 대기)

> 상세 계획은 `DATA_COLLECTION_PLAN.md` 참조

| Source | 내용 | 예상 용량 | 우선순위 |
|--------|------|-----------|----------|
| Gutenberg (전체) | 77,000권 | ~50GB | ⭐⭐⭐ |
| Internet Archive | 역사 서적 | ~100GB+ | ⭐⭐ |
| HathiTrust | 공개 도서 | ~3TB | ⭐ |
| LoC Newspapers | 미국 역사 신문 | ~50GB | ⭐⭐ |

---

## How to Resume Collection

### 기본 명령어
```bash
cd C:\Projects\Chaldeas
python data/scripts/collect_all.py --source <SOURCE_NAME>
```

### Phase 1 소스 재실행
```bash
# 위치 데이터
python data/scripts/collect_all.py --source pleiades
python data/scripts/collect_all.py --source wikidata
python data/scripts/collect_all.py --source topostext

# 고전 텍스트
python data/scripts/collect_all.py --source perseus
python data/scripts/collect_all.py --source ctext
python data/scripts/collect_all.py --source latin_library
python data/scripts/collect_all.py --source augustana

# 신화/종교
python data/scripts/collect_all.py --source theoi
python data/scripts/collect_all.py --source sacred_texts

# FGO 데이터
python data/scripts/collect_all.py --source atlas_academy
python data/scripts/collect_all.py --source gamepress
python data/scripts/collect_all.py --source pantheon
python data/scripts/collect_all.py --source wikipedia
```

### Phase 2 소스 재실행
```bash
# 이미 받은 파일은 자동 스킵됨
python data/scripts/collect_all.py --source gutenberg --limit 15000
```

### Phase 3 소스 재실행
```bash
python data/scripts/collect_all.py --source avalon
python data/scripts/collect_all.py --source fordham
python data/scripts/collect_all.py --source worldhistory
python data/scripts/collect_all.py --source stanford_encyclopedia
```

---

## Data Directory Structure

```
data/raw/
├── pleiades/               # 고대 장소 (Phase 1)
├── wikidata/               # 위키데이터 (Phase 1)
├── dbpedia/                # DBpedia (Phase 1)
├── topostext/              # ToposText 장소 (Phase 1)
├── perseus/                # 그리스/로마 고전 (Phase 1)
├── ctext/                  # 중국 고전 (Phase 1)
├── latin_library/          # 라틴 텍스트 (Phase 1)
├── augustana/              # 그리스/라틴 고전 (Phase 1)
├── theoi/                  # 그리스 신화 (Phase 1)
├── sacred_texts/           # 종교/신화 (Phase 1)
├── atlas_academy/          # FGO 서번트 (Phase 1)
├── gamepress/              # FGO 로어 (Phase 1)
├── pantheon/               # 역사 인물 (Phase 1)
├── wikipedia/              # 위키피디아 (Phase 1)
├── gutenberg/              # Gutenberg 도서 (Phase 2)
├── avalon/                 # Yale Avalon (Phase 3) ✅ NEW
├── fordham/                # Fordham Sourcebooks (Phase 3) ✅ NEW
├── worldhistory/           # World History Encyclopedia (Phase 3) ✅ NEW
└── stanford_encyclopedia/  # Stanford Encyclopedia (Phase 3) 🔄 NEXT
```

---

## Collectors List

### Phase 1 Collectors (14개)

| File | Source | URL |
|------|--------|-----|
| `collectors/pleiades.py` | Pleiades Gazetteer | https://pleiades.stoa.org/ |
| `collectors/wikidata.py` | Wikidata | https://query.wikidata.org/ |
| `collectors/dbpedia.py` | DBpedia | https://dbpedia.org/sparql |
| `collectors/topostext.py` | ToposText | https://topostext.org/ |
| `collectors/perseus.py` | Perseus Digital Library | https://www.perseus.tufts.edu/ |
| `collectors/ctext.py` | Chinese Text Project | https://api.ctext.org/ |
| `collectors/latin_library.py` | The Latin Library | https://thelatinlibrary.com/ |
| `collectors/bibliotheca_augustana.py` | Bibliotheca Augustana | https://www.hs-augsburg.de/~harsch/ |
| `collectors/theoi.py` | Theoi Project | https://www.theoi.com/ |
| `collectors/sacred_texts.py` | Sacred-Texts.com | https://sacred-texts.com/ |
| `collectors/atlas_academy.py` | Atlas Academy (FGO) | https://api.atlasacademy.io/ |
| `collectors/fgo_gamepress.py` | FGO Gamepress | https://fgo.gamepress.gg/ |
| `collectors/pantheon.py` | MIT Pantheon | https://pantheon.world/ |
| `collectors/wikipedia.py` | Wikipedia API | https://en.wikipedia.org/w/api.php |

### Phase 2 Collectors (1개)

| File | Source | URL |
|------|--------|-----|
| `collectors/gutenberg.py` | Project Gutenberg | https://www.gutenberg.org/ |

### Phase 3 Collectors (4개)

| File | Source | URL | Status |
|------|--------|-----|--------|
| `collectors/avalon.py` | Yale Avalon Project | https://avalon.law.yale.edu/ | ✅ 완료 |
| `collectors/fordham.py` | Fordham Sourcebooks | https://sourcebooks.fordham.edu/ | ✅ 완료 |
| `collectors/worldhistory.py` | World History Encyclopedia | https://www.worldhistory.org/ | ✅ 완료 |
| `collectors/stanford_encyclopedia.py` | Stanford Encyclopedia | https://plato.stanford.edu/ | 🔄 진행 예정 |

---

## Storage Estimates

| Category | Size |
|----------|------|
| Phase 1 완료 데이터 | ~1.6GB |
| Phase 2 Gutenberg 역사 (12,148권) | ~6.4GB |
| Phase 3 완료 예상 | ~500MB |
| **현재 총합** | **~8.5GB** |

---

## Known Issues

| Issue | Status | Solution |
|-------|--------|----------|
| Gutenberg Windows 유니코드 | ✅ 수정됨 | ASCII 변환 |
| Theoi URL 구조 변경 | ✅ 수정됨 | 새 URL 적용 |
| ToposText JSON-LD 파싱 에러 | ⚠️ 부분 | GeoJSON만 사용 |
| Fordham 일부 소스북 500 에러 | ⚠️ 서버측 | 접근 가능한 것만 수집 |

---

## Next Steps

1. [x] Phase 1 완료
2. [x] Avalon 수집 완료
3. [x] Fordham 수집 완료
4. [x] World History 수집 완료
5. [ ] Stanford Encyclopedia 수집
6. [ ] Gutenberg 역사 다운로드 완료 대기
7. [ ] `python data/scripts/transform_data.py` 실행
8. [ ] `python data/scripts/import_to_db.py` 실행

---

## Related Documents

- `docs/DATA_COLLECTION_PLAN.md` - 전체 수집 마스터 플랜 (Phase 4-5 포함)
- `docs/README.md` - 프로젝트 개요
