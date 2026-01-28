# 관계 품질 개선 계획

## 현재 상태 (2026-01-19)

### 관계 생성 방법
1. **하이퍼링크 기반**: Wikipedia 내부 링크 → 관계
2. **본문 언급 기반**: content에서 엔티티명 검색 → 관계
3. **공유 소스 기반**: 같은 source에 언급된 엔티티 → 관계

### 발견된 품질 이슈

#### 1. 시대 불일치 관계
**예시**: French Revolution 참여자로 Socrates, Julius Caesar 연결됨

**원인**: 본문에 비교/역사적 맥락으로 언급되면 관계 생성

**처리 방안**:
- ❌ 무조건 삭제: 부적절
  - "나폴레옹은 카이사르를 연구했다" → 유의미한 관계
  - "프랑스 혁명은 로마 공화정을 참고했다" → 유의미한 관계
- ✅ relationship_type으로 구분
  - `contemporary`: 동시대 관계 (시대 겹침)
  - `historical_reference`: 역사적 참조/영향 (시대 불일치)
  - `studied`, `influenced_by` 등 세분화

#### 2. 일반 단어 오탐
**처리 완료**: Commons, Other, London, William, Henry 등 삭제 (44,128개)

**향후 추가 검토 대상**:
- 2글자 이름 (Li, Wu 등)
- 일반 명사와 동음이의어
- 지명/인명 혼동

#### 3. 관계 강도(strength) ✅ 구현 완료
**상태**: 2026-01-19 적용 완료

**구현 내용** (`poc/scripts/update_person_relationship_strength.py`):
- Source Factor: `n * (1 + ln(n))^1.5` (공유 소스 수 기반)
- Location Factor: `shared_location_count * 2.0` (공유 장소 기반)
- Temporal Factor: 시대 중첩 점수
  - 20년 이상 겹침: +10
  - 10-20년 겹침: +7
  - 0-10년 겹침: +5
  - 50년 이내: +2
  - 100년 이내: 0
  - 100년 초과: -5 (페널티)

**결과 분포** (573,857개 관계):
- 강함 (>=10): 157,275개 (27.4%)
- 매우 강함 (>=30): 89,971개 (15.7%)
- 약함 (<5): 323,171개 (56.3%)
- 최대: 22,164 (Charles II ↔ Charles I)

---

## 개선 작업 계획

### Phase 1: 시대 기반 관계 분류 (미구현)

```sql
-- 동시대 관계 판별
-- Person A와 Event B가 시대적으로 겹치는지 확인
-- Person.death_year >= Event.date_start AND Person.birth_year <= Event.date_end

ALTER TABLE event_persons ADD COLUMN temporal_type VARCHAR(50);

UPDATE event_persons ep
SET temporal_type = CASE
    WHEN p.death_year IS NULL OR p.death_year >= e.date_start THEN 'contemporary'
    ELSE 'historical_reference'
END
FROM persons p, events e
WHERE ep.person_id = p.id AND ep.event_id = e.id;
```

### Phase 2: Strength 재계산 ✅ 완료

**적용 완료**: 2026-01-19
**스크립트**: `poc/scripts/update_person_relationship_strength.py`

```bash
# 실행 방법
python update_person_relationship_strength.py --dry-run  # 미리보기
python update_person_relationship_strength.py --execute  # 실제 적용
```

### Phase 3: 관계 유형 세분화 (미구현)

현재 relationship_type:
- `wikipedia_link`
- `content_mention`
- `co_mentioned`

추가 필요:
- `contemporary` / `historical_reference`
- `participated` / `witnessed` / `influenced`
- `born_in` / `died_in` / `resided_in` (person-location)

---

## 우선순위

| 작업 | 영향도 | 난이도 | 상태 |
|------|--------|--------|------|
| 시대 기반 분류 | 높음 | 중간 | 미구현 |
| Strength 재계산 | 중간 | 중간 | ✅ 완료 |
| 관계 유형 세분화 | 중간 | 높음 | 미구현 |
| 추가 오탐 정리 | 낮음 | 낮음 | ✅ 일부 완료 |

---

## 참고: 현재 관계 현황

| 테이블 | 레코드 수 |
|--------|-----------|
| person_relationships | 573,857 |
| event_persons | 1,125,688 |
| event_locations | 179,639 |
| person_locations | 609,513 |
| event_relationships | 193,201 |
| location_relationships | 18,636 |
| **총합** | **2,700,534** |

---

## 관련 스크립트

- `poc/scripts/create_relationships_from_links.py` - 하이퍼링크 기반
- `poc/scripts/create_relationships_from_mentions_v2.py` - 본문 언급 기반
- `poc/scripts/cleanup_false_positives.py` - 오탐 정리
- `poc/scripts/analyze_entity_tiers.py` - 티어 분석
- `poc/scripts/update_person_relationship_strength.py` - ✅ 강도 재계산
