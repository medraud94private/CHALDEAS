# CHALDEAS 역사의 고리 (Historical Chain) 컨셉

## 핵심 철학

> "모든 역사는 **누가(Person)** **어디서(Location)** **언제(Time)** **무엇을(Event)**  했는가로 결정된다."

역사는 사건-인물-장소-시간의 4원소가 결합하여 "연결된 고리"를 형성합니다.

---

## 컨셉 예시: 알렉상드르 뒤마의 나폴리 여행기

### 인물 중심의 역사 (Person-centric)

알렉상드르 뒤마의 나폴리 여행기를 읽음으로써:
- **누가**: 알렉상드르 뒤마
- **어떤 시선**: 프랑스 작가로서의 관점
- **언제**: 1843년
- **어디서**: 나폴리

→ "뒤마가 어떤 사람이고, 어떤 시선을 가졌으며, 1843년에 나폴리에 있었다"

### 지역 중심의 역사 (Location-centric)

같은 여행기에서 최초로 "피자"가 언급됩니다:
- **누가**: 나폴리 사람들
- **무엇을**: 피자를 먹음
- **언제**: 1843년
- **어디서**: 나폴리

→ "1843년 나폴리에서 피자가 일상 음식이었다"

### 불확실성 처리

모든 자료가 완벽한 조건을 만족하지는 않습니다:
- **시대 불분명**: 전설, 신화
- **인물 불분명**: 실존 여부 애매한 인물
- **장소 불분명**: 실재인지 메타포인지 불명확

→ `certainty` 필드로 구분: `fact`, `probable`, `legendary`, `mythological`

---

## 4가지 큐레이션 유형

### 1. 인물의 역사 (Person Story)

특정 인물의 생애를 따라가는 사건들의 연쇄

```
알렉산더 대왕의 역사:
  [탄생, 펠라, -356]
    ↓
  [아리스토텔레스에게 교육, 미에자, -343]
    ↓
  [즉위, 펠라, -336]
    ↓
  [이수스 전투, 이수스, -333]
    ↓
  [가우가멜라 전투, 가우가멜라, -331]
    ↓
  [사망, 바빌론, -323]
```

### 2. 장소의 역사 (Place Story)

특정 장소에서 일어난 사건들의 연대기

```
로마의 역사:
  [로마 건국, -753] (legendary)
    ↓
  [왕정 폐지, -509]
    ↓
  [포에니 전쟁, -264]
    ↓
  [카이사르 암살, -44]
    ↓
  [서로마 멸망, 476]
    ↓
  [르네상스, 1400]
    ...
```

### 3. 시대의 역사 (Era Story)

특정 시대의 주요 인물, 장소, 사건 종합

```
고대 그리스 (-500 ~ -323):
  인물: 소크라테스, 플라톤, 아리스토텔레스, 페리클레스, 알렉산더
  장소: 아테네, 스파르타, 테베, 델포이
  사건: 페르시아 전쟁, 펠로폰네소스 전쟁, 마케도니아 정복
```

### 4. 인과 연쇄 (Causal Chain)

원인-결과로 연결된 사건들의 흐름

```
프랑스 대혁명의 원인 체인:
  [계몽주의 사상 확산]
    ↓ (causes)
  [미국 독립 혁명]
    ↓ (inspires)
  [프랑스 재정 위기]
    ↓ (triggers)
  [삼부회 소집]
    ↓ (leads to)
  [바스티유 습격]
    ↓ (causes)
  [왕정 폐지]
```

---

## 데이터 구조

### HistoricalChain (역사의 고리)

```python
class HistoricalChain:
    id: int
    title: str                    # "알렉산더 대왕의 생애"
    title_ko: str                 # 한국어 제목
    description: str
    chain_type: ChainType         # person_story | place_story | era_story | causal_chain

    # 엔티티 참조 (chain_type에 따라 하나만 설정)
    person_id: Optional[int]      # Person Story일 때
    location_id: Optional[int]    # Place Story일 때
    period_id: Optional[int]      # Era Story일 때

    # 승격 시스템
    visibility: Visibility        # user | cached | featured | system
    access_count: int
    created_by_master_id: int
    promoted_at: Optional[datetime]
```

