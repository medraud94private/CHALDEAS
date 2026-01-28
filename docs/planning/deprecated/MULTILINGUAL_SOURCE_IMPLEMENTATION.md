# 다언어 설명 + 출처 표시 + 설정 페이지 구현

**작성일**: 2026-01-28
**상태**: Phase 1-5 구현 완료, 테스트 및 배포 대기

---

## 완료된 작업

### Phase 1: DB 스키마 확장 ✅

| 파일 | 변경 내용 |
|------|----------|
| `backend/alembic/versions/004_multilingual_source_tracking.py` | 마이그레이션 생성 |
| `backend/app/models/person.py` | `name_ja`, `biography_ja`, `biography_source`, `biography_source_url` 추가 |
| `backend/app/models/event.py` | `title_ja`, `description_ja`, `description_source`, `description_source_url` 추가 |
| `backend/app/models/location.py` | `name_ja`, `description_ja`, `description_source`, `description_source_url` 추가 |

**스키마 변경 요약**:
```
persons:    +name_ja, +biography_ja, +biography_source, +biography_source_url
events:     +title_ja, +description_ja, +description_source, +description_source_url
locations:  +name_ja, +description_ja, +description_source, +description_source_url
```

---

### Phase 2: 다언어 Wikipedia 데이터 수집 스크립트 ✅

| 파일 | 설명 |
|------|------|
| `poc/scripts/fetch_wikipedia_multilingual.py` | Wikidata 기반 다언어 설명 수집 |

**기능**:
- Wikidata ID로 ko/ja/en Wikipedia sitelinks 조회
- 각 언어 Wikipedia에서 extract (설명) 가져오기
- DB 업데이트 + source 정보 저장
- `--mark-existing` 옵션: 기존 Wikipedia 데이터에 출처 마킹

**사용법**:
```bash
# 모든 엔티티 타입 100개씩 업데이트
python poc/scripts/fetch_wikipedia_multilingual.py --entity-type all --limit 100

# 특정 타입만
python poc/scripts/fetch_wikipedia_multilingual.py --entity-type persons --limit 500

# 기존 데이터에 출처 마킹
python poc/scripts/fetch_wikipedia_multilingual.py --mark-existing
```

---

### Phase 3: 설정 페이지 (Frontend) ✅

| 파일 | 설명 |
|------|------|
| `frontend/src/store/settingsStore.ts` | Zustand 설정 스토어 (localStorage 영속화) |
| `frontend/src/components/settings/SettingsPage.tsx` | 설정 페이지 UI |
| `frontend/src/components/settings/SettingsPage.css` | 스타일링 |
| `frontend/src/components/settings/index.ts` | 모듈 export |

**설정 항목**:
| 설정 | 타입 | 기본값 | 설명 |
|------|------|--------|------|
| `preferredLanguage` | `'auto' \| 'ko' \| 'ja' \| 'en'` | `'auto'` | 설명 표시 언어 |
| `hideEmptyDescriptions` | `boolean` | `false` | 설명 없는 항목 숨기기 |
| `globeStyle` | `'default' \| 'holo' \| 'night'` | `'default'` | 지구본 스타일 |
| `shebaApiKey` | `string \| null` | `null` | SHEBA API 키 |

**헬퍼 함수**:
- `getEffectiveLanguage()`: auto 설정 시 브라우저 언어 감지
- `getLocalizedText()`: 엔티티에서 선호 언어 텍스트 추출 (fallback 포함)
- `parseSourceInfo()`: 출처 문자열 파싱

---

### Phase 4: 출처 표시 (Frontend) ✅

| 파일 | 설명 |
|------|------|
| `frontend/src/components/common/SourceBadge.tsx` | 출처 배지 컴포넌트 |
| `frontend/src/components/common/SourceBadge.css` | 스타일링 |

**SourceBadge 표시 규칙**:
| 출처 | 표시 |
|------|------|
| `wikipedia_en/ko/ja` | Wikipedia 로고 + 언어 태그 + 링크 |
| `llm` | ✨ AI Generated |
| `manual` | 표시 없음 |
| `null/unknown` | 표시 없음 |

**Detail View 수정**:
- `PersonDetailView.tsx`: `getLocalizedText()` + `SourceBadge` 적용
- `EventDetailPanel.tsx`: `getLocalizedText()` + `SourceBadge` 적용
- `LocationDetailView.tsx`: `getLocalizedText()` + `SourceBadge` 적용

