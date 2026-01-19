# Phase 8: UI/UX 개선 - FGO 스타일 역사 탐험

**작성일**: 2026-01-11
**최종 수정**: 2026-01-11
**상태**: ✅ 구현 완료

---

## 1. 개요

### 1.1 목표

프로젝트 핵심 철학을 UI에 반영하고, FGO(Fate/Grand Order) 스타일의 몰입감 있는 경험 제공.

**핵심 철학**:
> "모든 역사는 **누가(Person)** **어디서(Location)** **언제(Time)** **무엇을(Event)** 했는가로 결정된다."

### 1.2 배경

Phase 7에서 Historical Chain(113,830개 연결)이 완성되었으나:
- ChainPanel이 별도 모달로 분리되어 기존 UI와 단절
- ID 기반 검색으로 사용자 비친화적
- 4대 요소(WHO/WHERE/WHEN/WHAT)가 UI에 명시적으로 표현되지 않음

### 1.3 개선 영역

| 영역 | Before | After |
|-----|--------|-------|
| 이벤트 카드 | 제목+연도만 | WHO/WHERE 메타데이터 표시 |
| 상세 패널 | 텍스트 나열 | 4대 요소 그리드 + 탭 구조 |
| Chain 패널 | ID 검색 | 탭 기반 통계/목록 탐색 |
| 사이드바 | 이벤트 목록만 | Chain 통계 섹션 추가 |
| 애니메이션 | 없음 | FGO 스타일 전환 효과 |

---

## 2. 설계 원칙

### 2.1 4대 요소 우선 표시

모든 UI에서 사용자가 즉시 파악할 수 있어야 하는 정보:

```
┌─────────────────────────────────┐
│ WHEN: 언제 발생했는가?          │  → 시간적 맥락
│ WHERE: 어디서 발생했는가?        │  → 공간적 맥락
│ WHO: 누가 관련되었는가?          │  → 인물 맥락
│ WHAT: 무슨 일이 발생했는가?      │  → 사건 유형
└─────────────────────────────────┘
```

### 2.2 FGO 디자인 원칙

| 원칙 | 적용 |
|-----|------|
| **다크 테마** | `#0a0f1e` ~ `#1a1f2e` 배경 |
| **네온 악센트** | Cyan `#00d4ff`, Gold `#fbbf24` |
| **홀로그램 효과** | 그라데이션 보더, 글로우 |
| **HUD 스타일** | 정보 밀도 높은 카드 레이아웃 |
| **전환 애니메이션** | fadeIn, slideIn, pulse |

### 2.3 Historical Chain 통합

```
기존 (분리):
┌──────────┐     ┌──────────┐
│ Event    │     │ Chain    │
│ Detail   │  ❌  │ Modal    │
└──────────┘     └──────────┘

개선 (통합):
┌─────────────────────────────┐
│ Event Detail                │
│ ┌─────────┬───────────────┐ │
│ │Overview │ Connections   │ │ ← 탭으로 연결
│ └─────────┴───────────────┘ │
│ [4대 요소] [연결된 이벤트]  │
└─────────────────────────────┘
         ↓
    클릭 시 해당 이벤트로 이동
```

---

## 3. 구현 상세

### 3.1 이벤트 카드 개선

**Before**:
```jsx
<div className="event-item">
  <span>BC 490</span>
  <span>Battle of Marathon</span>
</div>
```

**After**:
```jsx
<div className="event-card">
  <div className="event-card-header">
    <div className="event-card-year">
      <span className="year-era">BC</span>
      <span className="year-number">490</span>
    </div>
    <span className="event-card-category battle">BATTLE</span>
  </div>
  <div className="event-card-title">Battle of Marathon</div>
  <div className="event-card-meta">
    <span className="event-card-who">👤 Miltiades +2</span>
    <span className="event-card-where">📍 Marathon</span>
  </div>
</div>
```

**디자인 결정 이유**:
- 목록에서 바로 WHO/WHERE 확인 가능
- 카테고리 색상으로 사건 유형 구분
- +N 표시로 추가 인물 존재 암시

