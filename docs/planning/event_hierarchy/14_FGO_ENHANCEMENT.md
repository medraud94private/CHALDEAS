# FGO Data Enhancement Plan

> **상태**: V2 구상
> **작성일**: 2026-01-07
> **목표**: FGO 서번트 ↔ 실제 역사 연결 강화

---

## 프로젝트 목표

> FGO 팬들이 게임에 등장하는 역사적 인물에 대해 더 쉽게 알아볼 수 있도록 한다.

```
FGO 서번트 선택 → 실제 역사 인물 정보 → Historical Chain → 관련 사건/장소
```

---

## 현재 데이터 현황

| 데이터 | 현재 상태 | 필요 작업 |
|--------|----------|----------|
| servants.json | 2개 (길가메시, 레오니다스) | 300+ 서번트 확장 |
| Atlas Academy | 메타정보만 (클래스, 레어도) | 역사 인물 연결 추가 |
| Singularities | 7개 기본 정보 | 실제 역사 시대 연결 |
| Lostbelts | 7개 기본 정보 | 대체 역사 해설 |
| Person (V1) | 5.65M NER 추출 | 서번트 매핑 |

---

## 서번트 ↔ 역사 인물 연결 구조

```
┌─────────────────────────────────────────────────────────┐
│                    FGO 서번트                           │
│  ┌─────────────────────────────────────────────────┐   │
│  │ servant_id: "gilgamesh-archer"                  │   │
│  │ fgo_name: "Gilgamesh"                           │   │
│  │ class: "Archer"                                 │   │
│  │ rarity: 5                                       │   │
│  │ noble_phantasm: "Gate of Babylon"              │   │
│  └─────────────────────────────────────────────────┘   │
└────────────────────────┬────────────────────────────────┘
                         │ 1:N 연결
                         ▼
┌─────────────────────────────────────────────────────────┐
│                 실제 역사 인물 (Person)                  │
│  ┌─────────────────────────────────────────────────┐   │
│  │ person_id: 12345                                │   │
│  │ name: "Gilgamesh"                               │   │
│  │ era: "Ancient Mesopotamia"                      │   │
│  │ birth_year: -2700                               │   │
│  │ role: "King of Uruk"                            │   │
│  │ certainty: "legendary"                          │   │
│  └─────────────────────────────────────────────────┘   │
└────────────────────────┬────────────────────────────────┘
                         │ Historical Chain
                         ▼
┌─────────────────────────────────────────────────────────┐
│                    관련 사건/장소                        │
│  - Epic of Gilgamesh 작성                              │
│  - Uruk 건설                                           │
│  - Enkidu와의 모험                                     │
│  - 불멸 탐구 여정                                       │
└─────────────────────────────────────────────────────────┘
```

---

## 서번트 분류 체계

### 1. 역사적 실존 인물 (Historical)

| 예시 | 역사 기록 |
|------|----------|
| 레오니다스 | 헤로도토스 역사서 |
| 이스칸달 (알렉산더) | 플루타르코스 영웅전 |
| 카이사르 | 로마 기록 |
| 네로 | 타키투스 연대기 |
| 다빈치 | 르네상스 기록 |
| 나폴레옹 | 근대 역사 |

**연결 방식**: Person 테이블 1:1 매칭

### 2. 전설/신화 인물 (Legendary)

| 예시 | 출처 |
|------|------|
| 길가메시 | 길가메시 서사시 |
| 아서왕 | 아서왕 전설 |
| 쿠 훌린 | 켈트 신화 |
| 오리온 | 그리스 신화 |

**연결 방식**: Person (certainty: legendary) + 신화 텍스트 소스

### 3. 신격 (Divine)

| 예시 | 신화 체계 |
|------|----------|
| 이슈타르 | 메소포타미아 |
| 케찰코아틀 | 메소아메리카 |
| 스카사하 | 켈트 |

**연결 방식**: 별도 Deity 테이블 또는 Person (role: deity)

### 4. 가공/복합 인물 (Fictional/Composite)

| 예시 | 설명 |
|------|------|
| 잭 더 리퍼 | 미제 사건 기반 |
| 프랑켄슈타인 | 문학 작품 기반 |
| 셜록 홈즈 | 소설 캐릭터 |

**연결 방식**: 원작 텍스트 소스 연결

---

## 필요 데이터 구조

### servant_profiles 테이블 (신규)

