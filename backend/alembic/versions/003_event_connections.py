"""Event connections table for Historical Chain

Revision ID: 003
Revises: 002_add_enrichment_tracking
Create Date: 2026-01-11

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '003_event_connections'
down_revision = '002_enrichment_tracking'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # event_connections: 이벤트 간 연결 (다층 방향성 그래프)
    op.create_table(
        'event_connections',
        sa.Column('id', sa.Integer(), primary_key=True),

        # 연결된 이벤트 쌍
        sa.Column('event_a_id', sa.Integer(), sa.ForeignKey('events.id', ondelete='CASCADE'), nullable=False),
        sa.Column('event_b_id', sa.Integer(), sa.ForeignKey('events.id', ondelete='CASCADE'), nullable=False),

        # 방향성
        sa.Column('direction', sa.String(20), nullable=False),  # forward, backward, bidirectional, undirected

        # 레이어 정보
        sa.Column('layer_type', sa.String(20), nullable=False),  # person, location, causal, thematic
        sa.Column('layer_entity_id', sa.Integer(), nullable=True),  # person_id, location_id (NULL for causal/thematic)

        # 연결 유형
        sa.Column('connection_type', sa.String(50), nullable=True),  # causes, follows, part_of, etc.

        # 강도 (계산된 값)
        sa.Column('strength_score', sa.Float(), default=0),
        sa.Column('source_count', sa.Integer(), default=0),
        sa.Column('time_distance', sa.Integer(), nullable=True),  # 연도 차이 (절대값)

        # 수동 강도 지정 (LLM/큐레이터가 직접 지정)
        sa.Column('manual_strength', sa.Float(), nullable=True),  # NULL이면 계산값 사용, 값 있으면 override
        sa.Column('manual_reason', sa.Text(), nullable=True),  # 왜 수동 지정했는지

        # 검증 상태
        sa.Column('verification_status', sa.String(20), default='unverified'),  # unverified, auto_verified, llm_verified, curated
        sa.Column('verified_by', sa.String(50), nullable=True),
        sa.Column('verified_at', sa.DateTime(), nullable=True),

        # 큐레이션
        sa.Column('curated_status', sa.String(20), nullable=True),  # approved, rejected, pending
        sa.Column('curated_by', sa.Integer(), nullable=True),
        sa.Column('curated_at', sa.DateTime(), nullable=True),
        sa.Column('curation_note', sa.Text(), nullable=True),

        # 타임스탬프
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # 인덱스
    op.create_index('idx_conn_events', 'event_connections', ['event_a_id', 'event_b_id'])
    op.create_index('idx_conn_direction', 'event_connections', ['direction'])
    op.create_index('idx_conn_layer', 'event_connections', ['layer_type', 'layer_entity_id'])
    op.create_index('idx_conn_strength', 'event_connections', ['strength_score'])
    op.create_index('idx_conn_verification', 'event_connections', ['verification_status'])

    # 복합 유니크: 같은 레이어에서 같은 이벤트 쌍
    op.create_unique_constraint(
        'uq_event_connection_layer',
        'event_connections',
        ['event_a_id', 'event_b_id', 'layer_type']
    )

    # connection_sources: 연결의 증거 (어떤 소스가 이 연결을 언급하는지)
    op.create_table(
        'connection_sources',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('connection_id', sa.Integer(), sa.ForeignKey('event_connections.id', ondelete='CASCADE'), nullable=False),
        sa.Column('source_id', sa.Integer(), sa.ForeignKey('sources.id', ondelete='CASCADE'), nullable=False),

        # 소스 내 위치/문맥
        sa.Column('mention_context', sa.Text(), nullable=True),  # 연결을 언급하는 문맥
        sa.Column('event_a_position', sa.Integer(), nullable=True),  # 텍스트 내 위치
        sa.Column('event_b_position', sa.Integer(), nullable=True),
        sa.Column('proximity_in_text', sa.Integer(), nullable=True),  # 두 이벤트 언급 간 거리

        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_index('idx_connsrc_connection', 'connection_sources', ['connection_id'])
    op.create_index('idx_connsrc_source', 'connection_sources', ['source_id'])


def downgrade() -> None:
    op.drop_table('connection_sources')
    op.drop_table('event_connections')
