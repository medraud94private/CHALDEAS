# Database Schema

## 구현 상태: 완료

## ER Diagram

```
┌─────────────┐       ┌─────────────────┐       ┌─────────────┐
│  Category   │◄──────│      Event      │───────►│  Location   │
├─────────────┤       ├─────────────────┤       ├─────────────┤
│ id          │       │ id              │       │ id          │
│ name        │       │ title           │       │ name        │
│ name_ko     │       │ title_ko        │       │ name_ko     │
│ slug        │       │ description     │       │ latitude    │
│ color       │       │ date_start (*)  │       │ longitude   │
│ parent_id   │       │ date_end        │       │ type        │
└─────────────┘       │ importance      │       │ modern_name │
                      │ category_id     │       └─────────────┘
                      │ location_id     │
                      └────────┬────────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
              ▼                ▼                ▼
       event_persons    event_locations   event_sources
              │                │                │
              ▼                ▼                ▼
        ┌─────────┐      ┌─────────┐      ┌─────────┐
        │ Person  │      │Location │      │ Source  │
        └─────────┘      └─────────┘      └─────────┘
```

## 핵심 테이블

### events
역사적 사건을 저장합니다.

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | SERIAL | Primary Key |
| title | VARCHAR(500) | 영문 제목 |
| title_ko | VARCHAR(500) | 한국어 제목 |
| slug | VARCHAR(500) | URL용 슬러그 |
| date_start | INTEGER | 시작 연도 (음수 = BCE) |
| date_end | INTEGER | 종료 연도 |
| date_precision | VARCHAR(20) | exact/year/decade/century |
| importance | INTEGER | 중요도 (1-5) |
| category_id | FK | 카테고리 참조 |
| primary_location_id | FK | 주요 장소 참조 |

### persons
역사적 인물을 저장합니다.

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | SERIAL | Primary Key |
| name | VARCHAR(255) | 영문 이름 |
| name_ko | VARCHAR(255) | 한국어 이름 |
| birth_year | INTEGER | 출생 연도 (음수 = BCE) |
| death_year | INTEGER | 사망 연도 |
| biography | TEXT | 약력 |
| category_id | FK | 카테고리 참조 |
| birthplace_id | FK | 출생지 참조 |

### locations
지리적 장소를 저장합니다.

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | SERIAL | Primary Key |
| name | VARCHAR(255) | 고대 지명 |
| name_ko | VARCHAR(255) | 한국어 지명 |
| latitude | DECIMAL(10,8) | 위도 |
| longitude | DECIMAL(11,8) | 경도 |
| type | VARCHAR(50) | city/region/landmark |
| modern_name | VARCHAR(255) | 현대 지명 |

### sources
출처 정보를 저장합니다 (LAPLACE용).

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | SERIAL | Primary Key |
| name | VARCHAR(255) | 출처명 |
| type | VARCHAR(50) | primary/secondary/digital_archive |
| url | VARCHAR(500) | URL |
| archive_type | VARCHAR(50) | perseus/ctext/gutenberg 등 |
| reliability | INTEGER | 신뢰도 (1-5) |

## BCE 날짜 처리

- 내부적으로 음수로 저장 (490 BCE → -490)
- 표시 시 변환: `date_display` property 사용

```python
# 예시
event.date_start = -490  # 490 BCE
event.date_display  # "490 BCE"
```

## 구현 파일

- `backend/app/models/event.py`
- `backend/app/models/person.py`
- `backend/app/models/location.py`
- `backend/app/models/source.py`
- `backend/app/models/category.py`
- `backend/app/models/associations.py`
