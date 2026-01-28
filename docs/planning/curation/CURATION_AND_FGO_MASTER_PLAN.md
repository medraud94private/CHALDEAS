# 큐레이션 & FGO 마스터 플랜

> 최종 수정: 2026-01-27
> 상태: 기획 확정

---

## 1. 현재 구현 상태

### 1.1 완료된 인프라

| 구분 | 내용 | 상태 |
|------|------|------|
| **Sources API** | 책/문서 조회, 멘션 통계 | ✅ 운영중 |
| **Person Sources API** | 인물별 관련 책 조회 | ✅ 운영중 |
| **Story API** | 인물 스토리 → 지도 노드 | ✅ 운영중 |
| **Book Extractor** | Ollama 기반 책 추출 UI | ✅ 운영중 |
| **Frontend Sources UI** | 인물 상세에 "관련 책" 표시 | ✅ 운영중 |

### 1.2 DB 현황

```
sources: 88,903개
├── gutenberg: 105개 (Book Extractor로 추출)
└── document: 76,023개 (기존 파이프라인)

text_mentions: 청크별 저장
├── person 멘션
├── location 멘션
└── event 멘션

persons: 275,343개
├── QID 있음: 91,596개 (33%)
└── QID 없음: 183,747개 (67%)
```

### 1.3 Book Extractor 자동화 플로우

```
책(ZIM) → Ollama 추출 → Context 생성 → DB 매칭 → text_mentions 저장
                ↓                              ↓
         auto_context: true           auto_db_match: true
```

---

## 2. 큐레이션 시스템 설계

### 2.1 목표

**현재**: 이벤트 데이터만 표시 (노드 = 이벤트)
**목표**: 각 노드에 **내러티브 스토리 + 1차 사료 인용** 추가

```
[현재]                           [목표]
노드: 오를레앙 해방              노드: 오를레앙 해방
연도: 1429                       연도: 1429년 4월 29일
위치: 오를레앙                   위치: 오를레앙, 프랑스
설명: (짧은 텍스트)
                                 [내러티브]
                                 "1429년 4월, 잔 다르크는 4천 명의
                                 병사를 이끌고 오를레앙에 도착했다..."

                                 [원본 출처]
                                 📜 "Le 29 avril, la Pucelle..."
                                    - Journal du Siège d'Orléans
```

### 2.2 DB 테이블

#### story_contents (스토리 콘텐츠)

```sql
CREATE TABLE story_contents (
    id SERIAL PRIMARY KEY,

    -- 대상 지정
    story_type VARCHAR(20) NOT NULL,  -- 'person', 'place', 'arc'
    subject_id INTEGER NOT NULL,       -- person_id, location_id, arc_id
    event_id INTEGER REFERENCES events(id),
    node_order INTEGER NOT NULL,

    -- 내러티브 (언어별)
    narrative_en TEXT,
    narrative_ko TEXT,
    narrative_ja TEXT,

    -- 페르소나
    persona VARCHAR(20) DEFAULT 'official',  -- 'official', 'mash', 'leonardo'

    -- 생성 정보
    generated_by VARCHAR(50),          -- 'gpt-4o', 'gpt-5-nano', 'manual'
    generated_at TIMESTAMP DEFAULT NOW(),

    -- 검증
    is_verified BOOLEAN DEFAULT FALSE,
    verified_by VARCHAR(100),
    verified_at TIMESTAMP,

    UNIQUE(story_type, subject_id, event_id, persona)
);

CREATE INDEX idx_story_contents_subject ON story_contents(story_type, subject_id);
CREATE INDEX idx_story_contents_event ON story_contents(event_id);
```

#### story_sources (출처 연결)

```sql
CREATE TABLE story_sources (
    id SERIAL PRIMARY KEY,
    story_content_id INTEGER REFERENCES story_contents(id) ON DELETE CASCADE,

    -- 출처 정보
    source_type VARCHAR(20),           -- 'primary', 'secondary', 'book'
    source_id INTEGER REFERENCES sources(id),  -- DB 내 소스 연결

    -- 인용문
    title VARCHAR(500),                -- 출처 제목
    author VARCHAR(200),
    year INTEGER,
    excerpt TEXT,                      -- 원문 발췌
    excerpt_translation TEXT,          -- 번역
    page_reference VARCHAR(100),

    -- 신뢰도
    reliability VARCHAR(20) DEFAULT 'medium',  -- 'high', 'medium', 'low'

    display_order INTEGER DEFAULT 0
);

CREATE INDEX idx_story_sources_content ON story_sources(story_content_id);
```

