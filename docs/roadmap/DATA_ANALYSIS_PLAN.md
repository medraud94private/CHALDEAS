# CHALDEAS 데이터 분석 계획

## 개요

Batch NER로 추출된 555K 엔티티와 Historical Chain 데이터에 대한 주기적 분석 계획.

---

## 현재 데이터 현황 (2026-01-07)

### 집계된 NER 데이터

| 엔티티 유형 | 수량 | 비고 |
|------------|------|------|
| **Persons** | 254,943 | 역사적 인물 |
| **Locations** | 116,062 | 지리적 장소 |
| **Events** | 91,977 | 역사적 사건 |
| **Polities** | 59,836 | 정치 단체 |
| **Periods** | 32,393 | 시대/기간 |
| **총합** | **555,211** | |

### 데이터 소스

- **원본 파일**: 76,090+ 텍스트 파일 (~50GB)
- **소스**: Gutenberg, British Library, Perseus, Open Library 등 27+ 아카이브
- **NER 모델**: gpt-5-nano (OpenAI Batch API)

### 저장 위치

```
poc/data/integrated_ner_full/
├── minimal_batch_0X.jsonl          # 원본 배치 요청
├── minimal_batch_0X_output.jsonl   # 배치 결과
└── aggregated/
    ├── persons.json    (67MB)
    ├── locations.json  (32MB)
    ├── events.json     (30MB)
    ├── polities.json   (9MB)
    ├── periods.json    (4MB)
    └── locations_enriched.json (2.6MB)
```

---

## 주기적 분석 항목

### 1. 데이터 품질 분석

#### 1.1 신뢰도 분포

```python
# 분석 스크립트: poc/scripts/analyze_confidence.py
# 실행 주기: 주 1회

분석 항목:
- 엔티티별 신뢰도(confidence) 분포
- 신뢰도 < 0.5인 엔티티 비율
- certainty 레벨별 분포 (fact/probable/legendary/mythological)
```

#### 1.2 중복 분석

```python
# 분석 스크립트: poc/scripts/analyze_duplicates.py
# 실행 주기: 주 1회

분석 항목:
- 이름 기반 중복 후보
- fuzzy matching으로 발견된 유사 엔티티
- canonical_id 연결률
```

#### 1.3 시대별 분포

```python
# 분석 스크립트: poc/scripts/analyze_temporal.py
# 실행 주기: 월 1회

분석 항목:
- 시대(era)별 인물 수
- 연도 범위별 이벤트 분포
- 시대별 데이터 밀도 (BCE vs CE)
```

### 2. 소스 추적 분석

#### 2.1 문서별 추출량

```python
# 분석 스크립트: poc/scripts/analyze_sources.py

분석 항목:
- 소스 문서별 추출 엔티티 수
- 아카이브별 기여도
- 문서 유형별 NER 정확도
```

#### 2.2 언급 패턴

```python
분석 항목:
- 가장 많이 언급된 인물 Top 100
- 가장 많이 언급된 장소 Top 100
- 공동 출현(co-occurrence) 패턴
```

### 3. Historical Chain 분석

#### 3.1 체인 커버리지

```python
# 분석 스크립트: poc/scripts/analyze_chains.py
# 실행 주기: 월 1회

분석 항목:
- Person Story 생성 가능 인물 수 (이벤트 연결된 인물)
- Place Story 생성 가능 장소 수
- Era Story 생성 가능 시대 수
- Causal Chain 후보 이벤트 쌍
```

#### 3.2 연결성 분석

```python
분석 항목:
- 인물-이벤트 연결률
- 장소-이벤트 연결률
- 이벤트 간 인과관계 밀도
```

---

## 분석 스크립트 템플릿

### 기본 분석 스크립트

