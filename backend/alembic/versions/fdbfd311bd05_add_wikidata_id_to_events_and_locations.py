"""Add wikidata_id to events and locations

Revision ID: fdbfd311bd05
Revises: 003_event_connections
Create Date: 2026-01-15 11:45:36.293167

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fdbfd311bd05'
down_revision: Union[str, None] = '003_event_connections'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add wikidata_id to events table
    op.add_column('events', sa.Column('wikidata_id', sa.String(50), nullable=True))

    # Add wikidata_id and wikipedia_url to locations table
    op.add_column('locations', sa.Column('wikidata_id', sa.String(50), nullable=True))
    op.add_column('locations', sa.Column('wikipedia_url', sa.String(500), nullable=True))

    # Create indexes for faster lookups
    op.create_index('ix_events_wikidata_id', 'events', ['wikidata_id'])
    op.create_index('ix_locations_wikidata_id', 'locations', ['wikidata_id'])


def downgrade() -> None:
    op.drop_index('ix_locations_wikidata_id', 'locations')
    op.drop_index('ix_events_wikidata_id', 'events')
    op.drop_column('locations', 'wikipedia_url')
    op.drop_column('locations', 'wikidata_id')
    op.drop_column('events', 'wikidata_id')