### 3.2 4대 요소 그리드

```
┌────────┬────────┐
│ WHEN   │ WHERE  │
│ 490BCE │Marathon│
├────────┼────────┤
│ WHO    │ WHAT   │
│Miltiad │ Battle │
└────────┴────────┘
```

**색상 체계**:
| 요소 | 색상 | Hex | 의미 |
|-----|------|-----|------|
| WHEN | Cyan | `#00d4ff` | 시간 = 흐름 |
| WHERE | Emerald | `#34d399` | 장소 = 자연 |
| WHO | Gold | `#fbbf24` | 인물 = 가치 |
| WHAT | Magenta | `#f472b6` | 사건 = 에너지 |

### 3.3 상세 패널 탭 구조

```
[Overview] [Connections]
     ↓           ↓
 4대 요소    연결된 이벤트
 설명       (유형별 그룹)
 시대 맥락   클릭→이동
```

**Connections 탭 설계**:
```jsx
// 유형별 그룹화
{
  causes: [...],      // 이 사건의 원인들
  leads_to: [...],    // 이 사건의 결과들
  follows: [...],     // 시간적 연결
  related: [...],     // 관련 사건들
}
```

### 3.4 ChainPanel 재설계

**Before (문제점)**:
- ID 직접 입력 필요 → 사용자가 ID를 알 수 없음
- Tailwind CSS 사용 → 프로젝트 스타일과 불일치

**After (개선)**:
```
┌─────────────────────────────────┐
│ [Overview][Strongest][Recent]   │  ← 탭 탐색
├─────────────────────────────────┤
│ Overview:                       │
│   113,830 Total Connections     │
│   Layer별 바 차트               │
│   Type별 그리드                 │
│   검증 상태                     │
├─────────────────────────────────┤
│ Strongest:                      │
│   strength ≥ 10 연결 카드 목록  │
├─────────────────────────────────┤
│ Recent:                         │
│   샘플 연결 카드 목록           │
└─────────────────────────────────┘
```

**연결 카드 설계**:
```
┌─────────────────────────────────┐
│ [CAUSES] [causal]      ⚡ 12.5  │
├─────────────────────────────────┤
│ Event A Title      →  Event B  │
│ 490 BCE               480 BCE  │
└─────────────────────────────────┘
```

### 3.5 사이드바 Chain 통계

```
┌─────────────────────────────────┐
│ ⧉ Historical Chain             │
│ ┌───────┬───────┐              │
│ │113,830│36,905 │              │
│ │Connect│Person │              │
│ ├───────┼───────┤              │
│ │20,442 │56,483 │              │
│ │Location│Causal│              │
│ └───────┴───────┘              │
│      Click to explore →        │
└─────────────────────────────────┘
```

**배치 이유**:
- 좌측 사이드바 하단 = 이벤트 스크롤 후 자연스럽게 노출
- 클릭 시 상세 ChainPanel 모달 열림
- 항상 보이는 위치로 Historical Chain 인지도 향상

---

## 4. 애니메이션 시스템

### 4.1 정의된 애니메이션

```css
/* 아래에서 위로 페이드인 */
@keyframes fadeInUp {
  from { opacity: 0; transform: translateY(20px); }
  to { opacity: 1; transform: translateY(0); }
}

/* 오른쪽에서 슬라이드인 */
@keyframes slideInRight {
  from { opacity: 0; transform: translateX(30px); }
  to { opacity: 1; transform: translateX(0); }
}

/* 발광 펄스 */
@keyframes glowPulse {
  0%, 100% { box-shadow: 0 0 10px rgba(0, 212, 255, 0.3); }
  50% { box-shadow: 0 0 20px rgba(0, 212, 255, 0.5); }
}

/* 바 차트 성장 */
@keyframes barGrow {
  from { width: 0; }
}

/* 카드 슬라이드인 */
@keyframes slideInCard {
  from { opacity: 0; transform: translateX(-20px); }
  to { opacity: 1; transform: translateX(0); }
}
```

### 4.2 적용 패턴

