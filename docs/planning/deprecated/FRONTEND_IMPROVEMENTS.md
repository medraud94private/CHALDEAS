# Frontend Improvements - SEO, PWA, Branding

## 현재 상태 (2026-01)

### 있는 것들 ✅

| 항목 | 상태 | 위치 |
|------|------|------|
| robots.txt | ✅ 있음 | `frontend/public/robots.txt` |
| favicon | ✅ 있음 (SVG) | `frontend/public/icons/icon.svg` |
| PWA 메타 태그 | ✅ 있음 | `frontend/index.html` |
| SEO 기본 (title, desc) | ✅ 있음 | `frontend/index.html` |
| Open Graph 태그 | ✅ 추가됨 (2026-01-23) | `frontend/index.html` |
| manifest.json | ✅ 추가됨 (2026-01-23) | `frontend/public/manifest.json` |
| sitemap.xml | ✅ 추가됨 (2026-01-23) | `frontend/public/sitemap.xml` |

### 수정 완료 ✅

| 항목 | 이전 | 수정됨 |
|------|------|--------|
| robots.txt sitemap | `chaldeas.app` | `www.chaldeas.site` ✅ |

---

## 개선 가능한 항목

### 1. sitemap.xml 생성 (SEO)

동적 sitemap 또는 정적 sitemap 필요:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://www.chaldeas.site/</loc></url>
  <url><loc>https://www.chaldeas.site/persons</loc></url>
  <url><loc>https://www.chaldeas.site/events</loc></url>
  <url><loc>https://www.chaldeas.site/locations</loc></url>
</urlset>
```

### 2. manifest.json (PWA)

홈 화면 추가, 앱처럼 사용 가능:
```json
{
  "name": "CHALDEAS - Historical Knowledge System",
  "short_name": "CHALDEAS",
  "start_url": "/",
  "display": "standalone",
  "background_color": "#050810",
  "theme_color": "#050810",
  "icons": [
    { "src": "/icons/icon-192.png", "sizes": "192x192", "type": "image/png" },
    { "src": "/icons/icon-512.png", "sizes": "512x512", "type": "image/png" }
  ]
}
```

### 3. 다양한 크기 favicon

| 크기 | 용도 |
|------|------|
| 16x16 | 브라우저 탭 |
| 32x32 | 브라우저 탭 (레티나) |
| 180x180 | Apple Touch Icon |
| 192x192 | Android Chrome |
| 512x512 | PWA 스플래시 |

### 4. Open Graph 메타 태그 (소셜 공유)

```html
<meta property="og:title" content="CHALDEAS - Historical Knowledge System" />
<meta property="og:description" content="Explore world history across time and space" />
<meta property="og:image" content="https://www.chaldeas.site/og-image.png" />
<meta property="og:url" content="https://www.chaldeas.site" />
<meta property="og:type" content="website" />
<meta name="twitter:card" content="summary_large_image" />
```

### 5. 구조화된 데이터 (JSON-LD)

Google 검색 결과 개선:
```html
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "WebApplication",
  "name": "CHALDEAS",
  "description": "Historical knowledge exploration system",
  "url": "https://www.chaldeas.site",
  "applicationCategory": "EducationalApplication"
}
</script>
```

### 6. 기타

- [ ] 404 페이지 커스텀
- [ ] Loading skeleton 개선
- [ ] 오프라인 지원 (Service Worker)
- [ ] 성능 최적화 (이미지 lazy loading, code splitting)

---

## 우선순위

| 순위 | 항목 | 난이도 | 효과 |
|------|------|--------|------|
| 1 | robots.txt URL 수정 | 쉬움 | 중 |
| 2 | Open Graph 태그 추가 | 쉬움 | 중 (소셜 공유) |
| 3 | manifest.json | 쉬움 | 중 (PWA) |
| 4 | sitemap.xml | 보통 | 중 (SEO) |
| 5 | 다양한 favicon | 보통 | 낮음 |
| 6 | JSON-LD | 보통 | 낮음 |

---

## 참고

- 현재 도메인: `https://www.chaldeas.site`
- Frontend: Cloud Run (us-central1)
- Backend: Cloud Run (asia-northeast3)
