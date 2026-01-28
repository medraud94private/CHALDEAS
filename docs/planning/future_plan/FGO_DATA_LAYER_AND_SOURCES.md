# FGO 데이터 레이어 & 소스 문서

## 개요

FGO(Fate/Grand Order) 데이터는 **역사 데이터와 분리된 레이어**로 관리한다.
- 역사 데이터: `universe_id = 1` (canonical, 기준)
- FGO 데이터: `universe_id = 2` (fictional, 파생)

```
┌─────────────────────────────────────────────────────────────┐
│  LAYER 1: Historical (Canonical)                            │
│  - Wikidata 연동                                            │
│  - NER 추출 데이터                                          │
│  - 1차 사료 기반                                            │
└───────────────────────────┬─────────────────────────────────┘
                            │ canonical_id 참조
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  LAYER 2: FGO (Fictional)                                   │
│  - 서번트 프로필                                            │
│  - 게임 메타데이터                                          │
│  - TYPE-MOON 해석                                           │
└─────────────────────────────────────────────────────────────┘
```

---

## 데이터베이스 구조

### universes 테이블

```sql
CREATE TABLE universes (
    id SERIAL PRIMARY KEY,
    code VARCHAR(30) UNIQUE NOT NULL,  -- 'historical', 'fgo'
    name VARCHAR(100) NOT NULL,
    is_canonical BOOLEAN DEFAULT FALSE,
    color VARCHAR(7)  -- UI 색상
);

INSERT INTO universes (code, name, is_canonical, color) VALUES
    ('historical', 'Historical Reality', TRUE, '#00d4ff'),
    ('fgo', 'Fate/Grand Order', FALSE, '#ff6b6b');
```

### persons 테이블 확장

```sql
ALTER TABLE persons ADD COLUMN universe_id INTEGER REFERENCES universes(id) DEFAULT 1;
ALTER TABLE persons ADD COLUMN canonical_id INTEGER REFERENCES persons(id);

-- 예시: 잔느 다르크
-- Historical: id=1, universe_id=1, canonical_id=NULL
-- FGO Ruler: id=1001, universe_id=2, canonical_id=1
-- FGO Alter: id=1002, universe_id=2, canonical_id=1
```

### servant_profiles 테이블 (FGO 전용)

```sql
CREATE TABLE servant_profiles (
    id SERIAL PRIMARY KEY,
    person_id INTEGER REFERENCES persons(id),

    -- FGO 메타
    servant_class VARCHAR(50),  -- Saber, Archer, Lancer, etc.
    rarity INTEGER,             -- 1-5
    noble_phantasm VARCHAR(200),
    fgo_id INTEGER,             -- Atlas Academy ID

    -- 분류
    origin_type VARCHAR(50),    -- historical, legendary, divine, fictional

    -- 콘텐츠
    historical_background TEXT,
    fate_interpretation TEXT
);
```

---

## 쿼리 패턴

### 역사 데이터만 (기본)
```sql
SELECT * FROM persons WHERE universe_id = 1;
```

### FGO 데이터만
```sql
SELECT * FROM persons WHERE universe_id = 2;
```

### 특정 인물의 모든 버전
```sql
SELECT p.*, u.name as universe_name
FROM persons p
JOIN universes u ON p.universe_id = u.id
WHERE p.id = 1 OR p.canonical_id = 1;
```

### API 엔드포인트
```
GET /api/v3/persons?universe=historical  # 역사만 (기본)
GET /api/v3/persons?universe=fgo         # FGO만
GET /api/v3/persons?universe=all         # 전체
GET /api/v3/persons/1/variants           # 파생 버전 조회
```

---

## 소스 책 목록

### 현재 보유 (15권)

