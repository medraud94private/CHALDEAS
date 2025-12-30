# CHALDEAS

> **"전체를 보는 구조, 질문에 맞게 픽업해서 설명해주는 AI"**

Fate/Grand Order의 칼데아 시스템에서 영감받은 **역사/철학/과학사/신화/인물사 통합 시공간 탐색 플랫폼**

---

## 프로젝트 비전

```
┌─────────────────────────────────────────────────────────────────────┐
│                         CHALDEAS 시스템                              │
│                                                                     │
│   ┌─────────────────────────────────────────────────────────────┐  │
│   │                    CHALDEAS (전체 세계)                       │  │
│   │                                                             │  │
│   │    역사 ─── 철학 ─── 과학 ─── 신화 ─── 인물                    │  │
│   │      │       │       │       │       │                      │  │
│   │      └───────┴───────┴───────┴───────┘                      │  │
│   │              │                                              │  │
│   │         모든 것이 연결된 시공간 그래프                          │  │
│   └─────────────────────────────────────────────────────────────┘  │
│                              │                                      │
│                              ▼                                      │
│   ┌─────────────────────────────────────────────────────────────┐  │
│   │                    SHEBA (관측/픽업)                          │  │
│   │                                                             │  │
│   │    User: "소크라테스가 살던 시대의 아테네는 어땠나요?"           │  │
│   │                         │                                   │  │
│   │                         ▼                                   │  │
│   │    [시간: -470~-399] + [장소: 아테네] + [인물: 소크라테스]      │  │
│   │                         │                                   │  │
│   │                         ▼                                   │  │
│   │    관련 이벤트 + 동시대 인물 + 문화적 맥락 픽업                  │  │
│   └─────────────────────────────────────────────────────────────┘  │
│                              │                                      │
│                              ▼                                      │
│   ┌─────────────────────────────────────────────────────────────┐  │
│   │                   LAPLACE (설명/출처)                         │  │
│   │                                                             │  │
│   │    "소크라테스(470-399 BCE)가 활동하던 아테네는..."            │  │
│   │    📚 출처: Plato, Apology (Perseus Digital Library)        │  │
│   │    🔗 관련: 펠로폰네소스 전쟁, 플라톤, 아리스토파네스           │  │
│   │    📍 지도: 아테네 아고라 위치 표시                            │  │
│   └─────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 핵심 시스템 (FGO 네이밍)

| 시스템 | FGO 참조 | 역할 |
|--------|----------|------|
| **CHALDEAS** | 지구 시뮬레이터 | 세계 상태(World State) 저장소 - 3D 지구본 시각화 |
| **SHEBA** | 근미래관측렌즈 | 패턴 감지, 질의 처리, 이벤트 관측 |
| **LAPLACE** | 사상기록전자해 | 역사 기록, 인과관계 추적, 출처 연결 |
| **TRISMEGISTUS** | 삼중 위대한 자 | 전체 시스템 조율 (Orchestrator) |
| **PAPERMOON** | 종이 달 | AI 제안 검증 및 승인 |
| **LOGOS** | 로고스 | LLM 기반 행동 제안자 |

---

## 기능

- **3D 지구본 시각화**: react-globe.gl 기반 인터랙티브 지구본
- **다중 지구본 스타일**: Blue Marble (실사) / HOLO (홀로그램) / Night (야경)
- **타임라인 탐색**: BCE 3000년 ~ 현재까지 시간 여행
- **이벤트 마커**: 역사적 사건 위치 표시 및 상세 정보
- **카테고리 필터**: 전쟁, 정치, 종교, 철학, 과학 등
- **검색 기능**: 이벤트, 인물, 장소 통합 검색

---

## 기술 스택

| 계층 | 기술 |
|------|------|
| Frontend | React 18 + TypeScript + Vite |
| 3D Globe | react-globe.gl (Three.js) |
| State | Zustand |
| Backend | Python 3.12 + FastAPI |
| Database | PostgreSQL / JSON (개발용) |
| Data | Pleiades, Wikidata, Perseus Digital Library |

---

## 빠른 시작

### 필수 요구사항

- Node.js 20+
- Python 3.12+
- Git

### 설치 및 실행

```bash
# 1. 저장소 클론
git clone https://github.com/medraud94private/CHALDEAS.git
cd CHALDEAS

# 2. Backend 실행
cd backend
python -m venv venv

# Windows:
venv\Scripts\activate
# Mac/Linux:
# source venv/bin/activate

pip install -r requirements.txt
uvicorn app.main:app --reload --port 8100

# 3. Frontend 실행 (새 터미널)
cd frontend
npm install
npm run dev -- --port 5100
```

### 접속

| 서비스 | URL |
|--------|-----|
| Frontend | http://localhost:5100 |
| Backend API | http://localhost:8100 |
| API 문서 | http://localhost:8100/docs |

---

## 프로젝트 구조

```
CHALDEAS/
├── frontend/                    # React SPA
│   ├── src/
│   │   ├── components/
│   │   │   ├── globe/          # 3D 지구본 (CHALDEAS)
│   │   │   ├── timeline/       # 타임라인 컨트롤
│   │   │   └── wiki/           # 상세 패널 (LAPLACE)
│   │   ├── store/              # Zustand 상태 관리
│   │   └── types/              # TypeScript 타입
│   └── ...
│
├── backend/
│   ├── app/
│   │   ├── core/               # World-Centric Core
│   │   │   ├── chaldeas/       # 세계 상태 관리
│   │   │   ├── sheba/          # 관측 시스템
│   │   │   ├── laplace/        # 설명 시스템
│   │   │   ├── trismegistus/   # 오케스트레이터
│   │   │   ├── papermoon/      # 검증 시스템
│   │   │   └── logos/          # LLM 제안자
│   │   ├── api/v1/             # REST API
│   │   ├── models/             # 데이터 모델
│   │   └── services/           # 비즈니스 로직
│   └── ...
│
├── data/
│   ├── json/                   # 수집된 데이터
│   └── scripts/                # 데이터 수집 스크립트
│
└── docs/                       # 문서
```

---

## 데이터 소스

| 소스 | 데이터 | 상태 |
|------|--------|------|
| **Pleiades** | 고대 지중해 지명/좌표 | 수집 완료 (36,000+ 위치) |
| **Wikidata** | 역사 이벤트/인물 | 수집 완료 (1,400+ 이벤트) |
| **Perseus Digital Library** | 고전 문헌 | 계획 중 |
| **Chinese Text Project** | 동양 고전 | 계획 중 |

---

## 로드맵

- [x] 3D 지구본 시각화
- [x] 이벤트 마커 및 상세 패널
- [x] 타임라인 컨트롤 (재생 기능)
- [x] 다중 지구본 스타일 (Blue Marble, HOLO, Night)
- [x] 카테고리 필터링
- [ ] AI 질의응답 (SHEBA + LOGOS)
- [ ] 인물 관계 그래프
- [ ] 다국어 지원 (한국어/영어/일본어)

---

## 라이선스

MIT License

---

## 참고

- [Fate/Grand Order](https://fate-go.jp/) - 영감의 원천
- [react-globe.gl](https://github.com/vasturiano/react-globe.gl) - 3D 지구본 라이브러리
- [Pleiades](https://pleiades.stoa.org/) - 고대 지명 데이터베이스
