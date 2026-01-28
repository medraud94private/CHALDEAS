# CHALDEAS 일반 공개 체크리스트

**작성일**: 2026-01-28
**목표**: 일반 사용자에게 안정적이고 법적으로 안전한 서비스 제공

---

## 현재 상태 요약

| 영역 | 상태 | 비고 |
|------|------|------|
| 기본 기능 | ✅ 완료 | Globe, Timeline, Search, Detail View |
| 다언어 지원 | ✅ 완료 | UI: ko/ja/en, 데이터: 수집 중 |
| PWA | ✅ 완료 | manifest.json, service worker |
| 반응형 UI | ✅ 완료 | Mobile 지원 |
| SEO 기초 | ✅ 완료 | robots.txt, sitemap.xml, Structured Data, Meta tags |
| 법적 준수 | ✅ 완료 | 이용약관, 개인정보처리방침 페이지 추가됨 |
| 에러 추적 | ✅ 완료 | Sentry 설정 완료 (프론트엔드 + 백엔드) |
| 사용자 분석 | ✅ 완료 | Plausible/Umami 지원 analytics 모듈 추가 |
| 접근성 | ✅ 완료 | ARIA 레이블, 키보드 포커스 스타일, prefers-reduced-motion 지원 |

---

## 필수 (Must Have)

### 1. 법적 문서 📜

**우선순위: 높음**

| 문서 | 설명 | 예상 작업 |
|------|------|----------|
| 이용약관 (Terms of Service) | 서비스 이용 규칙 | 템플릿 기반 작성 |
| 개인정보처리방침 (Privacy Policy) | 데이터 수집/사용 고지 | 수집 데이터 정리 후 작성 |
| 쿠키 정책 | localStorage 사용 고지 | 간단한 배너 |
| 데이터 출처 고지 | Wikipedia CC BY-SA 명시 | 푸터 또는 About 페이지 |

**필요한 파일**:
```
frontend/src/pages/TermsPage.tsx
frontend/src/pages/PrivacyPage.tsx
frontend/src/components/common/CookieBanner.tsx
```

**구현 예시**:
```tsx
// 푸터에 추가
<footer>
  <a href="/terms">이용약관</a>
  <a href="/privacy">개인정보처리방침</a>
  <span>Data from Wikipedia (CC BY-SA 4.0)</span>
</footer>
```

---

### 2. 에러 추적 (Error Tracking) 🐛

**우선순위: 높음**

| 옵션 | 비용 | 장점 |
|------|------|------|
| Sentry | 무료 티어 5K events/월 | 업계 표준, 상세 스택트레이스 |
| LogRocket | 무료 티어 1K sessions/월 | 세션 리플레이 |
| GCP Error Reporting | Cloud Run 연동 | 이미 GCP 사용 중 |

**권장**: Sentry (프론트엔드 + 백엔드)

**설치**:
```bash
# Frontend
npm install @sentry/react

# Backend
pip install sentry-sdk[fastapi]
```

**설정 파일**:
```typescript
// frontend/src/main.tsx
import * as Sentry from "@sentry/react";
Sentry.init({
  dsn: "YOUR_SENTRY_DSN",
  environment: import.meta.env.MODE,
});
```

---

### 3. 사용자 분석 (Analytics) 📊

**우선순위: 중간**

| 옵션 | 비용 | GDPR 준수 |
|------|------|----------|
| Google Analytics 4 | 무료 | 동의 필요 |
| Plausible | $9/월 | 기본 준수 (쿠키 없음) |
| Umami (Self-hosted) | 무료 | 완전 준수 |

**권장**: Plausible 또는 Umami (쿠키 동의 없이 사용 가능)

**GA4 사용 시 필요**:
- 쿠키 동의 배너
- 동의 전 추적 차단 로직

---

### 4. 접근성 (Accessibility) ♿

**우선순위: 중간**

| 항목 | 현재 상태 | 필요 작업 |
|------|----------|----------|
| 키보드 네비게이션 | ⚠️ 부분 | Tab 순서, Focus 스타일 |
| 스크린 리더 | ❌ 미지원 | ARIA 레이블 추가 |
| 색상 대비 | ⚠️ 부분 | 일부 텍스트 대비 낮음 |
| 이미지 대체 텍스트 | ⚠️ 부분 | alt 속성 추가 |

**주요 수정 대상**:
```tsx
// Globe 마커에 aria-label 추가
<button aria-label={`${event.title}, ${formatYear(event.date_start)}`}>

// 모달에 role 추가
<div role="dialog" aria-modal="true" aria-labelledby="modal-title">

// 아이콘 버튼에 접근성 추가
<button aria-label="설정 열기" title="Settings">⚙</button>
```

---

## 권장 (Should Have)

### 5. SEO 개선 🔍

| 항목 | 현재 | 개선 |
|------|------|------|
| Sitemap | 단일 페이지 | 동적 생성 (이벤트/인물 URL) |
| Structured Data | 없음 | JSON-LD 추가 |
| Meta Tags | 기본만 | 동적 OG 이미지 |
| URL 구조 | SPA | SSR 또는 Prerender |

**동적 Sitemap 생성** (백엔드):
```python
@app.get("/sitemap.xml")
def generate_sitemap():
    # 주요 이벤트/인물 URL 포함
    pass
```

**Structured Data 예시**:
```html
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "WebApplication",
  "name": "CHALDEAS",
  "description": "Historical Knowledge System",
  "applicationCategory": "EducationalApplication"
}
</script>
```

---

### 6. 성능 모니터링 ⚡