| 파일명 | 제목 | 크기 | 청크 | 상태 |
|--------|------|------|------|------|
| greek_roman_myths.txt | Greek/Roman Mythology | 886KB | 370 | ✅ 완료 |
| plato_republic.txt | Plato Republic | 1.27MB | 531 | ✅ 완료 |
| marcus_aurelius_meditations.txt | Marcus Aurelius | 751KB | 313 | ✅ 완료 |
| bulfinch_mythology.txt | Bulfinch Mythology | 688KB | 285 | ✅ 완료 |
| arabian_nights.txt | Arabian Nights | 629KB | 260 | ✅ 완료 |
| odyssey_homer.txt | Homer Odyssey | 718KB | 296 | ✅ 완료 |
| herodotus_histories.txt | Herodotus Histories | 916KB | 383 | ✅ 완료 |
| norse_mythology.txt | Norse Mythology | 632KB | 261 | ✅ 완료 |
| plutarch_lives.txt | Plutarch Lives | 4.32MB | 1842 | 🔄 진행중 |
| mahabharata.txt | Mahabharata | 1.39MB | ~590 | ⏳ 대기 |
| gilgamesh_epic.txt | Gilgamesh Epic | 252KB | ~105 | ⏳ 대기 |
| celtic_mythology.txt | Celtic Mythology | 906KB | ~385 | ⏳ 대기 |
| egyptian_mythology.txt | Egyptian Mythology | 596KB | ~250 | ⏳ 대기 |
| japanese_mythology.txt | Japanese Mythology | 403KB | ~170 | ⏳ 대기 |
| chinese_mythology.txt | Chinese Mythology | 714KB | ~300 | ⏳ 대기 |

---

## FGO 서번트 ↔ 소스 책 매핑

### Gilgamesh Epic
| 서번트 | 클래스 | 역할 |
|--------|--------|------|
| Gilgamesh | Archer/Caster | 주인공 |
| Enkidu | Lancer | 주인공 동료 |
| Ishtar | Archer/Rider | 여신 |
| Ereshkigal | Lancer | 명계의 여신 |
| Siduri | - | 조력자 |

### Mahabharata
| 서번트 | 클래스 | 역할 |
|--------|--------|------|
| Arjuna | Archer | 판다바 영웅 |
| Karna | Lancer | 카우라바 영웅 |
| Rama | Saber | 라마야나 연결 |
| Ashwatthama | Archer | 드로나의 아들 |
| Parvati | Lancer | 신격 |

### Celtic Mythology
| 서번트 | 클래스 | 역할 |
|--------|--------|------|
| Cu Chulainn | Lancer/Caster/Berserker | 울스터 영웅 |
| Scathach | Lancer/Assassin | 전사 여왕 |
| Fergus | Saber | 울스터 왕 |
| Medb | Rider | 코나흐트 여왕 |
| Fionn | Lancer | 피아나 기사단장 |
| Diarmuid | Lancer/Saber | 피아나 기사 |

### Egyptian Mythology
| 서번트 | 클래스 | 역할 |
|--------|--------|------|
| Ozymandias | Rider | 람세스 2세 |
| Cleopatra | Assassin | 프톨레마이오스 왕조 |
| Nitocris | Caster/Assassin | 제6왕조 |
| Sphinx | - | 신화 생물 |

### Norse Mythology
| 서번트 | 클래스 | 역할 |
|--------|--------|------|
| Brynhildr | Lancer | 발키리 |
| Sigurd | Saber | 영웅 |
| Valkyrie | Lancer | 전사 처녀들 |
| Skadi | Caster | 신격 |

### Japanese Mythology
| 서번트 | 클래스 | 역할 |
|--------|--------|------|
| Tamamo-no-Mae | Caster/Lancer | 구미호 |
| Shuten-Douji | Assassin/Caster | 오니 |
| Ibaraki-Douji | Berserker/Lancer | 오니 |
| Ushi Gozen | Avenger | 미나모토 요리미츠 |
| Kintoki | Berserker/Rider | 금태랑 |

### Chinese Mythology
| 서번트 | 클래스 | 역할 |
|--------|--------|------|
| Lu Bu | Berserker | 삼국지 무장 |
| Qin Shi Huang | Ruler | 진시황 |
| Xiang Yu | Berserker | 초패왕 |
| Yu Mei-ren | Assassin | 우희 |
| Nezha | Lancer | 봉신연의 |

### Greek/Roman (기존)
| 서번트 | 클래스 | 역할 |
|--------|--------|------|
| Achilles | Rider | 일리아스 영웅 |
| Hector | Lancer | 트로이 영웅 |
| Heracles | Berserker | 12과업 |
| Medusa | Rider | 고르곤 |
| Medea | Caster | 아르고호 |
| Jason | Saber | 아르고호 선장 |
| Atalante | Archer | 칼리돈 사냥 |
| Chiron | Archer | 켄타우로스 |
| Romulus | Lancer | 로마 건국 |
| Nero | Saber/Caster | 로마 황제 |
| Caligula | Berserker | 로마 황제 |