```sql
CREATE TABLE servant_profiles (
    id SERIAL PRIMARY KEY,
    servant_id VARCHAR(100) UNIQUE NOT NULL,

    -- FGO 정보
    fgo_name VARCHAR(200) NOT NULL,
    fgo_name_jp VARCHAR(200),
    servant_class VARCHAR(50) NOT NULL,
    rarity INTEGER,
    noble_phantasm VARCHAR(200),
    noble_phantasm_jp VARCHAR(200),

    -- 역사 연결
    historical_person_id INTEGER REFERENCES persons(id),
    origin_type VARCHAR(50), -- historical, legendary, divine, fictional

    -- 콘텐츠
    historical_background TEXT,
    historical_background_ko TEXT,
    fate_interpretation TEXT,
    fate_interpretation_ko TEXT,

    -- 메타
    atlas_id INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### servant_sources 테이블 (신규)

```sql
CREATE TABLE servant_sources (
    id SERIAL PRIMARY KEY,
    servant_id VARCHAR(100) REFERENCES servant_profiles(servant_id),
    source_id INTEGER REFERENCES sources(id),
    source_type VARCHAR(50), -- primary_historical, secondary_analysis, fate_material
    relevance_score FLOAT
);
```

---

## Singularity/Lostbelt ↔ 역사 연결

### Singularity 매핑

| Singularity | 역사적 배경 | Period 연결 |
|-------------|------------|-------------|
| F: 冬木 | 2004년 성배전쟁 | Modern |
| 1: 오를레앙 | 1431년 백년전쟁 | Late Medieval |
| 2: 세프템 | 60 CE 네로 치세 | Roman Empire |
| 3: 오케아노스 | 1573년 대항해시대 | Age of Discovery |
| 4: 런던 | 1888년 빅토리아 시대 | Industrial Revolution |
| 5: 북미 | 1783년 독립전쟁 | American Revolution |
| 6: 캐멀롯 | 500년경 아서왕 시대 | Post-Roman Britain |
| 7: 바빌로니아 | BC 2655 우루크 | Ancient Mesopotamia |

### Lostbelt 매핑 (대체 역사)

| Lostbelt | 분기점 | 역사적 What-If |
|----------|--------|---------------|
| 1: 아나스타시아 | 1570년 | 러시아 마술 왕조 존속 |
| 2: 괴팅겐 | 1000 BCE | 북유럽 신대 존속 |
| 3: 시황 | 210 BCE | 진시황 불사 달성 |
| 4: 유가 | 11900년경 | 인도 신대 존속 |
| 5: 아틀란티스 | 12000 BCE | 올림포스 존속 |
| 6: 아발론 | 500년경 | 요정국 존속 |
| 7: 황금수 | BC 2655 | 우루크 멸망 |

---

## 사용자 경험 시나리오

### 시나리오 1: 서번트 → 역사 탐색

```
1. FGO 서번트 목록에서 "이스칸달" 선택
2. 서번트 프로필 표시:
   - FGO 정보 (클래스, 보구, 스킬)
   - 실제 역사: "알렉산더 대왕"
3. "역사 보기" 클릭
4. Historical Chain 표시:
   - 마케도니아 왕위 계승 (BC 336)
   - 페르시아 원정 시작 (BC 334)
   - 이수스 전투 (BC 333)
   - 가우가멜라 전투 (BC 331)
   - 인도 원정 (BC 326)
   - 바빌론에서 사망 (BC 323)
5. 각 사건 클릭 → 지구본에서 위치 표시
```

### 시나리오 2: Singularity → 역사 배경

```
1. Singularity "오를레앙" 선택
2. 표시:
   - FGO 스토리 요약
   - 실제 역사: 백년전쟁, 잔 다르크
3. "역사적 배경" 탭
4. 관련 이벤트 체인:
   - 백년전쟁 발발 (1337)
   - 잔 다르크 등장 (1429)
   - 오를레앙 공방전 (1429)
   - 잔 다르크 처형 (1431)
5. 등장 서번트 목록:
   - 잔 다르크 (Ruler)
   - 잔 다르크 (Alter)
   - 질 드 레
```

### 시나리오 3: 역사 → 관련 서번트

```
1. 타임라인에서 "BC 480" 선택
2. "페르시아 전쟁" 이벤트 표시
3. "관련 서번트" 버튼
4. 목록 표시:
   - 레오니다스 (Lancer) - 테르모필레
   - 다리우스 3세 (Berserker) - 페르시아
   - 이스칸달 (Rider) - 마케도니아 (후대)
```

---

## 데이터 수집 우선순위

### Phase 1: 핵심 서번트 (100명)

| 분류 | 대상 | 우선순위 |
|------|------|---------|
| Singularity 주역 | 7개 특이점 메인 서번트 | 최고 |
| 인기 서번트 | 5성 + 스토리 등장 | 높음 |
| 역사적 실존 | 명확한 역사 기록 있음 | 높음 |

### Phase 2: 확장 (200명)

- 4성 서번트
- 이벤트 한정 서번트
- 전설/신화 인물

### Phase 3: 전체 (300+)

- 3성 이하
- 콜라보 서번트
- 신규 추가 서번트

---

## 자동화 가능 영역

### Atlas Academy API 연동

```python
# 서번트 기본 정보 자동 수집
GET /servant/{id}
- name, class, rarity, traits
- noble_phantasm info
- skills, ascension

