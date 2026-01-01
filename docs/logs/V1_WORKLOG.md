# CHALDEAS V1 작업 로그

## 형식

```
## [날짜] 세션 #N

### 작업 내용
- [CP-X.X] 체크포인트 ID
- 상태: ✅ 완료 / 🔄 진행중 / ❌ 실패

### 변경 파일
- `path/to/file.py` - 설명

### 이슈/메모
- 발견한 문제점이나 메모

### 다음 작업
- 다음에 할 일
```

---

## [2026-01-01] 세션 #1

### 작업 내용
- 문서 정리 및 V1 계획 수립

### 생성된 문서
| 문서 | 경로 | 설명 |
|-----|------|------|
| 방법론 | `docs/planning/METHODOLOGY.md` | 학술 참고자료 (CIDOC-CRM, EventKG 등) |
| 컨셉 | `docs/planning/HISTORICAL_CHAIN_CONCEPT.md` | 역사의 고리 4가지 큐레이션 유형 |
| 재설계 계획 | `docs/planning/REDESIGN_PLAN.md` | V1 아키텍처 설계 |
| 비용 산정 | `docs/planning/COST_ESTIMATION.md` | AI 호출 비용 (~$47 초기, ~$7/월) |
| 모델 목록 | `docs/planning/MODELS.md` | 사용 AI 모델 정리 |
| 작업 계획 | `docs/planning/V1_WORKPLAN.md` | 체크포인트별 작업 계획 |

### 결정 사항
- V0 = 기존 레거시 (운영 유지)
- V1 = 신규 Historical Chain 구조
- 초기 비용 ~$47 승인됨

### 다음 작업
- [x] CLAUDE.md 업데이트
- [x] CP-1.1: V1 디렉토리 구조 생성
- [ ] CP-1.2: Period 모델 생성

---

## [2026-01-01] 세션 #1 (계속)

### 작업 내용
- [CP-1.1] V1 디렉토리 구조 생성 ✅

### 생성된 파일
| 파일 | 설명 |
|-----|------|
| `backend/app/models/v1/__init__.py` | V1 모델 패키지 |
| `backend/app/api/v1_new/__init__.py` | V1 API 라우터 |
| `backend/app/schemas/v1/__init__.py` | V1 Pydantic 스키마 |
| `backend/app/core/chain/__init__.py` | Chain 생성 로직 |
| `backend/app/core/extraction/__init__.py` | NER 파이프라인 |

### 다음 작업
- [x] CP-1.2: Period 모델 생성
- [ ] CP-1.3: Location 이중 계층 확장

---

## [2026-01-01] 세션 #1 (계속)

### 작업 내용
- [CP-1.2] Period 모델 생성 ✅