### 2.3 페르소나 시스템

| 페르소나 | 톤 | 말투 | 용도 |
|----------|-----|------|------|
| **official** | 다큐멘터리/백과사전 | 격식체 | 기본값, 학습용 |
| **mash** | 따뜻하고 친근 | 해요체 | 친근한 안내 |
| **leonardo** | 자신감/장난기 | 반말 | 재미있는 설명 |

#### 페르소나 프롬프트 예시

```python
PERSONA_PROMPTS = {
    "official": """
당신은 역사 다큐멘터리 내레이터입니다.
- 객관적이고 사실에 기반한 설명
- 격식체 사용
- 200-300자 내외
""",
    "mash": """
당신은 마슈 키리에라이트입니다.
- 따뜻하고 친근한 톤
- "~해요", "~이에요" 말투
- 선배를 안내하듯 설명
- 200-300자 내외
""",
    "leonardo": """
당신은 레오나르도 다 빈치입니다.
- 자신감 넘치고 약간 장난스러운 톤
- 반말 사용
- 천재적 통찰을 곁들인 설명
- 200-300자 내외
"""
}
```

### 2.4 Curator AI 파이프라인

```
[Input]
- event_id: 12345
- person_id: 789
- persona: "mash"
- language: "ko"

[Process]
1. 이벤트 정보 조회 (events 테이블)
2. 관련 소스 조회 (text_mentions → sources)
3. 1차 사료 검색 (있으면)
4. 페르소나 프롬프트 적용
5. LLM 내러티브 생성 (gpt-5-nano 또는 gpt-4o-mini)
6. 출처 포맷팅

[Output]
{
  "narrative": "오를레앙에 도착했을 때, 도시는 이미 7개월째...",
  "sources": [
    {
      "title": "Journal du Siège d'Orléans",
      "excerpt": "Le 29 avril...",
      "translation": "4월 29일..."
    }
  ]
}
```

### 2.5 생성 전략

#### Option A: 사전 생성 (Pre-generation)
- 유명 인물 Top 1,000명에 대해 미리 생성
- 3 페르소나 × 3 언어 = 9개/인물
- 비용: ~$50-100 (1회성)

#### Option B: On-demand 생성
- 사용자 요청 시 실시간 생성
- DB에 캐싱 (재요청 시 즉시 반환)
- 첫 로딩: 3-5초, 이후: 즉시

**권장: Option B (On-demand)** - 비용 효율적, 실제 필요한 것만 생성

---

## 3. FGO 레이어 설계

### 3.1 멀티버스 모델

