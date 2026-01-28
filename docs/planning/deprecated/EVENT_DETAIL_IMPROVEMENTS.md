# Event Detail Panel 개선 계획

> 작성일: 2026-01-12
> 관련 파일: `frontend/src/components/detail/EventDetailPanel.tsx`

---

## 목표

**"이 시대 + 이 장소에서 무슨 일이 있었나?"**에 충실한 이벤트 상세 표시

---

## 현재 상태 분석

### WHO (참가자)
```
현재: 첫 번째 인물만 표시 + "+N others"
문제: 누가 참여했는지 한눈에 안 보임
```

### 출처 (Sources)
```
현재: 이름 + 신뢰도(별점)만 표시
문제: 원문 인용구가 없어서 실제 기록 확인 불가
```

### WHERE (장소)
```
현재: 장소명만 표시
문제: 이 장소에서 다른 무슨 일이 있었는지 연결 부족
```

---

## 개선 계획

### 1. 참가자(WHO) 섹션 개선

**Before:**
```
WHO
Alexander III of Macedon
+5 others
```

**After:**
```
WHO - Key Figures
┌─────────────────────────────────────────┐
│ 👑 Alexander III of Macedon            │
│    Role: Commander                      │
│ ⚔️ Darius III                          │
│    Role: Persian King (Opponent)        │
│ 🛡️ Parmenion                           │
│    Role: General                        │
│ ... Show all 6 figures                  │
└─────────────────────────────────────────┘
```

**구현 사항:**
- [x] 참가자 전체 목록 표시 (기본 1명, 펼침 가능)
- [x] 역할(role) 아이콘 + 텍스트 표시
- [x] 클릭 시 해당 인물의 활동 체인 시작

### 2. 출처(Sources) 섹션 개선

**Before:**
```
Historical Sources
Arrian, Anabasis ★★★★★
```

**After:**
```
Historical Sources
┌─────────────────────────────────────────┐
│ 📜 Arrian, Anabasis of Alexander       │
│    ★★★★★ (Primary Source)              │
│                                         │
│    "Alexander, seeing the danger,       │
│     charged directly at Darius..."      │
│                                         │
│    [View Full Text →]                   │
├─────────────────────────────────────────┤
│ 📚 Plutarch, Life of Alexander         │
│    ★★★★☆ (Secondary)                   │
│    "The battle was decided when..."     │
└─────────────────────────────────────────┘
```

**구현 사항:**
- [x] 원문 인용구(quote) 표시
- [x] Primary/Secondary 구분 표시
- [x] 외부 링크 (source.url)

### 3. 장소(WHERE) 섹션 개선

**Before:**
```
WHERE
Gaugamela
```

**After:**
```
WHERE - Location
┌─────────────────────────────────────────┐
│ 📍 Gaugamela                            │
│    Modern: Tell Gomel, Iraq             │
│    Coords: 36.56°N, 43.43°E             │
│                                         │
│ [🔍 Other events at this location (12)] │
│ [🗺️ Show on map]                        │
└─────────────────────────────────────────┘
```

**구현 사항:**
- [x] 현대 지명(modern_name) 표시
- [x] 좌표 표시
- [ ] "이 장소의 다른 사건" 버튼 → 클릭 시 목록 (추후)

---

## 장기 개선 계획

### 인물(Person) 시각화 강화

**목표:** 인물의 생애 경로를 지도에 시각화

```
알렉산더 대왕 (356-323 BCE)
────────────────────────────────────────
356 BCE  │ 📍 펠라 (출생)
         │   ↓
343 BCE  │ 📍 미에자 (아리스토텔레스 교육)
         │   ↓
336 BCE  │ 📍 펠라 (왕위 계승)
         │   ↓
334 BCE  │ 📍 그라니쿠스 (첫 전투)
         │   ↓
...      │   ...
323 BCE  │ 📍 바빌론 (사망)
```

**지도 표시:**
- 인물 마커: 간략화된 3D 모델 또는 특수 아이콘
- 이동 경로: 연도별 arc 애니메이션
- 주요 사건: 경로 위에 마커 표시

### 데이터 요구사항

```sql
-- persons 테이블 확장
ALTER TABLE persons ADD COLUMN life_events JSONB;
-- [{"year": -356, "location_id": 123, "event_type": "birth", "description": "..."}, ...]

-- 또는 별도 테이블
CREATE TABLE person_timeline (
    id SERIAL PRIMARY KEY,
    person_id INTEGER REFERENCES persons(id),
    year INTEGER,
    location_id INTEGER REFERENCES locations(id),
    event_type VARCHAR(50),  -- birth, death, battle, travel, appointment, ...
    title VARCHAR(255),
    description TEXT
);
```

---

## 구현 우선순위

| 순서 | 항목 | 난이도 | 영향도 |
|------|------|--------|--------|
| 1 | 참가자 목록 펼침 | 낮음 | 높음 |
| 2 | 원문 인용구 표시 | 낮음 | 높음 |
| 3 | 장소 상세 정보 | 낮음 | 중간 |
| 4 | "이 장소의 다른 사건" | 중간 | 높음 |
| 5 | 인물 생애 경로 (장기) | 높음 | 매우 높음 |

---

## 관련 타입 (types/index.ts)

```typescript
// 현재 PersonRole
interface PersonRole extends Person {
  role: string
}

// 현재 SourceReference
interface SourceReference extends Source {
  page_reference?: string
  quote?: string  // ← 이미 있음! 활용 필요
}
```

---

## 테스트 체크리스트

- [ ] 참가자 3명 이상인 이벤트에서 펼침 테스트
- [ ] quote가 있는 출처 표시 테스트
- [ ] 장소 클릭 → "다른 사건" 로딩 테스트
- [ ] 한국어/영어 번역 확인
