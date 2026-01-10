"""Add enrichment tracking fields to events table

Revision ID: 002
Revises: 001
Create Date: 2026-01-08

엔리치먼트 모델 추적을 위한 필드 추가:
- enriched_by: 엔리치먼트에 사용된 모델 (예: "gemma2:9b", "gpt-5.1-chat-latest")
- enriched_at: 엔리치먼트 수행 일시
- enrichment_version: 엔리치먼트 버전 (예: "v1.0", "v2.0-improved")
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '002_enrichment_tracking'
down_revision = '001_v1_schema'
branch_labels = None
depends_on = None


def upgrade():
    # events 테이블에 엔리치먼트 추적 필드 추가
    op.add_column('events', sa.Column('enriched_by', sa.String(100), nullable=True,
                  comment='Model used for enrichment (e.g., gemma2:9b, gpt-5.1)'))
    op.add_column('events', sa.Column('enriched_at', sa.DateTime, nullable=True,
                  comment='When enrichment was performed'))
    op.add_column('events', sa.Column('enrichment_version', sa.String(50), nullable=True,
                  comment='Enrichment pipeline version (e.g., v1.0, v2.0)'))

    # persons 테이블에도 동일하게 추가 (향후 인물 엔리치먼트용)
    op.add_column('persons', sa.Column('enriched_by', sa.String(100), nullable=True,
                  comment='Model used for enrichment'))
    op.add_column('persons', sa.Column('enriched_at', sa.DateTime, nullable=True,
                  comment='When enrichment was performed'))
    op.add_column('persons', sa.Column('enrichment_version', sa.String(50), nullable=True,
                  comment='Enrichment pipeline version'))

    # locations 테이블에도 추가 (지오코딩 추적용)
    op.add_column('locations', sa.Column('geocoded_by', sa.String(100), nullable=True,
                  comment='Model/service used for geocoding (e.g., pleiades, gpt-5.1)'))
    op.add_column('locations', sa.Column('geocoded_at', sa.DateTime, nullable=True,
                  comment='When geocoding was performed'))

    # 인덱스 추가 (모델별 조회용)
    op.create_index('idx_events_enriched_by', 'events', ['enriched_by'])
    op.create_index('idx_events_enrichment_version', 'events', ['enrichment_version'])


def downgrade():
    # 인덱스 삭제
    op.drop_index('idx_events_enrichment_version', 'events')
    op.drop_index('idx_events_enriched_by', 'events')

    # locations 컬럼 삭제
    op.drop_column('locations', 'geocoded_at')
    op.drop_column('locations', 'geocoded_by')

    # persons 컬럼 삭제
    op.drop_column('persons', 'enrichment_version')
    op.drop_column('persons', 'enriched_at')
    op.drop_column('persons', 'enriched_by')

    # events 컬럼 삭제
    op.drop_column('events', 'enrichment_version')
    op.drop_column('events', 'enriched_at')
    op.drop_column('events', 'enriched_by')