| 대상 | 애니메이션 | 타이밍 |
|-----|----------|-------|
| 이벤트 카드 | fadeInUp | `nth-child * 0.05s` 시차 |
| 4대 요소 카드 | fadeInUp | `nth-child * 0.1s` 시차 |
| 상세 패널 | slideInRight | 0.3s |
| Chain 아이콘 | glowPulse | 2s infinite |
| 통계 바 | barGrow | 0.8s |
| 연결 카드 | slideInCard | `index * 0.05s` 시차 |

### 4.3 호버 효과

```css
/* 이벤트 카드 호버 */
.event-card:hover {
  transform: translateX(-4px);
  border-color: rgba(0, 212, 255, 0.4);
  box-shadow: 0 4px 20px rgba(0, 212, 255, 0.15);
}

/* 선택된 카드 */
.event-card.selected {
  border-left: 3px solid #00d4ff;
  background: linear-gradient(90deg,
    rgba(0, 212, 255, 0.1) 0%,
    transparent 100%);
}
```

---

## 5. 파일 구조

### 5.1 수정된 파일

| 파일 | 변경 내용 | LOC |
|------|----------|-----|
| `frontend/src/App.tsx` | 이벤트 카드, Chain 통계 | +120 |
| `frontend/src/components/detail/EventDetailPanel.tsx` | 4대 요소, 탭, 연결 | +180 |
| `frontend/src/components/chain/ChainPanel.tsx` | 완전 재작성 | ~290 |
| `frontend/src/styles/globals.css` | 애니메이션, 카드 스타일 | +250 |

### 5.2 신규 파일

| 파일 | 내용 | LOC |
|------|------|-----|
| `frontend/src/components/chain/ChainPanel.css` | Chain 전용 스타일 | 466 |
| `docs/logs/UI_IMPROVEMENT_LOG.md` | UI 변경 로그 | 245 |

---

## 6. 색상 체계 정리

### 6.1 레이어 색상

| Layer | Color | Hex | 사용처 |
|-------|-------|-----|--------|
| Person | Gold | `#fbbf24` | 인물 체인 |
| Location | Emerald | `#34d399` | 장소 체인 |
| Causal | Pink | `#f472b6` | 인과 체인 |
| Thematic | Purple | `#a78bfa` | 주제 체인 |

### 6.2 연결 유형 색상

| Type | Color | Hex | 의미 |
|------|-------|-----|------|
| causes | Red | `#ef4444` | 원인 |
| leads_to | Orange | `#f97316` | 결과 |
| follows | Blue | `#3b82f6` | 시간순 |
| part_of | Purple | `#a855f7` | 부분 |
| concurrent | Green | `#22c55e` | 동시 |
| related | Gray | `#6b7280` | 관련 |

### 6.3 카테고리 색상

| Category | Color | 의미 |
|----------|-------|------|
| battle | Magenta | 전투 |
| war | `#ff6b6b` | 전쟁 |
| politics | `#4a9eff` | 정치 |
| religion | Orange | 종교 |
| philosophy | `#9966ff` | 철학 |
| science | Cyan | 과학 |
| culture | Pink | 문화 |
| civilization | Gold | 문명 |
| discovery | `#50fa7b` | 발견 |

---

## 7. 기술적 결정

### 7.1 React Query 도입 (ChainPanel)

**Before**: 직접 axios 호출
```jsx
useEffect(() => {
  axios.get('/api/v1/chains/stats').then(...)
}, [])
```

**After**: React Query
```jsx
const { data: stats } = useQuery({
  queryKey: ['chain-stats'],
  queryFn: () => api.get('/chains/stats'),
  select: (res) => res.data,
  staleTime: 60000,
});
```

**이유**:
- 캐싱으로 불필요한 API 호출 감소
- 로딩/에러 상태 자동 관리
- 탭 전환 시 데이터 유지

### 7.2 CSS 분리 (ChainPanel.css)

**이유**:
- globals.css 비대화 방지
- 컴포넌트별 스타일 관리
- 애니메이션 복잡도 분리

### 7.3 탭 기반 탐색