# 이미 data/raw/atlas_academy/에 수집됨
```

### Wikipedia 연동

```python
# 역사 인물 정보 자동 수집
# 이미 NER로 추출된 Person과 매칭
```

### 수동 작성 필요 영역

- `historical_background`: FGO와 실제 역사 차이 설명
- `fate_interpretation`: 페이트 세계관 해석
- `servant_sources`: 1차 사료 연결

---

## V2 Open Curation 연계

```
Community Curator 역할:
├── 서번트 역사 배경 작성/수정
├── 1차 사료 링크 추가
├── FGO 해석 vs 실제 역사 비교 작성
└── 번역 (EN/KO/JA)
```

**User Data Contribution 연계**:
- 팬들이 가진 역사 자료 업로드
- 학술 논문 링크 추가
- 원문 자료 번역 기여

---

---

## FGO 스토리 스크립트 검색

> **목적**: FGO 스토리를 통해 역사에 관심을 유도하는 진입점

### 데이터 소스

**Atlas Academy Script API**:
```
메타데이터: https://api.atlasacademy.io/nice/{region}/script/search?query=...
스크립트:   https://static.atlasacademy.io/{region}/Script/{chapter}/{id}.txt
```

| 리전 | 상태 | 내용 |
|------|------|------|
| NA | ✅ 사용 가능 | 영어 번역 |
| JP | ✅ 사용 가능 | 일본어 원문 |
| KR | ❌ 없음 | 별도 수집 필요 |

### 스크립트 파일 형식

```
＄01-00-07-03-2-0              # 에피소드 ID
[bgm BGM_EVENT_40]             # 배경음악
[charaFace A 12]               # 캐릭터 표정

＠Gilgamesh                    # 화자
살아남고 싶은 자들은 북쪽 성벽으로 향하라.
[k]                            # 대사 끝

？1：선택지 A                   # 플레이어 선택지
？2：선택지 B
```

### 사용자 경험 시나리오

```
┌─────────────────────────────────────────────────┐
│           FGO Story Search                      │
├─────────────────────────────────────────────────┤
│  🔍 "티아마트"                                   │
│                                                 │
│  📜 바빌로니아 16장 - 비스트 II의 정체           │
│     "티아마트는 비스트 중 하나다.                │
│      우리의 적은 말 그대로 원초의 신이다."       │
│     — 길가메시                                   │
│                                                 │
│  [원문 보기] [역사적 배경]                       │
│                                                 │
│  💡 관련 역사:                                   │
│     → 메소포타미아 창세 신화                    │
│     → 에누마 엘리시 (창조 서사시)               │
│     → 길가메시 서사시                           │
└─────────────────────────────────────────────────┘
```

### 핵심 기능

| 기능 | 설명 |
|------|------|
| 대사 검색 | 캐릭터명, 키워드로 스토리 대사 검색 |
| 챕터 브라우징 | Singularity/Lostbelt 별 스토리 탐색 |
| 역사 연결 | 대사에서 언급된 역사적 사실 → Person/Event 연결 |
| 다국어 지원 | JP 원문 ↔ NA 영어 (KR은 추후) |

### 역사 연결 예시

| FGO 대사 | 연결 역사 |
|----------|----------|
| "인류의 일곱 악" | 메소포타미아 신화, 비스트 개념 |
| "테르모필레에서 300명" | BC 480 페르시아 전쟁 |
| "오를레앙의 마녀" | 1431년 잔 다르크 처형 |
| "진시황의 불로불사" | BC 210 진시황 수은 복용 |

### 기술 구현

```
1. 스크립트 수집
   - Atlas Academy API로 전체 스크립트 다운로드
   - 대사 텍스트 파싱 (연출 코드 분리)

2. 인덱싱
   - Elasticsearch 또는 pgvector로 검색 인덱스
   - 화자, 챕터, 키워드 메타데이터

3. 역사 연결
   - NER로 역사 엔티티 추출
   - Person/Event/Location 자동 매핑

4. UI
   - 스토리 검색 패널
   - 대사 → 역사 하이퍼링크
```

### 저작권 고려

- FGO 스토리: TYPE-MOON / Aniplex 저작권
- **비상업적 팬 프로젝트**로 fair use 주장
- 원문 전체 표시보다 **검색 + 발췌** 방식 권장
- 출처 명시 필수

---

## 참고

- 현재 서번트 데이터: `backend/app/data/showcases/servants.json`
- Atlas Academy 원본: `data/raw/atlas_academy/`
- V1 Person 테이블: `backend/app/models/person.py`
- Open Curation: `docs/planning/v2/OPEN_CURATION_VISION.md`
