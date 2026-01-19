# Globe Marker 개선 계획

> 작성일: 2026-01-12
> 관련 파일: `frontend/src/components/globe/GlobeContainer.tsx`

---

## 문제점 요약

| # | 문제 | 심각도 | 상태 |
|---|------|--------|------|
| 1 | 마커 클릭 시 이벤트 매칭 실패 | 높음 | [x] 완료 |
| 2 | 전체 로딩 속도 저하 | 중간 | [x] 완료 |
| 3 | 확대 시 마커 겹침 (클릭 불가) | 높음 | [x] 완료 |
| 4 | 클러스터 클릭 시 팝업 목록 | 신규 | [x] 완료 |

---

## 문제 1: 마커 클릭 시 이벤트 매칭 실패

### 현상
```
Marker clicked but no matching event: 390430 Participation in the Finnish Diet
Marker clicked but no matching event: 357920 Journey of Catherine the Great...
```

### 원인 분석
```typescript
// globeMarkers API (라인 240-254)
const { data: globeMarkers } = useQuery({
  queryFn: () => api.get('/globe/markers', {
    params: {
      limit: 2000,  // 마커는 2000개 로드
      // ...
    },
  }),
})

// eventsData API (라인 257-269)
const { data: eventsData } = useQuery({
  queryFn: () => api.get('/events', {
    params: {
      limit: 1000,  // 이벤트는 1000개만 로드
      // ...
    },
  }),
})

// 마커 클릭 시 (라인 521-527)
const matchingEvent = eventsData?.find((e: Event) => e.id === singleMarker.id)
// → globeMarkers에는 있지만 eventsData에 없으면 매칭 실패
```

**핵심 문제**: `globeMarkers`(2000개)와 `eventsData`(1000개)의 limit 불일치

### 해결 방안

**Option A: 마커 클릭 시 개별 이벤트 fetch (권장)**
```typescript
onPointClick={(point) => {
  const marker = point as DisplayMarker
  if (isCluster(marker)) { /* 기존 로직 */ }

  const singleMarker = marker as GlobeMarker

  // 1차: 캐시에서 검색
  const cachedEvent = eventsData?.find((e: Event) => e.id === singleMarker.id)
  if (cachedEvent) {
    onEventClick(cachedEvent)
    return
  }

  // 2차: API에서 개별 fetch
  api.get(`/events/${singleMarker.id}`).then(res => {
    onEventClick(res.data)
  })
}}
```

**Option B: 두 API limit 통일**
- 둘 다 2000개로 맞추면 메모리 증가
- 둘 다 1000개로 맞추면 마커 누락

### 작업 항목
- [ ] 1-1. `onPointClick`에서 캐시 미스 시 개별 event fetch 로직 추가
- [ ] 1-2. 타입별 마커 디자인 구분 (event/person/location)
  - event: 기존 카테고리별 색상
  - person: 별 모양 또는 다른 아이콘/색상
  - location: 핀 모양 또는 다른 색상
- [ ] 1-3. 로딩 상태 표시 (선택적)
- [ ] 1-4. fetch 실패 시 에러 핸들링

---

## 문제 2: 전체 로딩 속도 저하

### 현상
- 마커 클릭 → Globe 회전/이동 후 상세 정보 로딩이 느림
- 전반적인 데이터 로딩 체감 속도가 느림

### 원인 분석 (전체 성능)
1. 대량의 마커 데이터 (2000개) 렌더링 부하
2. 연도 변경 시 매번 두 개의 API 호출 (markers + events)
3. React Query 캐시 전략 최적화 필요
4. 불필요한 리렌더링 발생 가능

### 해결 방안

**A. API 응답 캐싱 강화**
```typescript
const { data: globeMarkers } = useQuery({
  queryKey: ['globe-markers', debouncedYear],
  staleTime: 5 * 60 * 1000, // 5분간 fresh 유지
  gcTime: 30 * 60 * 1000,   // 30분간 캐시 보관
  // ...
})
```

**B. 데이터 Prefetch (연도 변경 예측)**
```typescript
// 타임라인 드래그 시 인접 연도 미리 로드
useEffect(() => {
  const nearYears = [currentYear - 50, currentYear + 50]
  nearYears.forEach(year => {
    queryClient.prefetchQuery({
      queryKey: ['globe-markers', year],
      // ...
    })
  })
}, [currentYear])
```

**C. 마커 hover 시 이벤트 상세 prefetch**
```typescript
onPointHover={(point) => {
  if (!point) return
  const marker = point as GlobeMarker
  queryClient.prefetchQuery({
    queryKey: ['event', marker.id],
    queryFn: () => api.get(`/events/${marker.id}`),
    staleTime: 60000,
  })
}}
```