### Herodotus Histories
| 서번트 | 클래스 | 역할 |
|--------|--------|------|
| Leonidas | Lancer | 테르모필레 |
| Darius III | Berserker | 페르시아 왕 |
| Xerxes | - | (미구현) |

### Plutarch Lives
| 서번트 | 클래스 | 역할 |
|--------|--------|------|
| Alexander (Iskandar) | Rider | 마케도니아 왕 |
| Caesar | Saber | 로마 독재관 |
| Cleopatra | Assassin | 이집트 여왕 |
| Spartacus | Berserker | 검투사 |

### Arabian Nights
| 서번트 | 클래스 | 역할 |
|--------|--------|------|
| Scheherazade | Caster | 화자 |
| Nitocris (Assassin) | Assassin | 아사신 연결 |

### Odyssey
| 서번트 | 클래스 | 역할 |
|--------|--------|------|
| Odysseus | Rider | 주인공 |
| Circe | Caster | 마녀 |
| Penelope | - | (미구현) |

---

## 데이터 임포트 전략

### Phase 1: 책 → NER 추출
```python
# 로컬 모델로 엔티티 추출
persons, locations, events = extract_entities(book_text)
# 결과: extraction_results_local.json
```

### Phase 2: NER → DB 매칭
```python
# 기존 DB와 매칭
for person in extracted_persons:
    match = find_in_db(person)
    if match:
        # 기존 엔티티에 소스 연결
        link_source(match.id, book_source_id)
    else:
        # 새 엔티티 생성
        create_person(person, universe_id=1)
```

### Phase 3: FGO 서번트 연결
```python
# FGO 서번트 임포트 (별도 레이어)
for servant in fgo_servants:
    # 역사 인물 찾기
    canonical = find_canonical(servant.name)

    # FGO Person 생성
    create_person(
        name=servant.name,
        universe_id=2,  # FGO
        canonical_id=canonical.id if canonical else None
    )

    # 서번트 프로필 생성
    create_servant_profile(servant)
```

---

## 현재 FGO 데이터 현황

### 보유 데이터
- `data/raw/atlas_academy/fgo_historical_figures.json` - 서번트 메타 (traits, class, rarity)
- `data/raw/indian_mythology/indian_fgo_servants.json` - 인도 서번트 목록

### 필요 작업
1. [ ] universes 테이블 생성
2. [ ] persons 테이블에 universe_id, canonical_id 추가
3. [ ] servant_profiles 테이블 생성
4. [ ] Atlas Academy 서번트 임포트
5. [ ] 역사 인물 ↔ 서번트 매핑
6. [ ] API 엔드포인트 universe 필터 추가

---

## 처리 스크립트

### 로컬 모델 책 처리
```bash
# 위치: poc/scripts/test_book_extract_local.py
python -u poc/scripts/test_book_extract_local.py

# Batch 2 (추가 책들)
python -u poc/scripts/test_book_extract_local_batch2.py
```

### 결과 파일
- `poc/data/book_samples/extraction_results.json` - GPT-5.1 결과
- `poc/data/book_samples/extraction_results_local.json` - 로컬 모델 결과 (Batch 1)
- `poc/data/book_samples/extraction_results_local_batch2.json` - 로컬 모델 결과 (Batch 2)

### 중단/재시작 기능

스크립트는 청크별 임시저장을 지원한다:

```
poc/data/book_samples/temp/{book}_progress.json
```

**동작 방식:**
1. 매 청크 처리 후 진행상황 자동 저장
2. 중단 후 재실행 시 마지막 청크부터 자동 재개
3. 완료 시 temp 파일 자동 삭제

**저장 데이터:**
```json
{
  "last_chunk": 800,
  "elapsed_sec": 15486.2,
  "persons": ["Alexander", "Caesar", ...],
  "locations": ["Rome", "Athens", ...],
  "concepts": [...],
  "events": [...]
}
```

**사용법:**
```bash
# 시작/재개 (동일 명령)
python -u poc/scripts/test_book_extract_local_batch2.py

# 중단: Ctrl+C 또는 프로세스 종료
# 재실행하면 자동으로 이어서 진행
```

---

## 참고 문서

- `docs/planning/road_to_v3/MULTIVERSE_DATA_MODEL.md` - 멀티버스 데이터 모델 상세
- `docs/planning/v2/FGO_DATA_ENHANCEMENT.md` - FGO 데이터 강화 계획
- `docs/planning/BOOK_EXTRACTION_COMPARISON.md` - GPT vs 로컬 모델 비교