### 생성된 파일
| 파일 | 설명 |
|-----|------|
| `backend/app/models/v1/period.py` | Period SQLAlchemy 모델 (Braudel's temporal scale 포함) |
| `backend/app/schemas/v1/period.py` | Period Pydantic 스키마 |
| `backend/app/db/seeds/periods.json` | 초기 시대 데이터 (30+ 시대, 계층 구조 포함) |

### 시드 데이터 포함 시대
- Ancient History (고대사) - 하위: 이집트, 메소포타미아, 그리스, 로마, 중국
- Medieval History (중세사) - 하위: 초기/성기/말기 중세, 이슬람 황금기
- Early Modern (근세) - 하위: 르네상스, 대항해시대, 종교개혁, 계몽주의
- Modern History (근현대) - 하위: 산업혁명, 세계대전, 냉전
- Mediterranean Trade Culture (지중해 무역 문화)
- Silk Road Era (실크로드 시대)

### 다음 작업
- [x] CP-1.3: Location 이중 계층 확장
- [x] CP-1.4: Event 필드 확장
- [ ] CP-1.5: Phase 1 마이그레이션

---

## [2026-01-01] 세션 #1 (계속)

### 작업 내용
- [CP-1.3] Location 이중 계층 확장 ✅
- [CP-1.4] Event 필드 확장 ✅

### 수정된 파일
| 파일 | 변경 내용 |
|-----|----------|
| `backend/app/models/location.py` | modern_parent_id, historical_parent_id, hierarchy_level, valid_from, valid_until 추가 |
| `backend/app/models/event.py` | temporal_scale, period_id, certainty 추가 |

### Phase 1 모델 확장 완료!
- ✅ CP-1.1: V1 디렉토리 구조
- ✅ CP-1.2: Period 모델
- ✅ CP-1.3: Location 확장
- ✅ CP-1.4: Event 확장
- ⬜ CP-1.5: 마이그레이션 (다음)

### 다음 작업
- [ ] CP-1.5: Phase 1 마이그레이션 생성

---

## [2026-01-01] 세션 #2 - PoC 구축

### 작업 내용
- PoC 백엔드 전체 구축 ✅

### 결정 사항
- 본 백엔드 직접 마이그레이션 대신 별도 PoC로 개념 검증 후 통합
- NER: spaCy (무료) + LLM 검증 (선택적)
- 로컬 LLM (Ollama) 옵션 검토 예정
- 임베딩은 OpenAI text-embedding-3-small 유지 (성능 우선)

### 생성된 파일
| 경로 | 설명 |
|-----|------|
| `poc/app/main.py` | FastAPI 메인 앱 |
| `poc/app/config.py` | SQLite 설정 |
| `poc/app/database.py` | Async SQLAlchemy 설정 |
| `poc/app/models/` | Period, Person, Location, Event, Chain, TextMention |
| `poc/app/schemas/chain.py` | Chain Pydantic 스키마 |
| `poc/app/api/chains.py` | 큐레이션 API (/curate 포함) |
| `poc/app/api/entities.py` | 엔티티 CRUD API |
| `poc/app/services/chain_generator.py` | 4가지 체인 타입 생성 로직 |
| `poc/app/core/extraction/ner_pipeline.py` | 하이브리드 NER (spaCy + GPT) |
| `poc/scripts/seed_db.py` | 테스트 데이터 시딩 |
| `poc/scripts/test_ner.py` | NER 파이프라인 테스트 |
| `poc/data/seeds/sample_data.json` | 샘플 역사 데이터 |
| `poc/README.md` | PoC 사용법 |

### 테스트 결과
- ✅ 데이터베이스 시딩 성공 (3 periods, 5 persons, 5 events, 3 locations)
- ✅ API 엔드포인트 동작 확인
- ✅ NER spaCy 기본 동작 확인
- ⚠️ spaCy 단독 NER 정확도 낮음 ("Julius Caesar" → location) → LLM 검증 필요성 확인

---

## [2026-01-01] 세션 #3 - Ollama 로컬 LLM 통합

### 작업 내용
- Ollama 설치 및 Qwen3 8B 모델 다운로드 ✅
- NER 파이프라인에 Ollama 통합 ✅
- 100% 무료 NER 파이프라인 완성 ✅

### 설치된 환경
| 항목 | 버전/크기 |
|-----|----------|
| Ollama | v0.13.5 |
| Qwen3 8B | 5.2GB |
| 경로 | `C:\Users\ryuti\AppData\Local\Programs\Ollama\` |

### 수정된 파일
| 파일 | 변경 내용 |
|-----|----------|
| `poc/app/config.py` | Ollama 설정 추가 (llm_provider, ollama_base_url, ollama_model) |
| `poc/app/core/extraction/ner_pipeline.py` | Ollama API 호출 로직 추가, 타임아웃 300초로 증가 |
| `poc/scripts/test_ollama.py` | Ollama 테스트 스크립트 생성 |

### config.py 설정
```python
llm_provider: str = "ollama"  # 기본값: 무료 로컬
ollama_base_url: str = "http://localhost:11434"
ollama_model: str = "qwen3:8b"

# OpenAI는 폴백용 (gpt-5-nano, gpt-5.1-chat-latest)
```

### 테스트 결과 - NER 정확도 비교

| 엔티티 | spaCy만 | spaCy + Ollama |
|--------|---------|----------------|
| Athens | location | location ✓ |
| **BCE** | ❌ location | ✅ **time** |
| Plato | person | person ✓ |

**핵심 성과**: Ollama가 spaCy의 오류(BCE를 location으로 분류)를 time으로 정확히 수정

### 비용 비교

| 방식 | 1000 텍스트 처리 비용 |
|-----|---------------------|
| **spaCy + Ollama** | **$0 (무료)** |
| spaCy + OpenAI gpt-5-nano | ~$0.15 |
| 임베딩 (OpenAI) | ~$0.02/백만토큰 (유지) |

### 사용자 PC 스펙 확인
- PC1: 32GB RAM + RTX 3060 (12GB VRAM) - Qwen3 8B 실행 가능
- PC2: 64GB RAM + RTX 2070 (8GB VRAM) - Qwen3 8B Q4 실행 가능

### 사용법
```bash
# Ollama 시작 (자동 시작 아닐 경우)
ollama serve

# PoC 테스트
cd poc
python scripts/test_ollama.py
```

### 다음 작업
- [ ] 더 많은 역사 텍스트로 NER 정확도 검증
- [ ] 체인 생성 API 테스트 (/curate)
- [ ] 프론트엔드 연동 테스트

---

<!-- 새 세션 로그는 여기 위에 추가 -->
