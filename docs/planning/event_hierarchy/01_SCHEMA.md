# 이벤트 계층화 - 스키마 설계

## 1. Event 모델 확장

```python
# backend/app/models/event.py

class Event(Base):
    # ... 기존 필드 ...

    # === 계층 구조 ===
    parent_event_id = Column(Integer, ForeignKey('events.id'), nullable=True, index=True)
    is_aggregate = Column(Boolean, default=False, index=True)
    hierarchy_level = Column(Integer, default=3, index=True)
    # 0=Era, 1=Mega, 2=Aggregate, 3=Major, 4=Minor

    # === 표시 설정 ===
    default_collapsed = Column(Boolean, default=False)
    min_zoom_level = Column(Float, default=1.0)
    # 1.0 = 항상 표시, 5.0 = 가까이서만 표시

    # === 집합 이벤트 메타데이터 ===
    aggregate_type = Column(String(50), nullable=True)
    # war, movement, dynasty, expedition, revolution, crisis,
    # artistic_period, philosophical_school, scientific_era

    # === 관계 ===
    children = relationship('Event',
                           backref=backref('parent', remote_side=[id]),
                           lazy='dynamic')
```

## 2. Alembic 마이그레이션

```python
# backend/alembic/versions/XXX_add_event_hierarchy.py

"""Add event hierarchy support

Revision ID: XXX
Create Date: 2026-01-28
"""

from alembic import op
import sqlalchemy as sa

def upgrade():
    # 계층 구조 컬럼
    op.add_column('events', sa.Column('parent_event_id', sa.Integer(), nullable=True))
    op.add_column('events', sa.Column('is_aggregate', sa.Boolean(), server_default='false'))
    op.add_column('events', sa.Column('hierarchy_level', sa.Integer(), server_default='3'))
    op.add_column('events', sa.Column('aggregate_type', sa.String(50), nullable=True))

    # 표시 설정 컬럼
    op.add_column('events', sa.Column('default_collapsed', sa.Boolean(), server_default='false'))
    op.add_column('events', sa.Column('min_zoom_level', sa.Float(), server_default='1.0'))

    # 인덱스
    op.create_index('ix_events_parent_event_id', 'events', ['parent_event_id'])
    op.create_index('ix_events_is_aggregate', 'events', ['is_aggregate'])
    op.create_index('ix_events_hierarchy_level', 'events', ['hierarchy_level'])
    op.create_index('ix_events_aggregate_type', 'events', ['aggregate_type'])

    # 외래키
    op.create_foreign_key(
        'fk_events_parent_event',
        'events', 'events',
        ['parent_event_id'], ['id'],
        ondelete='SET NULL'
    )


def downgrade():
    op.drop_constraint('fk_events_parent_event', 'events', type_='foreignkey')
    op.drop_index('ix_events_aggregate_type', 'events')
    op.drop_index('ix_events_hierarchy_level', 'events')
    op.drop_index('ix_events_is_aggregate', 'events')
    op.drop_index('ix_events_parent_event_id', 'events')
    op.drop_column('events', 'min_zoom_level')
    op.drop_column('events', 'default_collapsed')
    op.drop_column('events', 'aggregate_type')
    op.drop_column('events', 'hierarchy_level')
    op.drop_column('events', 'is_aggregate')
    op.drop_column('events', 'parent_event_id')
```

## 3. 계층 레벨 정의

| Level | 이름 | 설명 | 예시 |
|-------|------|------|------|
| 0 | Era | 시대 구분 | 고대, 중세, 근대 |
| 1 | Mega-Event | 대규모 역사적 흐름 | 로마 제국, 대항해시대 |
| 2 | Aggregate | 집합 이벤트 | 백년전쟁, 르네상스 |
| 3 | Major | 주요 개별 이벤트 | 아쟁쿠르 전투 |
| 4 | Minor | 세부 이벤트 | 소규모 조약, 회담 |

## 4. Aggregate Type 분류

| Type | 설명 | 예시 |
|------|------|------|
| `war` | 전쟁/군사 분쟁 | 백년전쟁, 세계대전 |
| `movement` | 사회/문화 운동 | 민권운동, 여성참정권 |
| `dynasty` | 왕조/정권 시대 | 명 왕조, 무굴 제국 |
| `expedition` | 탐험/원정 | 십자군, 대항해시대 |
| `revolution` | 혁명 | 프랑스 혁명, 산업혁명 |
| `crisis` | 위기/재난 | 흑사병, 대공황 |
| `artistic_period` | 예술 시대 | 르네상스, 바로크 |
| `philosophical_school` | 철학 학파/사조 | 계몽주의, 실존주의 |
| `scientific_era` | 과학 시대 | 과학혁명, 원자력 시대 |
| `religious` | 종교 운동 | 종교개혁, 대각성운동 |

## 5. API 스키마 확장

```python
# backend/app/schemas/event.py

class EventBase(BaseModel):
    # ... 기존 필드 ...
    parent_event_id: Optional[int] = None
    is_aggregate: bool = False
    hierarchy_level: int = 3
    aggregate_type: Optional[str] = None


class EventWithChildren(EventBase):
    children: List['EventBase'] = []
    children_count: int = 0


class EventHierarchy(BaseModel):
    event: EventBase
    ancestors: List[EventBase] = []  # 부모 → 조부모 순
    children: List[EventBase] = []
    siblings: List[EventBase] = []  # 같은 부모의 다른 자식
```

## 6. 쿼리 예시

```python
# 상위 이벤트만 조회
db.query(Event).filter(Event.is_aggregate == True).all()

# 특정 이벤트의 모든 자식
db.query(Event).filter(Event.parent_event_id == parent_id).all()

# 계층 레벨별 조회
db.query(Event).filter(Event.hierarchy_level <= 2).all()

# 줌 레벨에 맞는 이벤트
db.query(Event).filter(Event.min_zoom_level <= current_zoom).all()

# 특정 타입의 집합 이벤트
db.query(Event).filter(
    Event.is_aggregate == True,
    Event.aggregate_type == 'philosophical_school'
).all()
```