```
┌─────────────────────────────────────────────────────────────┐
│  LAYER 1: Historical (Canonical) - universe_id = 1          │
│  ├── Wikidata 연동 (QID)                                    │
│  ├── 책에서 NER/LLM 추출                                    │
│  └── 1차 사료 기반                                          │
└───────────────────────────┬─────────────────────────────────┘
                            │ canonical_id 참조
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  LAYER 2: FGO (Fictional) - universe_id = 2                 │
│  ├── 서번트 프로필                                          │
│  ├── 클래스, 보구, 레어도                                   │
│  └── TYPE-MOON 해석                                         │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 DB 테이블

#### universes (세계관)

```sql
CREATE TABLE universes (
    id SERIAL PRIMARY KEY,
    code VARCHAR(30) UNIQUE NOT NULL,  -- 'historical', 'fgo', 'strange_fake'
    name VARCHAR(100) NOT NULL,
    name_ko VARCHAR(100),
    is_canonical BOOLEAN DEFAULT FALSE,
    color VARCHAR(7),                   -- UI 색상 (#00d4ff)
    icon VARCHAR(50),                   -- 아이콘
    created_at TIMESTAMP DEFAULT NOW()
);

INSERT INTO universes (code, name, name_ko, is_canonical, color) VALUES
    ('historical', 'Historical Reality', '역사적 현실', TRUE, '#00d4ff'),
    ('fgo', 'Fate/Grand Order', '페이트/그랜드 오더', FALSE, '#ff6b6b');
```

#### persons 테이블 확장

```sql
-- 기존 persons 테이블에 컬럼 추가
ALTER TABLE persons ADD COLUMN universe_id INTEGER REFERENCES universes(id) DEFAULT 1;
ALTER TABLE persons ADD COLUMN canonical_id INTEGER REFERENCES persons(id);

-- 예시 데이터
-- Historical Joan of Arc: id=100, universe_id=1, canonical_id=NULL
-- FGO Ruler Jeanne:       id=2001, universe_id=2, canonical_id=100
-- FGO Alter Jeanne:       id=2002, universe_id=2, canonical_id=100
```

#### servant_profiles (FGO 전용)

```sql
CREATE TABLE servant_profiles (
    id SERIAL PRIMARY KEY,
    person_id INTEGER REFERENCES persons(id) ON DELETE CASCADE,

    -- FGO 기본 정보
    servant_class VARCHAR(50) NOT NULL,  -- Saber, Archer, Lancer, Rider, Caster, Assassin, Berserker, Extra
    rarity INTEGER CHECK (rarity BETWEEN 1 AND 5),

    -- 보구
    noble_phantasm_name VARCHAR(200),
    noble_phantasm_name_jp VARCHAR(200),
    noble_phantasm_rank VARCHAR(10),
    noble_phantasm_type VARCHAR(50),     -- Anti-Unit, Anti-Army, Anti-World

    -- Atlas Academy 연동
    atlas_id INTEGER,                    -- Atlas Academy Servant ID

    -- 분류
    origin_type VARCHAR(50),             -- historical, legendary, divine, fictional
    gender VARCHAR(20),
    attribute VARCHAR(20),               -- Human, Earth, Sky, Star, Beast

    -- FGO 콘텐츠
    historical_fact TEXT,                -- 실제 역사적 사실
    fate_interpretation TEXT,            -- TYPE-MOON 해석
    bond_story TEXT,                     -- 인연 스토리 요약

    -- 이미지
    portrait_url TEXT,
    sprite_url TEXT,

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    UNIQUE(person_id)
);

CREATE INDEX idx_servant_profiles_class ON servant_profiles(servant_class);
CREATE INDEX idx_servant_profiles_rarity ON servant_profiles(rarity);
```

### 3.3 API 설계

```
# 기본 조회 (역사만 - 기본값)
GET /api/v1/persons?universe=historical

# FGO만
GET /api/v1/persons?universe=fgo

# 전체
GET /api/v1/persons?universe=all

# 특정 인물의 모든 버전 (역사 + FGO 파생)
GET /api/v1/persons/{id}/variants

# 서번트 프로필
GET /api/v1/servants/{person_id}/profile

# 서번트 목록 (클래스별)
GET /api/v1/servants?class=Saber&rarity=5
```

---

## 4. 서번트 ↔ 책 매핑

### 4.1 카테고리별 서번트 & 추천 책

#### 그리스/로마 (~50명)
| 서번트 | 클래스 | 원전 책 | Gutenberg ID |
|--------|--------|---------|--------------|
| Achilles | Rider | Iliad | 6130 |
| Heracles | Berserker | Greek Myths | - |
| Hector | Lancer | Iliad | 6130 |
| Jason | Saber | Argonautica | 830 |
| Medea | Caster | Argonautica | 830 |
| Medusa | Rider | Greek Myths | - |
| Odysseus | Rider | Odyssey | ✅ 보유 |
| Circe | Caster | Odyssey | ✅ 보유 |
| Nero | Saber/Caster | Plutarch | ✅ 보유 |
| Caesar | Saber | Plutarch | ✅ 보유 |
| Alexander | Rider | Plutarch | ✅ 보유 |

#### 아서왕 전설 (~20명)
| 서번트 | 클래스 | 원전 책 | Gutenberg ID |
|--------|--------|---------|--------------|
| Altria | Saber | Le Morte d'Arthur | 1251 |
| Merlin | Caster | Le Morte d'Arthur | 1251 |
| Lancelot | Saber/Berserker | Le Morte d'Arthur | 1251 |
| Mordred | Saber | Le Morte d'Arthur | 1251 |
| Gawain | Saber | Le Morte d'Arthur | 1251 |
| Tristan | Archer | Tristan and Iseult | 14244 |

#### 켈트/아일랜드 (~15명)
| 서번트 | 클래스 | 원전 책 | Gutenberg ID |
|--------|--------|---------|--------------|
| Cu Chulainn | Lancer | Celtic Mythology | ✅ 보유 |
| Scathach | Lancer | Celtic Mythology | ✅ 보유 |
| Medb | Rider | Cattle Raid of Cooley | 16464 |
| Fionn | Lancer | Gods and Fighting Men | 14465 |
| Diarmuid | Lancer | Gods and Fighting Men | 14465 |

#### 노르드 (~10명)
| 서번트 | 클래스 | 원전 책 | Gutenberg ID |
|--------|--------|---------|--------------|
| Sigurd | Saber | Volsunga Saga | 1152 |
| Brynhildr | Lancer | Volsunga Saga | 1152 |
| Valkyrie | Lancer | Poetic Edda | 14726 |
| Skadi | Caster | Prose Edda | 18947 |

#### 인도 (~15명)
| 서번트 | 클래스 | 원전 책 | Gutenberg ID |
|--------|--------|---------|--------------|
| Arjuna | Archer | Mahabharata | ✅ 보유 |
| Karna | Lancer | Mahabharata | ✅ 보유 |
| Rama | Saber | Ramayana | 24869 |
| Ashwatthama | Archer | Mahabharata | ✅ 보유 |

#### 메소포타미아 (~8명)
| 서번트 | 클래스 | 원전 책 | Gutenberg ID |
|--------|--------|---------|--------------|
| Gilgamesh | Archer/Caster | Epic of Gilgamesh | ✅ 보유 |
| Enkidu | Lancer | Epic of Gilgamesh | ✅ 보유 |
| Ishtar | Archer | Epic of Gilgamesh | ✅ 보유 |
| Ereshkigal | Lancer | Descent of Inanna | - |

#### 일본 (~40명)
| 서번트 | 클래스 | 원전 책 | Gutenberg ID |
|--------|--------|---------|--------------|
| Musashi | Saber | Book of Five Rings | 17007 |
| Tamamo | Caster | Japanese Mythology | ✅ 보유 |
| Shuten | Assassin | Japanese Mythology | ✅ 보유 |
| Raikou | Berserker | Tale of Heike | 웹 |

#### 중국 (~15명)
| 서번트 | 클래스 | 원전 책 | Gutenberg ID |
|--------|--------|---------|--------------|
| Lu Bu | Berserker | Romance of Three Kingdoms | 웹 |
| Zhuge Liang | Caster | Romance of Three Kingdoms | 웹 |
| Qin Shi Huang | Ruler | Records of Grand Historian | 웹 |
| Xuanzang | Caster | Journey to the West | 웹 |

#### 영문학 (~15명)
| 서번트 | 클래스 | 원전 책 | Gutenberg ID |
|--------|--------|---------|--------------|
| Sherlock Holmes | Ruler | Complete Sherlock Holmes | 1661 |
| Moriarty | Archer | Complete Sherlock Holmes | 1661 |
| Frankenstein | Berserker | Frankenstein | 84 |
| Jekyll/Hyde | Assassin | Dr Jekyll and Mr Hyde | 43 |
| Edmond Dantes | Avenger | Count of Monte Cristo | 1184 |

### 4.2 책 다운로드 우선순위

#### Tier 1: 다수 서번트 커버 (10명+)
| 순위 | 책 | 서번트 수 | ID | 상태 |
|------|-----|----------|-----|------|
| 1 | Le Morte d'Arthur | ~20 | 1251 | ⏳ |
| 2 | Iliad | ~15 | 6130 | ⏳ |
| 3 | Complete Sherlock Holmes | ~5 | 1661 | ⏳ |

#### Tier 2: 중요 서번트 커버 (5-10명)
| 순위 | 책 | 서번트 수 | ID | 상태 |
|------|-----|----------|-----|------|
| 4 | Volsunga Saga | ~6 | 1152 | ⏳ |
| 5 | Cattle Raid of Cooley | ~8 | 16464 | ⏳ |
| 6 | Ramayana | ~5 | 24869 | ⏳ |

#### Tier 3: 개별 서번트 원전
| 책 | 서번트 | ID | 상태 |
|----|--------|-----|------|
| Frankenstein | Frankenstein | 84 | ⏳ |
| Count of Monte Cristo | Edmond Dantes | 1184 | ⏳ |
| Book of Five Rings | Musashi | 17007 | ⏳ |

---

## 5. 구현 로드맵

### Phase 1: DB 스키마 (1-2일)
- [ ] `story_contents` 테이블 생성
- [ ] `story_sources` 테이블 생성
- [ ] `universes` 테이블 생성
- [ ] `servant_profiles` 테이블 생성
- [ ] `persons` 테이블에 `universe_id`, `canonical_id` 추가
- [ ] Alembic 마이그레이션

### Phase 2: FGO 데이터 임포트 (2-3일)
- [ ] Atlas Academy 서번트 데이터 다운로드
- [ ] FGO persons 레코드 생성 (universe_id=2)
- [ ] servant_profiles 임포트
- [ ] 역사 인물 ↔ 서번트 canonical_id 매핑

### Phase 3: Curator AI 파이프라인 (2-3일)
- [ ] `poc/scripts/generate_story_content.py` 생성
- [ ] 페르소나 프롬프트 구현
- [ ] On-demand 생성 API 추가
- [ ] DB 캐싱 로직

### Phase 4: 잔 다르크 시범 (1일)
- [ ] 잔 다르크 11개 노드 스토리 생성
- [ ] 3 페르소나 × 3 언어 테스트
- [ ] 1차 사료 연결 (수동)

### Phase 5: API 확장 (1-2일)
- [ ] `/api/v1/persons?universe=` 필터 추가
- [ ] `/api/v1/persons/{id}/variants` 엔드포인트
- [ ] `/api/v1/servants` 엔드포인트
- [ ] `/api/v1/story/person/{id}` 에 narrative 포함

### Phase 6: Frontend 확장 (2-3일)
- [ ] StoryModal에 내러티브 영역 추가
- [ ] 페르소나/언어 선택 UI
- [ ] 출처 인용 표시
- [ ] FGO 서번트 뷰 (역사 인물과 연결)

### Phase 7: 책 확장 (ongoing)
- [ ] Tier 1 책 다운로드 & 추출
- [ ] Tier 2 책 다운로드 & 추출
- [ ] 서번트-엔티티 자동 매핑 개선

---

## 6. 비용 추정

### 큐레이션 내러티브 생성

| 모델 | 토큰 비용 | 1인물 (5노드, 1언어) | 비고 |
|------|----------|---------------------|------|
| gpt-5-nano | $0.10/1M in, $0.40/1M out | ~$0.01 | 권장 |
| gpt-4o-mini | $0.15/1M in, $0.60/1M out | ~$0.015 | 품질↑ |
| gpt-4o | $2.50/1M in, $10/1M out | ~$0.25 | 최고품질 |

### 시나리오별 비용

| 시나리오 | 인물 수 | 비용 (gpt-5-nano) |
|----------|---------|-------------------|
| 잔 다르크만 (3언어×3페르소나) | 1 | ~$0.50 |
| Top 100 유명 인물 | 100 | ~$5 |
| Top 1,000 인물 | 1,000 | ~$50 |
| On-demand (월간 예상) | - | ~$5-10/월 |

---

## 7. 관련 파일

### 기존 문서 (deprecated 예정)
- `docs/planning/STORY_CURATION_SYSTEM.md` → 이 문서로 통합
- `docs/planning/FGO_DATA_LAYER_AND_SOURCES.md` → 이 문서로 통합
- `docs/planning/FGO_SERVANT_BOOK_MAPPING.md` → 이 문서로 통합

### 데이터 파일
- `data/raw/atlas_academy/` - FGO 서번트 원본 데이터
- `poc/data/book_contexts/` - 책 컨텍스트 추출 결과

### 스크립트 (생성 예정)
- `poc/scripts/import_fgo_servants.py`
- `poc/scripts/generate_story_content.py`
- `poc/scripts/map_servants_to_historical.py`

---

## 8. 참고: 잔 다르크 쇼케이스 예시

### 노드 구성 (11개)
1. 출생 (1412, Domrémy)
2. 신의 목소리 (1425, Domrémy)
3. 시농 성 알현 (1429, Chinon)
4. 오를레앙 해방 (1429, Orléans)
5. 파테 전투 (1429, Patay)
6. 랭스 대관식 (1429, Reims)
7. 파리 공성전 (1429, Paris)
8. 콩피에뉴 포로 (1430, Compiègne)
9. 재판 (1431, Rouen)
10. 화형 (1431, Rouen)
11. 복권 (1456, Paris)

### 내러티브 예시 (mash 페르소나, 한국어)

**노드 4: 오를레앙 해방**
```
선배, 이곳이 오를레앙이에요. 1429년 4월, 잔 다르크가 도착했을 때
이 도시는 이미 7개월째 잉글랜드군에 포위되어 있었어요.

그녀가 이끄는 4천 명의 군대가 도착하고 단 9일 만에 포위가 풀렸다니,
정말 기적 같은 일이죠? 이 승리가 백년전쟁의 전환점이 되었어요.

📜 원본 기록
"4월 29일, 라 퓌셀(처녀)이 오를레앙에 입성하였다..."
- 오를레앙 포위전 일지 (Journal du Siège d'Orléans)
```