### ChainSegment (고리의 마디)

```python
class ChainSegment:
    id: int
    chain_id: int
    segment_order: int           # 순서
    event_id: int                # 연결된 사건
    narrative: str               # AI 생성 설명
    narrative_ko: str
    connection_type: str         # 이전 세그먼트와의 연결 유형
                                 # causes, follows, part_of, leads_to, inspires
```

---

## 승격 시스템 (Promotion System)

사용자가 생성한 체인이 인기를 얻으면 시스템 레벨로 승격됩니다.

### 승격 레벨

| 레벨 | 설명 | 임계값 |
|-----|------|-------|
| `user` | 사용자 개인 체인 | 초기 상태 |
| `cached` | 캐시된 체인 (다른 사용자도 조회 가능) | 5회 이상 조회 |
| `featured` | 추천 체인 (UI에 노출) | 50회 이상 조회 |
| `system` | 시스템 체인 (영구 보존) | 200회 이상 조회 |

### 초기 시스템 체인

중요 인물/장소/시대에 대해서는 사전에 생성해둡니다:

**Person Stories**:
- 알렉산더 대왕, 카이사르, 공자, 석가모니, 예수, 무함마드
- 플라톤, 아리스토텔레스, 소크라테스
- 레오나르도 다빈치, 미켈란젤로, 셰익스피어

**Place Stories**:
- 로마, 아테네, 예루살렘, 바빌론
- 장안, 낙양, 교토
- 파리, 런던, 비엔나

**Era Stories**:
- 고대 그리스, 로마 제국, 르네상스
- 춘추전국시대, 삼국시대
- 계몽주의, 산업혁명

---

## Braudel의 시간 구조 적용

각 사건과 시대에 Braudel의 3중 시간 구조를 적용합니다:

### temporal_scale 필드

| 값 | 의미 | 예시 |
|---|------|------|
| `evenementielle` | 개별 사건 (일~년) | 카이사르 암살, 바스티유 습격 |
| `conjuncture` | 중기 순환 (수십년~세기) | 르네상스, 산업혁명 |
| `longue_duree` | 장기 구조 (수세기~천년) | 지중해 무역 문화, 유교 문명 |

### 적용 예시

```
피자의 역사:

[longue_duree] 지중해 빵 문화 (BC 3000 ~ 현재)
    ├── [conjuncture] 이탈리아 음식 문화 발전 (1500~1900)
    │       ├── [evenementielle] 뒤마의 나폴리 여행기 (1843)
    │       ├── [evenementielle] 마르게리타 피자 탄생 (1889)
    │       └── [evenementielle] 미국 최초 피자집 (1905)
    └── [conjuncture] 글로벌 피자 확산 (1950~현재)
```

---

## 비용 고려사항

### 체인 생성 비용

| 방식 | 비용 | 용도 |
|-----|------|------|
| 캐시 조회 | $0 | 기존 체인 재사용 |
| GPT-5-nano | ~$0.001/chain | 일반 체인 생성 |
| GPT-5.1-chat-latest | ~$0.01/chain | 복잡한 체인, 품질 검증 |

### 비용 최적화 전략

1. **캐시 우선**: 동일/유사 쿼리는 캐시에서 조회
2. **배치 생성**: 주요 체인은 오프라인에서 미리 생성
3. **점진적 승격**: 인기 있는 체인만 고품질 모델로 재생성
4. **청킹**: 긴 체인은 세그먼트별로 생성

---

## 변경 이력

| 날짜 | 변경 내용 |
|-----|----------|
| 2026-01-01 | 초기 컨셉 문서 작성 |