**D. Globe 이동 시간 단축**
- 1000ms → 600ms로 줄여 체감 속도 개선

### 작업 항목
- [ ] 2-1. React Query staleTime/gcTime 최적화
- [ ] 2-2. `onPointHover`에 prefetch 로직 추가
- [ ] 2-3. Globe 이동 시간 단축 (1000ms → 600ms)
- [ ] 2-4. (선택) 인접 연도 데이터 미리 로드

---

## 문제 3: 확대 시 마커 겹침

### 현상
- 확대해도 마커 크기가 동일하여 밀집 지역에서 클릭 불가
- 클러스터링이 있지만 충분히 확대하면 해제됨 → 겹침 발생

### 원인 분석
```typescript
// 현재 pointRadius (라인 443-450)
pointRadius={(d) => {
  const marker = d as DisplayMarker
  if (isCluster(marker)) {
    return Math.min(3, 1 + Math.log2(marker.count) * 0.5)
  }
  return 0.8  // 항상 고정 크기!
}}
```

문제점:
1. 개별 마커 크기가 `0.8`로 고정
2. altitude(확대 수준)에 따른 크기 조절 없음
3. 확대 시 클러스터 해제 후 마커 겹침

### 해결 방안

**A. altitude 기반 동적 마커 크기**
```typescript
pointRadius={(d) => {
  const marker = d as DisplayMarker

  // altitude: 4.0(줌아웃) ~ 0.3(줌인)
  // 줌인할수록 마커 작게 (겹침 방지)
  const baseRadius = isCluster(marker)
    ? Math.min(3, 1 + Math.log2(marker.count) * 0.5)
    : 0.8

  // altitude 2.5 기준, 줌인 시 작아지고 줌아웃 시 커짐
  const scaleFactor = Math.max(0.3, Math.min(1.5, altitude / 2.5))
  return baseRadius * scaleFactor
}}
```

**B. 클러스터 해제 임계값 조정**
```typescript
// 현재: altitude < 0.8 이면 클러스터 해제
// 개선: 더 확대해야 클러스터 해제
const clusterRadius = useMemo(() => {
  if (!enableClustering) return 0
  if (altitude < 0.5) return 0  // 0.8 → 0.5로 변경 (더 확대해야 해제)
  return Math.min(800, Math.max(80, altitude * 180))  // 반경 축소
}, [altitude, enableClustering])
```

**C. 마커 간 최소 거리 보장 (Collision Detection)**
```typescript
// 밀집 지역에서 마커 위치 약간 분산
function spreadMarkers(markers: GlobeMarker[], minDistance: number): GlobeMarker[] {
  return markers.map((m, i) => {
    const nearby = markers.filter((other, j) =>
      j !== i && haversineDistance(m.lat, m.lng, other.lat, other.lng) < minDistance
    )
    if (nearby.length === 0) return m

    // 골든 앵글로 약간씩 분산
    const angle = (i * 137.5) * Math.PI / 180
    const offset = minDistance / 111 // km to degrees (approx)
    return {
      ...m,
      lat: m.lat + Math.sin(angle) * offset * 0.3,
      lng: m.lng + Math.cos(angle) * offset * 0.3,
    }
  })
}
```

### 작업 항목
- [ ] 3-1. `pointRadius`에 altitude 기반 스케일링 추가
- [ ] 3-2. 클러스터 해제 임계값 조정 (0.8 → 0.5)
- [ ] 3-3. 클러스터 반경 공식 개선
- [ ] 3-4. (선택) 밀집 마커 분산 로직 추가

---

## 구현 우선순위

1. **문제 1** (마커 매칭 실패) - 기본 기능 문제, 즉시 수정
2. **문제 3** (마커 겹침) - UX 영향 큼
3. **문제 2** (로딩 지연) - 체감 개선

---

## 예상 변경 파일

| 파일 | 변경 내용 |
|------|----------|
| `GlobeContainer.tsx` | onPointClick, onPointHover, pointRadius 수정 |
| `globeStore.ts` | (선택) prefetch 상태 관리 |

---

## 테스트 체크리스트

- [ ] 2000개 이상 마커 있는 연도에서 클릭 테스트
- [ ] 마커 밀집 지역 (유럽 1600년대) 확대 후 클릭 테스트
- [ ] 네트워크 느린 환경에서 로딩 시간 체크
- [ ] 클러스터 클릭 → 확대 → 개별 마커 클릭 플로우 테스트
