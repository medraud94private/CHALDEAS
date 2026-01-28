"""Add multilingual support and source tracking

Revision ID: 004_multilingual_source_tracking
Revises: c8d52fbe79c7
Create Date: 2026-01-28

Adds:
- name_ja, biography_ja for persons
- title_ja, description_ja for events
- name_ja, description_ja for locations
- biography_source, biography_source_url for persons
- description_source, description_source_url for events
- description_source, description_source_url for locations
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '004_multilingual_source_tracking'
down_revision: Union[str, None] = 'c8d52fbe79c7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Persons table - Japanese name/biography + source tracking
    op.add_column('persons', sa.Column('name_ja', sa.String(255), nullable=True))
    op.add_column('persons', sa.Column('biography_ja', sa.Text(), nullable=True))
    op.add_column('persons', sa.Column('biography_source', sa.String(50), nullable=True))
    op.add_column('persons', sa.Column('biography_source_url', sa.String(500), nullable=True))

    # Events table - Japanese title/description + source tracking
    op.add_column('events', sa.Column('title_ja', sa.String(500), nullable=True))
    op.add_column('events', sa.Column('description_ja', sa.Text(), nullable=True))
    op.add_column('events', sa.Column('description_source', sa.String(50), nullable=True))
    op.add_column('events', sa.Column('description_source_url', sa.String(500), nullable=True))

    # Locations table - Japanese name/description + source tracking
    op.add_column('locations', sa.Column('name_ja', sa.String(255), nullable=True))
    op.add_column('locations', sa.Column('description_ja', sa.Text(), nullable=True))
    op.add_column('locations', sa.Column('description_source', sa.String(50), nullable=True))
    op.add_column('locations', sa.Column('description_source_url', sa.String(500), nullable=True))


def downgrade() -> None:
    # Locations table
    op.drop_column('locations', 'description_source_url')
    op.drop_column('locations', 'description_source')
    op.drop_column('locations', 'description_ja')
    op.drop_column('locations', 'name_ja')

    # Events table
    op.drop_column('events', 'description_source_url')
    op.drop_column('events', 'description_source')
    op.drop_column('events', 'description_ja')
    op.drop_column('events', 'title_ja')

    # Persons table
    op.drop_column('persons', 'biography_source_url')
    op.drop_column('persons', 'biography_source')
    op.drop_column('persons', 'biography_ja')
    op.drop_column('persons', 'name_ja')
