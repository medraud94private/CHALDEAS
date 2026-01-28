# V3 데이터 진입 파이프라인

## 개요

V3 시스템 완성 후 신규 데이터가 들어오는 모든 경로와 처리 방법 정의.

---

## 데이터 진입 경로

```
┌─────────────────────────────────────────────────────────────┐
│                     데이터 진입 경로                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐ │
│  │ Wikipedia │   │ Wikidata │   │   User   │   │  Admin   │ │
│  │  Update   │   │  Update  │   │  Submit  │   │  Manual  │ │
│  └────┬─────┘   └────┬─────┘   └────┬─────┘   └────┬─────┘ │
│       │              │              │              │        │
│       ▼              ▼              ▼              ▼        │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              Ingestion Gateway API                   │   │
│  │         POST /api/v3/ingest/{source_type}           │   │
│  └─────────────────────┬───────────────────────────────┘   │
│                        │                                    │
│                        ▼                                    │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              Processing Pipeline                     │   │
│  │  1. Validate → 2. Classify → 3. Enrich → 4. Store   │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 1. Wikipedia 업데이트 경로

### 1-1. 정기 덤프 업데이트 (월간)

```python
# cron: 0 0 1 * * (매월 1일)

class WikipediaDumpUpdater:
    """Wikipedia 덤프 변경분 감지 및 처리"""

    def check_for_updates(self):
        """최신 덤프와 기존 덤프 비교"""
        latest_dump = download_latest_dump_metadata()
        if latest_dump.date > self.last_processed_date:
            return self.get_changed_articles(latest_dump)
        return []

    def process_updates(self, changed_articles: List[str]):
        for article_path in changed_articles:
            # 기존 데이터 있으면 업데이트, 없으면 신규
            existing = db.query(HistoricalUnit).filter_by(
                wikipedia_path=article_path
            ).first()

            article_data = extract_from_zim(article_path)
            classified = classify_entity(article_data)

            if existing:
                self.update_unit(existing, article_data)
            elif classified:
                self.create_unit(article_data, classified)
```

### 1-2. 실시간 변경 감지 (선택적)

```python
# Wikipedia EventStreams API 활용
# https://stream.wikimedia.org/v2/stream/recentchange

class WikipediaStreamListener:
    """실시간 Wikipedia 편집 감지"""

    STREAM_URL = "https://stream.wikimedia.org/v2/stream/recentchange"

    async def listen(self):
        async with aiohttp.ClientSession() as session:
            async with session.get(self.STREAM_URL) as response:
                async for line in response.content:
                    if line.startswith(b'data:'):
                        change = json.loads(line[5:])
                        if self.is_relevant(change):
                            await self.queue_for_processing(change)

    def is_relevant(self, change: dict) -> bool:
        """우리가 추적하는 문서인지 확인"""
        # 1. 이미 DB에 있는 문서
        # 2. 역사적 인물/사건/장소로 분류될 가능성 있는 문서
        return (
            change['namespace'] == 0 and  # Main namespace
            change['wiki'] == 'enwiki' and
            self.might_be_historical(change['title'])
        )
```

---

## 2. Wikidata 업데이트 경로

### 2-1. QID 기반 변경 감지

```python
class WikidataUpdater:
    """Wikidata 변경사항 반영"""

    def check_updates_for_qids(self, qids: List[str]):
        """우리 DB에 있는 QID들의 변경사항 확인"""
        query = """
        SELECT ?item ?modified WHERE {
          VALUES ?item { %s }
          ?item schema:dateModified ?modified.
          FILTER(?modified > "%s"^^xsd:dateTime)
        }
        """ % (
            ' '.join(f'wd:{qid}' for qid in qids),
            self.last_check_time.isoformat()
        )
        return self.sparql_query(query)

    def apply_wikidata_update(self, qid: str):
        """단일 아이템 업데이트"""
        unit = db.query(HistoricalUnit).filter_by(wikidata_id=qid).first()
        if not unit:
            return

        # 날짜 정보 업데이트
        dates = get_wikidata_dates(qid)
        if dates['start']:
            unit.date_start = dates['start']
            unit.date_start_precision = dates['precision']

        # 관계 업데이트
        new_periods = get_wikidata_period(qid)
        self.sync_period_relations(unit, new_periods)

        db.commit()
```

### 2-2. 신규 QID 발견

```python
def discover_new_entities_from_wikidata():
    """Wikidata에서 새로운 역사적 엔티티 발견"""
    query = """
    SELECT ?item ?itemLabel ?start ?end WHERE {
      ?item wdt:P31/wdt:P279* wd:Q178561.  # 전투
      ?item wdt:P580 ?start.
      FILTER(?start < "1900-01-01"^^xsd:dateTime)
      FILTER NOT EXISTS {
        ?item wdt:P31 wd:Q4167410.  # disambiguation 제외
      }
      SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
    }
    LIMIT 1000
    """
    # 우리 DB에 없는 것만 필터링 후 추가