```python
#!/usr/bin/env python3
"""
CHALDEAS Data Analysis Script Template
Run: python poc/scripts/analyze_XXX.py
"""
import json
from pathlib import Path
from datetime import datetime
from collections import Counter

DATA_PATH = Path("poc/data/integrated_ner_full/aggregated")
OUTPUT_PATH = Path("docs/logs/analysis")

def load_data(entity_type: str) -> list:
    """Load aggregated entity data."""
    with open(DATA_PATH / f"{entity_type}.json", encoding='utf-8') as f:
        return json.load(f)

def save_report(report: dict, name: str):
    """Save analysis report."""
    OUTPUT_PATH.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d")
    with open(OUTPUT_PATH / f"{name}_{timestamp}.json", 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

def main():
    # Load data
    persons = load_data("persons")

    # Analysis
    confidence_dist = Counter()
    for p in persons:
        conf = p.get("confidence", 0.5)
        if conf >= 0.9:
            confidence_dist["high"] += 1
        elif conf >= 0.7:
            confidence_dist["medium"] += 1
        elif conf >= 0.4:
            confidence_dist["low"] += 1
        else:
            confidence_dist["very_low"] += 1

    # Report
    report = {
        "timestamp": datetime.now().isoformat(),
        "total_persons": len(persons),
        "confidence_distribution": dict(confidence_dist)
    }

    save_report(report, "persons_confidence")
    print(json.dumps(report, indent=2))

if __name__ == "__main__":
    main()
```

---

## 분석 일정

### 주간 분석 (매주 월요일)

| 항목 | 스크립트 | 소요 시간 |
|------|----------|----------|
| 신뢰도 분포 | `analyze_confidence.py` | ~5분 |
| 중복 후보 | `analyze_duplicates.py` | ~10분 |
| 임포트 현황 | DB 쿼리 | ~1분 |

### 월간 분석 (매월 1일)

| 항목 | 스크립트 | 소요 시간 |
|------|----------|----------|
| 시대별 분포 | `analyze_temporal.py` | ~15분 |
| 체인 커버리지 | `analyze_chains.py` | ~20분 |
| 연결성 분석 | `analyze_connectivity.py` | ~30분 |
| 종합 리포트 | `generate_monthly_report.py` | ~10분 |

---

## 분석 결과 저장

### 디렉토리 구조

```
docs/logs/analysis/
├── weekly/
│   ├── confidence_20260107.json
│   ├── duplicates_20260107.json
│   └── ...
├── monthly/
│   ├── temporal_202601.json
│   ├── chains_202601.json
│   └── monthly_report_202601.md
└── adhoc/
    └── special_analysis_YYYYMMDD.json
```

### 리포트 형식

#### 주간 리포트 (Markdown)

```markdown
# 주간 데이터 분석 리포트 - 2026-01-07

## 요약
- 총 엔티티: 555,211개
- 신규 임포트: +0 (DB 미실행)
- 고신뢰도 비율: XX%

## 신뢰도 분포
| 레벨 | 수량 | 비율 |
|------|------|------|
| High (≥0.9) | XXX | XX% |
| Medium (0.7-0.9) | XXX | XX% |
| Low (0.4-0.7) | XXX | XX% |
| Very Low (<0.4) | XXX | XX% |

## 중복 후보
- 발견된 유사 엔티티 쌍: XX개
- 처리 필요: XX개

## 다음 주 작업
- [ ] 중복 처리
- [ ] 저신뢰도 검토
```

---

## 자동화 (향후)

### Cron 작업 설정

```bash
# 주간 분석 (매주 월요일 오전 6시)
0 6 * * 1 cd /path/to/chaldeas && python poc/scripts/run_weekly_analysis.py

# 월간 분석 (매월 1일 오전 7시)
0 7 1 * * cd /path/to/chaldeas && python poc/scripts/run_monthly_analysis.py
```

### 알림 설정

```python
# Slack/Discord 웹훅으로 분석 결과 알림
WEBHOOK_URL = os.getenv("ANALYSIS_WEBHOOK_URL")

def send_notification(report: dict):
    if WEBHOOK_URL:
        requests.post(WEBHOOK_URL, json={
            "content": f"분석 완료: {report['summary']}"
        })
```

---

## 다음 단계

1. **DB 임포트 완료 후**
   - 실제 DB 데이터 기반 분석 스크립트 작성
   - 쿼리 기반 실시간 대시보드 구축

2. **분석 스크립트 구현**
   - `poc/scripts/analyze_confidence.py`
   - `poc/scripts/analyze_duplicates.py`
   - `poc/scripts/analyze_temporal.py`

3. **대시보드 구축**
   - Streamlit 또는 Grafana 기반
   - 실시간 데이터 품질 모니터링

---

## 변경 이력

| 날짜 | 변경 내용 |
|-----|----------|
| 2026-01-07 | 초안 작성 |
