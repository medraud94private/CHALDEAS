# CHALDEAS 역사학 방법론 참고자료

## 개요

CHALDEAS는 역사를 **사건(Event) - 인물(Person) - 장소(Location) - 시간(Time)**의 4원소 결합으로 이해합니다. 이 문서는 해당 접근법을 뒷받침하는 학술 연구와 표준 온톨로지를 정리합니다.

---

## 1. Event-Centric Knowledge Graphs

역사적 지식을 사건 중심으로 구조화하는 연구들입니다.

### 1.1 EventKG

- **논문**: [EventKG - the Hub of Event Knowledge on the Web](https://arxiv.org/pdf/1905.08794)
- **규모**: 690,000+ 이벤트, 2.3M 시간 관계
- **특징**: 다국어 사건 중심 시간적 지식그래프
- **적용점**: 사건 간 시간적 관계 모델링

### 1.2 WarSampo

- **논문**: [Integrating Historical Person Registers as Linked Open Data](https://link.springer.com/chapter/10.1007/978-3-030-59833-4_8)
- **특징**: 전쟁을 "시공간적 사건 시퀀스"로 표현
- **구조**: 인물/부대/장소가 사건에 참여하는 형태
- **적용점**: 사건-인물-장소 통합 모델의 실제 구현 사례

### 1.3 VisKonnect

- **논문**: [Visually Connecting Historical Figures Through Event Knowledge Graphs](https://arxiv.org/abs/2109.09380)
- **특징**: 역사적 인물들을 공유 사건을 통해 시각적으로 연결
- **적용점**: 인물 간 관계 시각화 방법론

### 1.4 OEKG (Open Event Knowledge Graph)

- **논문**: [OEKG: The Open Event Knowledge Graph](https://www.researchgate.net/publication/368877083_OEKG_The_Open_Event_Knowledge_Graph)
- **특징**: 다국어, 사건 중심, 시간적 지식그래프
- **적용점**: 글로벌 사건 모델링

---

## 2. CIDOC-CRM 온톨로지

### 2.1 개요

- **공식 사이트**: [CIDOC-CRM](https://cidoc-crm.org/)
- **개발 기관**: 국제박물관협회(ICOM) 산하 CIDOC
- **지위**: ISO 21127:2014 국제 표준

### 2.2 핵심 원칙

> "역사는 사람과 사물이 시공간에서 만나 역사를 창조하는 사건들의 분석이다"

**Event-Centric Model**:
- 모든 역사적 사실을 "사건(Event)"을 중심으로 표현
- 사건에 시간, 장소, 참여자가 연결됨

### 2.3 CHALDEAS에 적용할 패턴

```
E5 Event (사건)
  → P7 took place at → E53 Place (장소)
  → P4 has time-span → E52 Time-Span (시간)
  → P11 had participant → E21 Person (인물)
  → P17 was motivated by → E5 Event (원인 사건)
```

### 2.4 확장 모듈

| 모듈 | 용도 |
|-----|------|
| CRMgeo | 지리정보 통합 |
| CRMba | 건축물 기록 |
| CRMdig | 디지털 자산 출처 |

### 2.5 참고 문헌

- [Cultural Heritage Data Management: The Role of Formal Ontology and CIDOC CRM](https://link.springer.com/chapter/10.1007/978-3-319-65370-9_6)

---

## 3. Prosopography (인물학)

### 3.1 정의

Prosopography는 그리스어 'prosopon'(얼굴/사람)과 'graphia'(기록)에서 유래했으며, 특정 역사적/문학적 맥락 내에서 인물 집단을 식별하고 관계를 분석하는 역사 연구 방법입니다.

### 3.2 Lawrence Stone의 2가지 관점

1. **숨겨진 연결 발굴**: 서사에서 명시되지 않은 이해관계와 연결 발견
2. **역할 변화 분석**: 커뮤니티 내 인물들의 역할 변화 추적

### 3.3 Factoid Model

- **개발**: King's College London, John Bradley
- **적용 사례**:
  - PASE (Prosopography of Anglo-Saxon England)
  - PoMS (People of Medieval Scotland)
  - PBW (Prosopography of the Byzantine World)

### 3.4 Network Science와의 결합

> "네트워크 과학 방법론은 역사적 맥락에서 연구 대상의 관계 패턴, 구성, 활동을 분석하는 대안적 방법을 제공한다"

**분석 가능한 질문들**:
- 모든 구성원을 연결하는 최소 단계 수는?
- 가장 많은 다른 구성원과 연결된 인물은?
- 집단 전체의 연결 밀도는?

### 3.5 참고 문헌

- [Prosopographical Networks - Wikipedia](https://en.wikipedia.org/wiki/Prosopographical_network)
- [Social Network Analysis, Prosopography, and History](https://poms.ac.uk/documents/89/1-Starting-points.pdf)
- [Digital Prosopography and Network Analysis](https://senereko.ceres.rub.de/en/hnr-workshop-2015/papers-workshops/digital-prosopography-and-network-analysis/)

---

## 4. Annales School & Longue Durée

### 4.1 Annales 학파 개요

- **창립**: 1920년대, Lucien Febvre, Marc Bloch
- **특징**: 정치사/외교사 중심에서 사회과학적 방법론으로 전환
- **영향**: 프랑스 및 전 세계 역사학에 지대한 영향

### 4.2 Fernand Braudel의 3중 시간 구조

| 시간 층위 | 프랑스어 | 기간 | 내용 | CHALDEAS 적용 |
|----------|---------|------|------|--------------|
| 단기 | Histoire événementielle | 일~년 | 개별 사건, 인물의 행위 | Event 레벨 |
| 중기 | Conjonctures | 수십년~세기 | 경제/사회/정치 순환 | Era/Period 레벨 |
| 장기 | Longue durée | 수세기~천년 | 지리, 기후, 기술, 문명 | Civilization 레벨 |

### 4.3 적용 예시: 나폴리의 피자

- **Événementielle**: 알렉상드르 뒤마가 1843년 나폴리 여행기에서 피자를 언급
- **Conjuncture**: 19세기 이탈리아 통일 운동과 도시 문화
- **Longue durée**: 지중해 무역 문화와 빵/치즈 기반 음식의 전통

### 4.4 참고 문헌

- [Fernand Braudel and the Structures of Historical Time](https://jnnielsen.medium.com/fernand-braudel-and-the-structure-of-historical-time-71a10b8685d8)
- [Annales School - Wikipedia](https://en.wikipedia.org/wiki/Annales_school)
- [Longue durée - Wikipedia](https://en.wikipedia.org/wiki/Longue_dur%C3%A9e)

---

## 5. Historical GIS & Spatial History

### 5.1 역사 GIS의 발전

- **시작**: 1990년대 후반
- **중요 학술지**: Social Science History (2000, Anne Kelly Knowles 편집)
- **확장**: 정량적 연구에서 정성적 연구로 확대

### 5.2 시공간 모델링 방법론

**Event-Based Modeling**:
- 객체를 Object ID, Event ID, TIME stamp로 표현
- 형식: "parent OID – EID and TIME - son OID"
- 역사적 변화를 의미론적으로 추적

### 5.3 HiStory Framework (2025)

- **논문**: [HiStory: Methodology and System for GIS-Based Narrative](https://onlinelibrary.wiley.com/doi/10.1111/tgis.70131)
- **핵심 개념**:
  - 사건을 서사의 핵심으로 위치
  - 계층적 이벤트 트리와 시간 그래프
  - Focalization 메커니즘

### 5.4 Historical GIS 활용 분야

1. 역사적 지도의 디지털화 및 지리참조
2. 인구조사, 교구, 경제 데이터의 지리참조
3. 과거 역사적 장소와 동적 사건의 재구성

### 5.5 참고 문헌

- [Historical GIS Guide](https://spatialhistory.net/guide/historical-gis.html)
- Gregory & Healey, "Historical GIS: structuring, mapping and analysing geographies of the past" (2007)
- Knowles (ed.), "Past Time, Past Place: GIS for History" (2002)

---

## 6. CHALDEAS에의 종합 적용

### 6.1 데이터 모델

```
┌─────────────────────────────────────────────────────────────┐
│                        CIDOC-CRM 패턴                        │
├─────────────────────────────────────────────────────────────┤
│  Event (E5)                                                  │
│    ├── took place at → Location (E53)                       │
│    ├── has time-span → Time (E52) + Braudel's 3 layers     │
│    ├── had participant → Person (E21) + Prosopography       │
│    └── was motivated by → Event (E5) → Causal Chain        │
└─────────────────────────────────────────────────────────────┘
```

### 6.2 큐레이션 유형과 방법론 연결

| 큐레이션 유형 | 적용 방법론 |
|-------------|------------|
| 인물의 역사 (Person Story) | Prosopography, Factoid Model |
| 장소의 역사 (Place Story) | Historical GIS, Spatial History |
| 시대의 역사 (Era Story) | Annales School, Braudel's temporal layers |
| 인과 연쇄 (Causal Chain) | EventKG, CIDOC-CRM P17 relation |

---

## 변경 이력

| 날짜 | 변경 내용 |
|-----|----------|
| 2026-01-01 | 초기 문서 작성 |
