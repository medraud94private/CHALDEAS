# Timeline Performance Optimization

**Date**: 2026-01-12
**Status**: Phase 1 Complete
**Priority**: High

---

## 1. Problem

Timeline 시대 이동 시 느림 현상 발생

### 증상
- 타임라인 드래그 시 렉 발생
- 시대 점프 버튼 클릭 후 UI 반응 지연
- Globe 마커 업데이트 느림

### 원인 분석

**Root Cause**: `currentYear` 변경 시마다 API 호출 발생

```typescript
// App.tsx:106-114
const { data: allEventsData } = useQuery({
  queryKey: ['sidebar-events', currentYear, showAllEras],  // ← currentYear 변경마다 새 쿼리!
  queryFn: () => api.get('/events', {
    params: { year_start: currentYear - 50, year_end: currentYear + 50, limit: 1000 }
  }),
})
```

타임라인 드래그 시:
- 매 프레임마다 `currentYear` 업데이트
- 매번 새로운 API 호출 트리거
- 응답 대기 중 UI 블로킹

---

## 2. Solution Options

### Option A: Debounce (권장) ✅ 적용됨
```typescript
// currentYear 변경을 debounce (150ms 대기 후 호출)
const debouncedYear = useDebounce(currentYear, 150)

const { data } = useQuery({
  queryKey: ['sidebar-events', debouncedYear, showAllEras],
  // ...
})
```

**장점**: 구현 간단, 효과적
**단점**: 150ms 지연 발생 (체감 거의 없음)

### Option B: Range-based Caching
```typescript
// 50년 단위로 range 계산 → 같은 range면 캐시 사용
const yearRange = Math.floor(currentYear / 50) * 50

const { data } = useQuery({
  queryKey: ['sidebar-events', yearRange, showAllEras],
  // year_start: yearRange - 100, year_end: yearRange + 100
})
```

**장점**: 캐시 활용 극대화
**단점**: 경계에서 점프 느낌

### Option C: Hybrid (Debounce + Range)
- 드래그 중: debounce로 API 호출 최소화
- 드래그 완료: 즉시 정확한 range 로드

---

## 3. Implementation Checklist

### Phase 1: Immediate Fix (Debounce)
- [ ] `useDebounce` hook 추가
- [ ] `App.tsx`의 events query에 debounce 적용
- [ ] Globe events query에도 동일 적용
- [ ] 테스트: 드래그 시 API 호출 빈도 확인

### Phase 2: Globe Optimization
- [ ] Globe 마커 업데이트 최적화
- [ ] 마커 렌더링 throttle 적용
- [ ] 불필요한 리렌더링 방지 (React.memo)

### Phase 3: Prefetching
- [ ] 현재 연도 ±100년 데이터 미리 로드
- [ ] Background prefetch 구현
- [ ] 캐시 전략 최적화

---

## 4. Files to Modify

| File | Change |
|------|--------|
| `frontend/src/hooks/useDebounce.ts` | 새로 생성 |
| `frontend/src/App.tsx` | events query에 debounce 적용 |
| `frontend/src/components/globe/GlobeContainer.tsx` | 마커 업데이트 최적화 |

---

## 5. Progress Log

| Date | Checkpoint | Status |
|------|------------|--------|
| 2026-01-12 | 문제 분석 완료 | ✓ |
| 2026-01-12 | Phase 1: useDebounce hook 추가 | ✓ |
| 2026-01-12 | Phase 1: App.tsx sidebar events debounce | ✓ |
| 2026-01-12 | Phase 1: GlobeContainer markers/events debounce | ✓ |
| 2026-01-12 | **디바운스 시간 통일 (300ms → 150ms)** | ✓ |
| | Phase 2 구현 (필요시) | - |
| | Phase 3 구현 (필요시) | - |

> **Note**: Phase 2, 3는 현재 성능이 충분하므로 보류. 추가 렉 발생 시 진행.
