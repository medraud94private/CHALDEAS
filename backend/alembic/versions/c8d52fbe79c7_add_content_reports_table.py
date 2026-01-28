"""add content_reports table

Revision ID: c8d52fbe79c7
Revises: 655ce5c78189
Create Date: 2026-01-28 10:48:05.170453

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c8d52fbe79c7'
down_revision: Union[str, None] = '655ce5c78189'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create content_reports table
    op.create_table(
        'content_reports',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('entity_type', sa.String(50), nullable=False, index=True),
        sa.Column('entity_id', sa.Integer(), nullable=False, index=True),
        sa.Column('field_name', sa.String(100), nullable=True),
        sa.Column('report_type', sa.String(50), nullable=False, default='incorrect'),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('suggested_correction', sa.Text(), nullable=True),
        sa.Column('reporter_ip', sa.String(50), nullable=True),
        sa.Column('reporter_session', sa.String(100), nullable=True),
        sa.Column('status', sa.String(50), default='pending', index=True),
        sa.Column('reviewed_by', sa.String(100), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(), nullable=True),
        sa.Column('review_notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.CheckConstraint(
            "entity_type IN ('person', 'event', 'location', 'source')",
            name='ck_content_reports_entity_type'
        ),
        sa.CheckConstraint(
            "report_type IN ('incorrect', 'suspicious', 'low_quality', 'inappropriate', 'other')",
            name='ck_content_reports_report_type'
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'reviewed', 'accepted', 'rejected')",
            name='ck_content_reports_status'
        ),
    )

    # Create composite indexes
    op.create_index('idx_content_report_entity', 'content_reports', ['entity_type', 'entity_id'])
    op.create_index('idx_content_report_status', 'content_reports', ['status', 'created_at'])


def downgrade() -> None:
    op.drop_index('idx_content_report_status', table_name='content_reports')
    op.drop_index('idx_content_report_entity', table_name='content_reports')
    op.drop_table('content_reports')