```

---

## 3. 사용자 제출 경로

### 3-1. 웹 UI 제출

```typescript
// Frontend: 신규 엔티티 제안 폼
interface EntitySubmission {
  type: 'person' | 'location' | 'event' | 'period';
  name: string;
  name_ko?: string;
  year_start?: number;
  year_end?: number;
  description: string;
  sources: string[];  // URL 또는 참고문헌
  wikidata_qid?: string;
  wikipedia_url?: string;
}

// API: POST /api/v3/submit
```

### 3-2. 검증 및 승인 플로우

```python
class SubmissionProcessor:
    """사용자 제출 처리"""

    def process_submission(self, submission: EntitySubmission):
        # 1. 중복 체크
        duplicates = self.find_potential_duplicates(submission)
        if duplicates:
            return {"status": "duplicate_check", "candidates": duplicates}

        # 2. Wikidata 검증 (QID 제공된 경우)
        if submission.wikidata_qid:
            wikidata_info = verify_wikidata(submission.wikidata_qid)
            if not wikidata_info:
                return {"status": "invalid_qid"}

        # 3. 대기열에 추가 (관리자 승인 필요)
        pending = PendingSubmission(
            data=submission,
            status='pending_review',
            submitted_at=datetime.now()
        )
        db.add(pending)

        return {"status": "pending", "id": pending.id}

    def approve_submission(self, submission_id: int, admin_id: int):
        """관리자 승인"""
        pending = db.query(PendingSubmission).get(submission_id)

        # 정식 엔티티로 변환
        unit = self.create_historical_unit(pending.data)

        # Wikidata 보강
        if unit.wikidata_id:
            enrich_from_wikidata(unit)

        # 승인 기록
        pending.status = 'approved'
        pending.approved_by = admin_id
        pending.approved_at = datetime.now()

        db.commit()
```

### 3-3. 수정 제안

```python
class EditSuggestion:
    """기존 엔티티 수정 제안"""

    def suggest_edit(self, unit_id: int, changes: dict, reason: str):
        suggestion = EntityEditSuggestion(
            unit_id=unit_id,
            proposed_changes=changes,
            reason=reason,
            status='pending'
        )
        db.add(suggestion)
        return suggestion.id
```

---

## 4. 관리자 수동 경로

### 4-1. 관리자 대시보드

```python
# Admin API endpoints

@router.post("/admin/units")
def create_unit_manual(data: HistoricalUnitCreate, admin: Admin):
    """관리자 직접 생성"""
    unit = HistoricalUnit(**data.dict())
    unit.created_by = admin.id
    unit.is_manual = True
    db.add(unit)

    # 자동 보강 트리거
    if data.wikidata_id:
        background_tasks.add(enrich_from_wikidata, unit.id)

    return unit

@router.post("/admin/bulk-import")
def bulk_import(file: UploadFile, admin: Admin):
    """CSV/JSON 일괄 임포트"""
    # ...
```

### 4-2. 큐레이션 도구

```python
@router.get("/admin/curation/unlinked")
def get_unlinked_units():
    """시대 연결 안 된 유닛 목록"""
    return db.query(HistoricalUnit).filter(
        ~HistoricalUnit.id.in_(
            db.query(HistoricalUnitRelation.source_id)
            .filter(HistoricalUnitRelation.relation_type == 'part_of')
        )
    ).all()

@router.get("/admin/curation/no-location")
def get_units_without_location():
    """장소 없는 유닛 목록"""
    # ...
```

---

## 5. 통합 처리 파이프라인

### 5-1. 공통 프로세서

```python
class IngestionPipeline:
    """모든 진입 경로의 공통 처리"""

    def process(self, raw_data: dict, source_type: str) -> HistoricalUnit:
        # 1. 검증
        validated = self.validate(raw_data, source_type)

        # 2. 분류
        unit_type = self.classify(validated)
        scale = self.determine_scale(validated)

        # 3. 중복 체크
        existing = self.find_existing(validated)
        if existing:
            return self.merge_or_update(existing, validated)

        # 4. 생성
        unit = HistoricalUnit(
            name=validated['name'],
            unit_type=unit_type,
            scale=scale,
            source_type=source_type,
            **validated
        )

        # 5. 보강
        unit = self.enrich(unit)

        # 6. 관계 연결
        self.link_to_periods(unit)
        self.link_to_locations(unit)

        # 7. 저장
        db.add(unit)
        db.commit()

        return unit

    def enrich(self, unit: HistoricalUnit) -> HistoricalUnit:
        """Wikidata 기반 자동 보강"""
        if not unit.wikidata_id:
            # QID 찾기 시도
            unit.wikidata_id = find_wikidata_qid(unit.name, unit.year_start)

        if unit.wikidata_id:
            # 날짜 정밀도
            dates = get_wikidata_dates(unit.wikidata_id)
            if dates:
                unit.date_start = dates.get('start')
                unit.date_start_precision = dates.get('precision')

            # 좌표 (장소인 경우)
            if unit.unit_type == 'location':
                coords = get_wikidata_coords(unit.wikidata_id)
                if coords:
                    unit.latitude = coords['lat']
                    unit.longitude = coords['lng']

        return unit