---

### Phase 5: 필터 확장 ✅

| 파일 | 변경 내용 |
|------|----------|
| `frontend/src/components/filters/FilterPanel.tsx` | "설명 없는 항목 숨기기" 체크박스 추가 |
| `frontend/src/components/filters/FilterPanel.css` | 체크박스 스타일 추가 |
| `frontend/src/App.tsx` | 설정 버튼 추가, 필터 로직 연동 |
| `frontend/src/styles/globals.css` | `.settings-toggle-btn` 스타일 추가 |

**App.tsx 변경**:
- Settings 버튼 (⚙) 추가 (우측 하단)
- `SettingsPage` 모달 렌더링
- 이벤트 필터에 `hideEmptyDescriptions` 적용
- Globe 스타일을 `settingsStore`와 연동

---

### i18n 번역 추가 ✅

| 파일 | 추가된 키 |
|------|----------|
| `frontend/src/i18n/locales/en.json` | `settings.*`, `filters.*` |
| `frontend/src/i18n/locales/ko.json` | `settings.*`, `filters.*` |
| `frontend/src/i18n/locales/ja.json` | `settings.*`, `filters.*` |

---

## 남은 작업

### 즉시 실행 필요

```bash
# 1. DB 마이그레이션 적용
cd backend
python -m alembic upgrade head

# 2. 기존 Wikipedia 데이터에 출처 마킹
python poc/scripts/fetch_wikipedia_multilingual.py --mark-existing

# 3. 다언어 데이터 수집 (시간 소요)
python poc/scripts/fetch_wikipedia_multilingual.py --entity-type persons --limit 500
python poc/scripts/fetch_wikipedia_multilingual.py --entity-type events --limit 500
python poc/scripts/fetch_wikipedia_multilingual.py --entity-type locations --limit 500
```

### 테스트 체크리스트

- [ ] 마이그레이션 성공 확인: `alembic current`
- [ ] 프론트엔드 빌드: `npm run build`
- [ ] 설정 페이지 열기/닫기
- [ ] 언어 변경 후 상세 페이지에서 설명 언어 변경 확인
- [ ] 설정 저장 후 새로고침 → 설정 유지 확인
- [ ] SourceBadge 표시 확인 (Wikipedia 출처 데이터)
- [ ] "설명 없는 항목 숨기기" 필터 동작 확인
- [ ] Globe 스타일 변경 시 설정 저장 확인

### 프로덕션 배포

```powershell
# 전체 배포 (Cloud Build)
gcloud builds submit --config=cloudbuild.yaml --project=chaldeas-archive

# DB 동기화 (로컬 → 클라우드)
.\scripts\sync-db.ps1 up
```

---

## 파일 변경 목록

### Backend (신규)
- `backend/alembic/versions/004_multilingual_source_tracking.py`
- `poc/scripts/fetch_wikipedia_multilingual.py`

### Backend (수정)
- `backend/app/models/person.py`
- `backend/app/models/event.py`
- `backend/app/models/location.py`

### Frontend (신규)
- `frontend/src/store/settingsStore.ts`
- `frontend/src/components/settings/SettingsPage.tsx`
- `frontend/src/components/settings/SettingsPage.css`
- `frontend/src/components/settings/index.ts`
- `frontend/src/components/common/SourceBadge.tsx`
- `frontend/src/components/common/SourceBadge.css`

### Frontend (수정)
- `frontend/src/App.tsx`
- `frontend/src/components/common/index.ts`
- `frontend/src/components/detail/PersonDetailView.tsx`
- `frontend/src/components/detail/EventDetailPanel.tsx`
- `frontend/src/components/detail/LocationDetailView.tsx`
- `frontend/src/components/filters/FilterPanel.tsx`
- `frontend/src/components/filters/FilterPanel.css`
- `frontend/src/styles/globals.css`
- `frontend/src/i18n/locales/en.json`
- `frontend/src/i18n/locales/ko.json`
- `frontend/src/i18n/locales/ja.json`

---

## 향후 확장 가능 항목

1. **자동 번역**: 설명이 없는 언어에 대해 LLM 번역 제공
2. **출처 신뢰도 표시**: Wikipedia vs LLM vs Manual 신뢰도 차별화
3. **언어별 설명 품질 지표**: 어떤 언어 설명이 더 완전한지 표시
4. **설정 동기화**: 로그인 사용자에 대해 서버에 설정 저장
