# CHALDEAS 데이터 동기화 가이드

로컬 개발 환경과 GCP Cloud SQL 간 데이터 동기화 방법을 설명합니다.

---

## 데이터 구조

```
data/
├── raw/              # 수집된 원본 데이터 (JSON)
│   ├── wikidata/
│   ├── dbpedia/
│   ├── pleiades/
│   ├── atlas_academy/
│   └── ...
├── processed/        # 변환된 데이터 (JSON)
│   ├── events_*.json
│   ├── persons_*.json
│   └── locations_*.json
└── scripts/          # 수집/변환 스크립트
```

---

## 동기화 방법

### Option 1: 인덱싱 스크립트 실행 (추천)

로컬에서 Cloud SQL로 직접 데이터 인덱싱:

```bash
# 환경변수 설정
export DATABASE_URL="postgresql://chaldeas:qj3sXK5A0jjqFjW_-uu4HCze@34.22.103.164:5432/chaldeas"

# 인덱싱 스크립트 실행
cd backend
python -m app.scripts.index_events
```

### Option 2: pg_dump / pg_restore

로컬 PostgreSQL 데이터를 덤프 후 Cloud SQL에 복원:

```bash
# 1. 로컬 DB 덤프
export PGPASSWORD="chaldeas_dev"
pg_dump -h localhost -p 5433 -U chaldeas -d chaldeas -Fc > chaldeas_backup.dump

# 2. Cloud SQL에 복원
export PGPASSWORD="qj3sXK5A0jjqFjW_-uu4HCze"
pg_restore -h 34.22.103.164 -U chaldeas -d chaldeas -c chaldeas_backup.dump
```

### Option 3: SQL 덤프 (텍스트)

```bash
# 덤프
pg_dump -h localhost -p 5433 -U chaldeas -d chaldeas > backup.sql

# 복원
psql -h 34.22.103.164 -U chaldeas -d chaldeas < backup.sql
```

---

## 테이블 구조 확인

```bash
# Cloud SQL 접속
export PGPASSWORD="qj3sXK5A0jjqFjW_-uu4HCze"
psql -h 34.22.103.164 -U chaldeas -d chaldeas

# 테이블 목록
\dt

# 데이터 개수 확인
SELECT 'events' as table_name, COUNT(*) FROM events
UNION ALL SELECT 'persons', COUNT(*) FROM persons
UNION ALL SELECT 'locations', COUNT(*) FROM locations;
```

---

## 데이터 파이프라인

### 수집 → 변환 → 인덱싱

```bash
# 1. 데이터 수집 (소스에서 raw/ 폴더로)
python data/scripts/collect_all.py

# 2. 데이터 변환 (raw/ → processed/)
python data/scripts/transform_data.py

# 3. 벡터 DB 인덱싱 (processed/ → PostgreSQL)
python backend/app/scripts/index_events.py
```

---

## 주의사항

1. **pgvector 확장**: Cloud SQL에 이미 활성화됨
2. **IP 화이트리스트**: Cloud SQL 접속 시 IP가 자동으로 임시 허용됨 (5분)
3. **대용량 데이터**: 대량 데이터 동기화 시 Cloud SQL Proxy 사용 권장

---

## 접속 정보

| 환경 | 호스트 | 포트 | 데이터베이스 | 사용자 |
|------|--------|------|--------------|--------|
| 로컬 Docker | localhost | 5433 | chaldeas | chaldeas |
| Cloud SQL | 34.22.103.164 | 5432 | chaldeas | chaldeas |

### 비밀번호
- 로컬: `chaldeas_dev`
- Cloud SQL: `qj3sXK5A0jjqFjW_-uu4HCze`
