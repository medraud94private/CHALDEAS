# 로딩 속도 최적화 계획

> 작성일: 2026-01-12
> 상태: 진행 중

---

## 문제 분석

### 현재 병목 지점

| 구분 | 항목 | 소요시간 | 문제점 |
|------|------|----------|--------|
| 번들 | Three.js 초기화 | ~1MB | 코드 스플리팅 미적용 |
| 네트워크 | GeoJSON 항상 로드 | ~500KB | 조건부 로드 필요 |
| 캐시 | gcTime 미설정 | - | 불필요한 재요청 |
| 클러스터링 | O(n²) 알고리즘 | ~100ms | 1000개 마커 기준 |
| 디바운스 | 300ms | - | 체감 지연 |

### 측정 기준

```
초기 로드: 페이지 진입 → 지구본 인터랙션 가능
마커 클릭: 클릭 → 상세 패널 표시
연도 변경: 타임라인 조작 → 마커 갱신
```

---

## Phase 1: 즉시 적용 가능한 최적화

### 1.1 React Query 캐시 최적화

**파일**: `frontend/src/main.tsx`

**변경 전**:
```typescript
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000,
    },
  },
})
```

**변경 후**:
```typescript
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000,
      gcTime: 10 * 60 * 1000,          // 10분간 캐시 유지
      refetchOnWindowFocus: false,      // 포커스 시 재요청 방지
      retry: 1,                         // 재시도 1회로 제한
    },
  },
})
```

**체크리스트**:
- [x] gcTime 추가 (10분)
- [x] refetchOnWindowFocus: false 설정
- [x] retry 횟수 제한

### 1.2 GeoJSON 조건부 로드

**파일**: `frontend/src/components/globe/GlobeContainer.tsx`

**문제**: Holo 스타일에서만 사용하는 GeoJSON을 항상 로드

**해결**: `globeStyle === 'holo'`일 때만 fetch

**체크리스트**:
- [x] GeoJSON 로드 조건 추가
- [x] enabled 옵션으로 조건부 쿼리

### 1.3 디바운스 시간 단축

**파일**: `frontend/src/hooks/useDebounce.ts`

**변경**: 300ms → 150ms

**체크리스트**:
- [x] 기본 디바운스 값 변경
- [x] 타임라인 연도 변경 반응 개선

---

## Phase 2: 구조적 최적화

### 2.1 쿼리 통합

**현재 상태**: 3개 API 병렬 호출
```
/api/v1/events?limit=1000
/api/v1/persons?limit=500
/api/v1/locations?limit=500
```

**개선안**: 단일 엔드포인트
```
/api/v1/globe/markers?year_start=-500&year_end=500&limit=2000
```

**백엔드 변경 필요**:
```python
@router.get("/globe/markers")
async def get_globe_markers(
    year_start: int = Query(None),
    year_end: int = Query(None),
    limit: int = Query(2000),
    include_types: str = Query("event,person,location")
):
    # 단일 쿼리로 모든 마커 타입 반환
    pass
```

**체크리스트**:
- [x] 백엔드 통합 엔드포인트 생성
- [x] 프론트엔드 쿼리 통합
- [x] 기존 개별 쿼리와 호환성 유지

### 2.2 클러스터링 알고리즘 최적화

**변경 전**: O(n²) - 모든 마커 쌍 비교
```typescript
markers.forEach((marker, i) => {
  markers.slice(i + 1).forEach((other) => {
    if (haversineDistance(marker, other) < threshold) {
      // 클러스터에 추가
    }
  })
})
```

**변경 후**: O(n) - 그리드 기반 공간 해싱
```typescript
// 그리드 셀 크기 계산 (km → 도)
const cellSizeDeg = clusterRadius / 111

// O(n) - 각 마커를 그리드 셀에 할당
const grid = new Map<string, GlobeMarker[]>()
for (const marker of markers) {
  const cellLat = Math.floor(marker.lat / cellSizeDeg)
  const cellLng = Math.floor(marker.lng / cellSizeDeg)
  const key = `${cellLat},${cellLng}`
  // 셀에 마커 추가
}

// O(n) - 그리드 셀을 클러스터로 변환
for (const [key, cellMarkers] of grid) {
  if (cellMarkers.length === 1) {
    // 단일 마커
  } else {
    // 클러스터 생성
  }
}
```

**체크리스트**:
- [x] 그리드 기반 알고리즘 구현 (추가 라이브러리 없음)
- [x] 기존 클러스터링 로직 교체
- [x] 줌 레벨에 따른 동적 클러스터링 유지

---

## Phase 3: 고급 최적화 (향후)

### 3.1 코드 스플리팅

**대상**: Three.js, react-globe.gl

```typescript
// vite.config.ts
build: {
  rollupOptions: {
    output: {
      manualChunks: {
        'three': ['three'],
        'globe': ['react-globe.gl'],
      }
    }
  }
}
```

### 3.2 웹 워커 활용

**대상**: 클러스터링 연산

```typescript
// clustering.worker.ts
self.onmessage = (e) => {
  const { markers, zoom, bbox } = e.data
  const clusters = computeClusters(markers, zoom, bbox)
  self.postMessage(clusters)
}
```

### 3.3 가상화 (Virtualization)

**대상**: 클러스터 팝업 목록

```typescript
import { useVirtualizer } from '@tanstack/react-virtual'
```

---

## 성능 목표

| 지표 | 현재 | 목표 | 달성 |
|------|------|------|------|
| 초기 로드 (LCP) | ~3s | < 2s | - |
| 마커 클릭 반응 | ~500ms | < 200ms | - |
| 연도 변경 반응 | ~300ms | < 150ms | - |
| 메모리 사용량 | ~150MB | < 100MB | - |

---

## 진행 상황

### 2026-01-12

- [x] Phase 1.1: gcTime, refetchOnWindowFocus 설정
- [x] Phase 1.2: GeoJSON 조건부 로드
- [x] Phase 1.3: 디바운스 150ms로 단축
- [x] Phase 2.1: 통합 API 엔드포인트 생성
- [x] Phase 2.2: Supercluster 기반 클러스터링

---

## 관련 문서

- `docs/planning/GLOBE_MARKER_IMPROVEMENTS.md` - 마커 개선 계획
- `docs/planning/GLOBE_VISUALIZATION_V2.md` - V2 시각화 계획
