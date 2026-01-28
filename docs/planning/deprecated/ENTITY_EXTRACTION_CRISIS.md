# Entity Extraction Crisis Report

## 현재 상황 (2024-01)

### 뭘 하려고 했나

**목표**: 구텐베르크 책들에서 역사적 엔티티(인물/장소/사건)를 추출하고, DB의 기존 엔티티와 연결

**왜**:
- "이 책에서 나폴레옹이 언급됨" → 소스 추적 (LAPLACE)
- 중복 엔티티 방지
- 지식 그래프 확장

---

## 뭐가 잘못됐나

### 1. 추출 설계 실패

**현재 추출 결과**:
```json
{"persons": ["Richard", "John", "William"]}
```

**문제**:
- "Richard"가 누구? Richard I? Richard III? Richard Nixon?
- 역사에 Richard 수천 명
- 이름만으로 구분 불가

**필요했던 것**:
```json
{
  "persons": [
    {
      "name": "Richard I of England",
      "aliases": ["Richard the Lionheart"],
      "context": "King who led Third Crusade against Saladin"
    }
  ]
}
```

### 2. 매칭 설계 실패

**현재 매칭 로직**:
1. 이름으로 DB 검색
2. embedding 유사도로 후보 찾기
3. LLM으로 확인

**문제**:
- "Richard" embedding → 모든 Richard가 비슷한 유사도
- context 정보 없이 LLM도 구분 못함
- 5단계 파이프라인이 무의미

### 3. 기존 데이터 166권

- 전부 이름만 추출됨
- 매칭 불가능한 상태
- 재추출 필요할 수 있음

---

## 근본적 질문: 뭘 원하는가?

### 최종 목표
1. **책 → 엔티티 추출**: 책에서 역사적 인물/장소/사건 식별
2. **엔티티 → DB 연결**: 이미 DB에 있으면 연결, 없으면 생성
3. **소스 추적**: "나폴레옹은 어떤 책들에서 언급되었나?"
4. **지식 확장**: 새로운 엔티티/관계 발견

### 핵심 요구사항
- **정확한 식별**: "Richard" ≠ 아무 Richard, 특정 Richard
- **중복 방지**: 같은 인물이 다른 이름으로 중복 생성되면 안 됨
- **소스 연결**: 어떤 책의 어떤 부분에서 나왔는지 추적

---

## 해결 방향

### Option A: 추출부터 다시 (Clean)

**프롬프트 개선**:
```
Extract historical entities with FULL identification:
- Use complete names with titles/epithets
- Include distinguishing context
- "Richard the Lionheart, King of England" NOT just "Richard"
```

**장점**: 깔끔, 정확
**단점**: 166권 재추출 (~13일)

### Option B: 매칭 때 context 역추적 (Dirty)

**방법**:
- 기존 chunk_results에서 엔티티 출현 위치 찾기
- 주변 텍스트 (context) 추출
- context 포함해서 매칭

**장점**: 기존 데이터 활용, 빠름
**단점**: 정확도 낮을 수 있음

### Option C: Wikidata 기반 (Smart)

**방법**:
- 추출된 이름 + context로 Wikidata 검색
- Wikidata에서 QID + description 가져옴
- QID로 DB 매칭

**장점**: Wikidata가 disambiguation 해줌
**단점**: API 호출 많음, 비용

---

## 결정 필요

1. **기존 166권 어떻게?** - 재추출 vs 역추적
2. **새 추출 프롬프트** - 어떤 형식으로?
3. **매칭 전략** - embedding vs Wikidata vs 수동

---

## 현재 시스템 상태

- **서버**: http://localhost:8200 실행 중
- **추출 완료**: 166권 (이름만 추출됨)
- **매칭 완료**: 1권 (Beowulf) - 226개 중 24개 매칭, 202개 new
- **DB**: 286,566 persons, 7,379 duplicate QIDs

---

## 교훈

1. **이름만으로는 식별 불가** - context 필수
2. **설계 먼저, 구현 나중** - 파이프라인 전체를 먼저 검증했어야
3. **테스트 데이터로 검증** - 1-2권 먼저 끝까지 돌려보고 문제 파악했어야