```

### 5-2. 비동기 작업 큐

```python
# Celery 또는 간단한 작업 큐

@celery.task
def async_enrich_unit(unit_id: int):
    """비동기 Wikidata 보강"""
    unit = db.query(HistoricalUnit).get(unit_id)
    enriched = IngestionPipeline().enrich(unit)
    db.commit()

@celery.task
def async_link_periods(unit_id: int):
    """비동기 시대 연결"""
    unit = db.query(HistoricalUnit).get(unit_id)
    IngestionPipeline().link_to_periods(unit)
    db.commit()

# 배치 처리
@celery.task
def batch_process_pending():
    """대기 중인 제출물 일괄 처리"""
    pending = db.query(PendingSubmission).filter_by(status='auto_approved').all()
    for p in pending:
        process_submission(p)
```

---

## 6. API 엔드포인트 정리

### 6-1. Ingestion API

```
POST /api/v3/ingest/wikipedia     # Wikipedia 문서 추가
POST /api/v3/ingest/wikidata      # Wikidata 아이템 추가
POST /api/v3/ingest/manual        # 수동 추가

GET  /api/v3/ingest/status/{id}   # 처리 상태 확인
GET  /api/v3/ingest/queue         # 대기열 조회
```

### 6-2. User Submission API

```
POST /api/v3/submit               # 신규 엔티티 제안
POST /api/v3/submit/edit/{id}     # 수정 제안
GET  /api/v3/submit/my            # 내 제출 목록
GET  /api/v3/submit/{id}/status   # 제출 상태
```

### 6-3. Admin API

```
GET  /api/v3/admin/pending        # 승인 대기 목록
POST /api/v3/admin/approve/{id}   # 승인
POST /api/v3/admin/reject/{id}    # 거절
POST /api/v3/admin/bulk-import    # 일괄 임포트

GET  /api/v3/admin/curation/*     # 큐레이션 도구
```

---

## 7. 모니터링 및 로깅

```python
class IngestionMetrics:
    """진입 파이프라인 메트릭"""

    def log_ingestion(self, source: str, status: str, unit_id: int = None):
        metric = IngestionLog(
            source_type=source,
            status=status,
            unit_id=unit_id,
            timestamp=datetime.now()
        )
        db.add(metric)

    def get_daily_stats(self, date: date) -> dict:
        return {
            'wikipedia_updates': count_by_source('wikipedia', date),
            'wikidata_updates': count_by_source('wikidata', date),
            'user_submissions': count_by_source('user', date),
            'admin_manual': count_by_source('admin', date),
            'success_rate': calculate_success_rate(date),
        }
```

---

## 8. 데이터 품질 관리

### 8-1. 자동 검증

```python
class DataQualityChecker:
    """데이터 품질 자동 검사"""

    def check_unit(self, unit: HistoricalUnit) -> List[QualityIssue]:
        issues = []

        # 필수 필드
        if not unit.year_start:
            issues.append(QualityIssue('missing_date', 'No start date'))

        # 시간 일관성
        if unit.year_end and unit.year_start > unit.year_end:
            issues.append(QualityIssue('date_order', 'End before start'))

        # 고아 체크 (시대 연결 없음)
        if not unit.period_relations:
            issues.append(QualityIssue('orphan', 'No period link'))

        # 장소 체크
        if unit.scope_type == 'point' and not unit.locations:
            issues.append(QualityIssue('missing_location', 'No location'))

        return issues
```

### 8-2. 주기적 품질 리포트

```python
@celery.task
def weekly_quality_report():
    """주간 데이터 품질 리포트"""
    issues = {
        'missing_dates': count_missing_dates(),
        'missing_locations': count_missing_locations(),
        'orphan_units': count_orphan_units(),
        'duplicate_candidates': find_duplicate_candidates(),
    }
    send_report_email(issues)
```