**이유**:
- ID 입력 불필요 → 진입 장벽 낮춤
- 통계 → 상세 → 탐색 자연스러운 흐름
- 데이터 규모(113,830개) 고려한 분류 제공

---

## 8. 성능 고려

### 8.1 애니메이션 최적화

```css
/* GPU 가속 활용 */
.event-card {
  will-change: transform;
  transform: translateZ(0);
}
```

### 8.2 데이터 페칭

- `staleTime: 60000` - 1분간 캐시 유지
- 탭별 조건부 페칭 (`enabled: viewMode === 'strongest'`)
- 목록 제한 (`limit: 20`)

### 8.3 렌더링 최적화

- 시차 애니메이션은 CSS만 사용 (JS 타이머 불필요)
- 연결 목록 최대 20개로 제한

---

## 9. 다음 단계 예측

### Phase 8.5: UI 고도화 (즉시 가능)

| 항목 | 설명 | 우선순위 |
|-----|------|---------|
| 필터 UI 개선 | 고급 필터 접기/펼치기 | 중 |
| 반응형 디자인 | 모바일/태블릿 대응 | 중 |
| 키보드 네비게이션 | 방향키로 이벤트 탐색 | 낮 |
| 다크/라이트 모드 토글 | 사용자 선호도 반영 | 낮 |

### Phase 9: Globe 연결선 시각화 (중기)

```
┌─────────────────────────────────┐
│           🌍 Globe              │
│                                 │
│     A ────────→ B               │
│      \         /                │
│       \       /                 │
│        ↘     ↙                  │
│          C                      │
│                                 │
│ 이벤트 선택 시 연결선 표시       │
└─────────────────────────────────┘
```

**구현 방안**:
- three.js 커브 (QuadraticBezierCurve3)
- 레이어별 색상 차별화
- 강도에 따른 선 두께

### Phase 10: Person/Location 상세 뷰 (중기)

```
Person Detail:
┌─────────────────────────────────┐
│ 👤 소크라테스 (BC 470-399)      │
├─────────────────────────────────┤
│ Timeline:                       │
│ ├─ BC 470: 출생 (아테네)        │
│ ├─ BC 432: 펠로폰네소스 참전    │
│ ├─ BC 399: 재판 및 처형         │
│                                 │
│ Connections:                    │
│ ├─ 플라톤 (제자)                │
│ ├─ 아리스토파네스 (비판)        │
└─────────────────────────────────┘
```

### Phase 11: Curation UI (장기)

```
Admin Panel:
┌─────────────────────────────────┐
│ Pending Connections (41,124)    │
├─────────────────────────────────┤
│ [Event A] → [Event B]           │
│ Strength: 3.2 | Layer: causal   │
│                                 │
│ [✓ Approve] [✗ Reject] [Edit]   │
│                                 │
│ Note: ___________________       │
└─────────────────────────────────┘
```

---

## 10. 비용 분석

| 항목 | 비용 |
|-----|------|
| Phase 8 UI 개선 | $0 (프론트엔드 작업) |
| Phase 9 Globe 시각화 | $0 (프론트엔드 작업) |
| Phase 10 상세 뷰 | $0 (기존 API 활용) |
| Phase 11 Curation | $0~5 (LLM 추천 시) |

---

## 11. 결론

Phase 8에서 달성한 핵심 성과:

1. **철학의 시각화**: 4대 요소(WHO/WHERE/WHEN/WHAT)가 UI 전반에 명시적으로 표현됨
2. **Chain 접근성**: ID 검색 → 탭 탐색으로 진입 장벽 제거
3. **UI 통합**: 분리된 모달 → 탭/섹션으로 자연스러운 흐름
4. **FGO 스타일**: 다크 테마, 네온 악센트, 애니메이션으로 몰입감 향상

다음 단계로 Globe 연결선 시각화와 Person/Location 상세 뷰를 구현하면, 역사 탐험 경험이 크게 향상될 것으로 예상됨.

---

## 변경 이력

| 날짜 | 내용 |
|-----|------|
| 2026-01-11 | 초기 작성, 구현 완료 |