| 도구 | 용도 |
|------|------|
| Lighthouse CI | 빌드 시 성능 체크 |
| Web Vitals | 실사용자 성능 측정 |
| GCP Cloud Monitoring | 서버 리소스 모니터링 |

**Web Vitals 설치**:
```bash
npm install web-vitals
```

```typescript
// src/reportWebVitals.ts
import { onCLS, onFID, onLCP } from 'web-vitals';

export function reportWebVitals() {
  onCLS(console.log);
  onFID(console.log);
  onLCP(console.log);
}
```

---

### 7. 사용자 피드백 채널 💬

| 옵션 | 설명 |
|------|------|
| GitHub Issues | 이미 있음, 링크 추가 필요 |
| 피드백 폼 | 간단한 인앱 폼 |
| Discord/Slack | 커뮤니티 구축 |

**현재 구현됨**: `ReportButton` (콘텐츠 오류 신고)

**추가 필요**:
```tsx
// 푸터 또는 About에 추가
<a href="https://github.com/anthropics/claude-code/issues">
  피드백 & 버그 신고
</a>
```

---

### 8. 소셜 공유 🌐

| 항목 | 현재 | 개선 |
|------|------|------|
| OG 이미지 | SVG 아이콘 | 스크린샷/프리뷰 이미지 |
| Twitter Card | summary | summary_large_image |
| 공유 버튼 | 없음 | 이벤트/인물 공유 버튼 |

**공유 버튼 컴포넌트**:
```tsx
function ShareButton({ title, url }: Props) {
  const share = () => {
    if (navigator.share) {
      navigator.share({ title, url });
    } else {
      navigator.clipboard.writeText(url);
    }
  };
  return <button onClick={share}>공유</button>;
}
```

---

## 선택 (Nice to Have)

### 9. 온보딩/튜토리얼 📚

| 옵션 | 설명 |
|------|------|
| 첫 방문 투어 | react-joyride 사용 |
| 도움말 페이지 | FAQ 및 사용법 |
| 툴팁 개선 | 주요 UI 요소에 설명 추가 |

---

### 10. 성능 최적화 🚀

| 항목 | 현재 | 목표 |
|------|------|------|
| LCP | ~3s (추정) | < 2.5s |
| Bundle Size | 1.6MB | < 1MB (코드 스플릿) |
| 이미지 최적화 | 없음 | WebP, lazy load |

---

### 11. 다크/라이트 모드 🌓

현재 다크 모드 고정. 라이트 모드 추가 고려.

---

## 우선순위별 구현 순서

### Phase 1: 법적 필수 (1-2일) ✅ 완료
1. [x] 이용약관 페이지 작성 - `frontend/src/pages/TermsPage.tsx`
2. [x] 개인정보처리방침 페이지 작성 - `frontend/src/pages/PrivacyPage.tsx`
3. [x] 푸터에 링크 추가 - App.tsx 푸터 영역
4. [x] Wikipedia CC BY-SA 출처 고지 - 푸터 및 SourceBadge 컴포넌트

### Phase 2: 안정성 (1-2일) ✅ 완료
5. [x] Sentry 설정 (프론트엔드) - `frontend/src/lib/sentry.tsx`
6. [x] Sentry 설정 (백엔드) - `backend/app/main.py`
7. [x] ErrorBoundary 컴포넌트 추가 - `main.tsx`에 Sentry ErrorBoundary 통합

### Phase 3: 분석 (0.5일) ✅ 완료
8. [x] Analytics 선택 및 설치 - Plausible/Umami 지원 `frontend/src/lib/analytics.ts`
9. [x] 주요 이벤트 추적 설정 - 검색, 엔티티 조회, 설정 변경 추적

### Phase 4: 접근성 (1-2일) ✅ 완료
10. [x] ARIA 레이블 추가 - App.tsx, SettingsPage.tsx, TermsPage.tsx, PrivacyPage.tsx
11. [x] 키보드 네비게이션 개선 - focus-visible 스타일, skip-link 지원
12. [x] 색상 대비/움직임 - prefers-reduced-motion 지원

### Phase 5: SEO (1일) ✅ 완료
13. [x] sitemap.xml 개선 - 다국어 hreflang 태그 추가
14. [x] Structured Data - JSON-LD (WebApplication, Organization, WebSite)
15. [x] robots.txt 개선 - 봇별 설정, crawl-delay
16. [x] Meta tags 개선 - keywords, canonical, 향상된 OG/Twitter 태그

---

## 예상 총 작업량

| Phase | 예상 시간 | 우선순위 |
|-------|----------|----------|
| 법적 필수 | 1-2일 | 🔴 필수 |
| 안정성 | 1-2일 | 🔴 필수 |
| 분석 | 0.5일 | 🟡 권장 |
| 접근성 | 1-2일 | 🟡 권장 |
| SEO | 1일 | 🟢 선택 |
| **합계** | **4-7일** | |

---

## 체크리스트 요약

### 공개 전 필수 ✅ 완료!
- [x] 이용약관 페이지
- [x] 개인정보처리방침 페이지
- [x] 데이터 출처 고지 (Wikipedia CC BY-SA)
- [x] 에러 추적 (Sentry)
- [x] 기본 접근성 (ARIA 레이블)
- [x] Analytics 설정 (Plausible/Umami 지원)

### 공개 후 개선 🔄
- [x] SEO 최적화 (robots.txt, sitemap, Structured Data) ✅
- [ ] 성능 모니터링 (Web Vitals)
- [ ] 온보딩 투어
- [ ] 소셜 공유 기능
- [ ] OG 이미지 (스크린샷 기반 이미지 생성)
