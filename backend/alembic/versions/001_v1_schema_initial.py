"""V1 Schema - Historical Chain and NER Support

Revision ID: 001_v1_schema
Revises:
Create Date: 2026-01-06

This migration adds:
1. New tables: polities, historical_chains, chain_segments, chain_entity_roles,
   text_mentions, entity_aliases, import_batches, pending_entities
2. New association tables: polity_relationships, person_polities
3. Extended columns on existing tables: persons, sources, person_relationships, event_relationships

Theoretical Basis:
- CIDOC-CRM: Event-centric ontology
- Braudel/Annales: Temporal scales
- Prosopography: Person network analysis
- Historical GIS: Dual hierarchies
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

# revision identifiers
revision: str = '001_v1_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ===========================================
    # 1. Enable pgvector extension
    # ===========================================
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')
    op.execute('CREATE EXTENSION IF NOT EXISTS pg_trgm')

    # ===========================================
    # 2. Create new tables
    # ===========================================

    # 2.0 Periods table (dependency for historical_chains)
    op.create_table(
        'periods',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('name_ko', sa.String(200)),
        sa.Column('slug', sa.String(200), unique=True, index=True),
        sa.Column('year_start', sa.Integer(), nullable=False),
        sa.Column('year_end', sa.Integer()),
        sa.Column('scale', sa.String(20), default='conjuncture'),
        sa.Column('parent_id', sa.Integer(), sa.ForeignKey('periods.id')),
        sa.Column('description', sa.Text()),
        sa.Column('description_ko', sa.Text()),
        sa.Column('is_manual', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.CheckConstraint(
            "scale IN ('evenementielle', 'conjuncture', 'longue_duree')",
            name='ck_periods_scale'
        ),
    )

    # 2.1 Polities table
    op.create_table(
        'polities',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('name', sa.String(255), nullable=False, index=True),
        sa.Column('name_ko', sa.String(255)),
        sa.Column('name_original', sa.String(255)),
        sa.Column('slug', sa.String(255), unique=True, nullable=False, index=True),
        sa.Column('polity_type', sa.String(50), index=True),
        sa.Column('start_year', sa.Integer(), index=True),
        sa.Column('start_year_precision', sa.String(20), default='year'),
        sa.Column('end_year', sa.Integer()),
        sa.Column('end_year_precision', sa.String(20), default='year'),
        sa.Column('capital_id', sa.Integer(), sa.ForeignKey('locations.id')),
        sa.Column('region', sa.String(100)),
        sa.Column('predecessor_id', sa.Integer(), sa.ForeignKey('polities.id')),
        sa.Column('successor_id', sa.Integer(), sa.ForeignKey('polities.id')),
        sa.Column('parent_polity_id', sa.Integer(), sa.ForeignKey('polities.id')),
        sa.Column('certainty', sa.String(20), default='fact'),
        sa.Column('description', sa.Text()),
        sa.Column('description_ko', sa.Text()),
        sa.Column('embedding', Vector(1536)),
        sa.Column('mention_count', sa.Integer(), default=0),
        sa.Column('avg_confidence', sa.Float(), default=0.0),
        sa.Column('image_url', sa.String(500)),
        sa.Column('wikipedia_url', sa.String(500)),
        sa.Column('wikidata_id', sa.String(50)),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.CheckConstraint(
            "polity_type IN ('empire', 'kingdom', 'republic', 'dynasty', 'city_state', 'tribe', 'confederation', 'caliphate', 'shogunate', 'other')",
            name='ck_polities_type'
        ),
        sa.CheckConstraint(
            "certainty IN ('fact', 'probable', 'legendary', 'mythological')",
            name='ck_polities_certainty'
        ),
    )

    # 2.2 Historical Chains table
    op.create_table(
        'historical_chains',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('chain_type', sa.String(20), nullable=False, index=True),
        sa.Column('slug', sa.String(500), unique=True, nullable=False, index=True),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('title_ko', sa.String(500)),
        sa.Column('summary', sa.Text()),
        sa.Column('summary_ko', sa.Text()),
        sa.Column('focal_person_id', sa.Integer(), sa.ForeignKey('persons.id'), index=True),
        sa.Column('focal_location_id', sa.Integer(), sa.ForeignKey('locations.id'), index=True),
        sa.Column('focal_period_id', sa.Integer(), sa.ForeignKey('periods.id'), index=True),
        sa.Column('focal_event_id', sa.Integer(), sa.ForeignKey('events.id'), index=True),
        sa.Column('year_start', sa.Integer(), nullable=False, index=True),
        sa.Column('year_end', sa.Integer()),
        sa.Column('temporal_scale', sa.String(20)),
        sa.Column('region', sa.String(100)),
        sa.Column('segment_count', sa.Integer(), default=0),
        sa.Column('entity_count', sa.Integer(), default=0),
        sa.Column('status', sa.String(20), default='user', index=True),
        sa.Column('access_count', sa.Integer(), default=0, index=True),
        sa.Column('last_accessed_at', sa.DateTime()),
        sa.Column('is_auto_generated', sa.Boolean(), default=False),
        sa.Column('generation_model', sa.String(50)),
        sa.Column('generation_prompt_hash', sa.String(64)),
        sa.Column('quality_score', sa.Float()),
        sa.Column('human_reviewed', sa.Boolean(), default=False),
        sa.Column('created_by_master_id', sa.Integer(), sa.ForeignKey('masters.id')),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.CheckConstraint(
            "chain_type IN ('person_story', 'place_story', 'era_story', 'causal_chain')",
            name='ck_chains_type'
        ),
        sa.CheckConstraint(
            "status IN ('user', 'cached', 'featured', 'system')",
            name='ck_chains_status'
        ),
    )

    # 2.3 Chain Segments table
    op.create_table(
        'chain_segments',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('chain_id', sa.Integer(), sa.ForeignKey('historical_chains.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('sequence_number', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(500)),
        sa.Column('narrative', sa.Text()),
        sa.Column('narrative_ko', sa.Text()),
        sa.Column('event_id', sa.Integer(), sa.ForeignKey('events.id'), index=True),
        sa.Column('person_id', sa.Integer(), sa.ForeignKey('persons.id'), index=True),
        sa.Column('location_id', sa.Integer(), sa.ForeignKey('locations.id'), index=True),
        sa.Column('period_id', sa.Integer(), sa.ForeignKey('periods.id'), index=True),
        sa.Column('year_start', sa.Integer()),
        sa.Column('year_end', sa.Integer()),
        sa.Column('temporal_scale', sa.String(20)),
        sa.Column('transition_type', sa.String(30)),
        sa.Column('transition_strength', sa.Integer()),
        sa.Column('transition_narrative', sa.Text()),
        sa.Column('importance', sa.Integer(), default=3),
        sa.Column('is_keystone', sa.Boolean(), default=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint('chain_id', 'sequence_number', name='uq_chain_segment_order'),
        sa.CheckConstraint(
            "transition_type IN ('causes', 'follows', 'parallel', 'background', 'consequence', 'enables', 'opposes') OR transition_type IS NULL",
            name='ck_segment_transition'
        ),
        sa.CheckConstraint('importance >= 1 AND importance <= 5', name='ck_segment_importance'),
    )

    # 2.4 Chain Entity Roles table
    op.create_table(
        'chain_entity_roles',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('chain_id', sa.Integer(), sa.ForeignKey('historical_chains.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('person_id', sa.Integer(), sa.ForeignKey('persons.id'), index=True),
        sa.Column('location_id', sa.Integer(), sa.ForeignKey('locations.id'), index=True),
        sa.Column('event_id', sa.Integer(), sa.ForeignKey('events.id'), index=True),
        sa.Column('role', sa.String(50), nullable=False),
        sa.Column('importance', sa.Integer(), default=3),
        sa.Column('first_appearance', sa.Integer()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.CheckConstraint(
            "role IN ('protagonist', 'antagonist', 'supporting', 'setting', 'catalyst', 'witness', 'context', 'outcome')",
            name='ck_entity_role'
        ),
    )

    # 2.5 Import Batches table
    op.create_table(
        'import_batches',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('batch_name', sa.String(255), unique=True, nullable=False),
        sa.Column('batch_type', sa.String(50)),
        sa.Column('status', sa.String(50), default='pending', index=True),
        sa.Column('total_documents', sa.Integer(), default=0),
        sa.Column('processed_documents', sa.Integer(), default=0),
        sa.Column('failed_documents', sa.Integer(), default=0),
        sa.Column('total_entities', sa.Integer(), default=0),
        sa.Column('new_entities', sa.Integer(), default=0),
        sa.Column('linked_entities', sa.Integer(), default=0),
        sa.Column('started_at', sa.DateTime()),
        sa.Column('completed_at', sa.DateTime()),
        sa.Column('model_used', sa.String(100)),
        sa.Column('config_json', sa.Text()),
        sa.Column('error_log', sa.Text()),
        sa.Column('last_error', sa.Text()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.CheckConstraint(
            "status IN ('pending', 'processing', 'completed', 'failed', 'partial')",
            name='ck_batch_status'
        ),
    )

    # 2.6 Text Mentions table
    op.create_table(
        'text_mentions',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('entity_type', sa.String(50), nullable=False, index=True),
        sa.Column('entity_id', sa.Integer(), nullable=False, index=True),
        sa.Column('source_id', sa.Integer(), sa.ForeignKey('sources.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('mention_text', sa.String(500)),
        sa.Column('context_text', sa.Text()),
        sa.Column('position_start', sa.Integer()),
        sa.Column('position_end', sa.Integer()),
        sa.Column('chunk_index', sa.Integer()),
        sa.Column('confidence', sa.Float(), nullable=False, default=1.0),
        sa.Column('extraction_model', sa.String(100)),
        sa.Column('extracted_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('batch_id', sa.String(100), index=True),
        sa.Column('request_id', sa.String(100)),
        sa.Column('is_verified', sa.Integer(), default=0),
        sa.Column('verified_by', sa.String(100)),
        sa.Column('verified_at', sa.DateTime()),
        sa.CheckConstraint(
            "entity_type IN ('person', 'location', 'event', 'polity', 'period')",
            name='ck_mention_entity_type'
        ),
    )
    op.create_index('idx_text_mentions_entity', 'text_mentions', ['entity_type', 'entity_id'])
    op.create_index('idx_text_mentions_batch', 'text_mentions', ['batch_id', 'request_id'])
    op.create_index('idx_text_mentions_confidence', 'text_mentions', ['confidence'])

    # 2.7 Entity Aliases table
    op.create_table(
        'entity_aliases',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('entity_type', sa.String(50), nullable=False, index=True),
        sa.Column('entity_id', sa.Integer(), nullable=False, index=True),
        sa.Column('alias', sa.String(500), nullable=False, index=True),
        sa.Column('alias_type', sa.String(50), default='alternate'),
        sa.Column('language', sa.String(10)),
        sa.Column('source_id', sa.Integer(), sa.ForeignKey('sources.id')),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('is_primary', sa.Integer(), default=0),
        sa.UniqueConstraint('entity_type', 'entity_id', 'alias', name='uq_entity_alias'),
        sa.CheckConstraint(
            "entity_type IN ('person', 'location', 'event', 'polity', 'period')",
            name='ck_alias_entity_type'
        ),
        sa.CheckConstraint(
            "alias_type IN ('canonical', 'alternate', 'abbreviation', 'translation', 'misspelling', 'historical', 'latinized', 'romanized')",
            name='ck_alias_type'
        ),
    )
    op.create_index('idx_entity_aliases', 'entity_aliases', ['entity_type', 'entity_id'])

    # 2.8 Pending Entities table
    op.create_table(
        'pending_entities',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('entity_type', sa.String(50), nullable=False, index=True),
        sa.Column('extracted_name', sa.String(500), nullable=False, index=True),
        sa.Column('extracted_data', sa.Text()),
        sa.Column('source_id', sa.Integer(), sa.ForeignKey('sources.id')),
        sa.Column('batch_id', sa.Integer(), sa.ForeignKey('import_batches.id'), index=True),
        sa.Column('candidates', sa.Text()),
        sa.Column('best_match_id', sa.Integer()),
        sa.Column('best_match_similarity', sa.Float()),
        sa.Column('status', sa.String(50), default='pending', index=True),
        sa.Column('resolved_entity_id', sa.Integer()),
        sa.Column('resolved_at', sa.DateTime()),
        sa.Column('resolved_by', sa.String(100)),
        sa.Column('priority', sa.Integer(), default=0, index=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.CheckConstraint(
            "status IN ('pending', 'resolved_link', 'resolved_new', 'rejected', 'needs_review')",
            name='ck_pending_status'
        ),
    )
    op.create_index('idx_pending_status_priority', 'pending_entities', ['status', 'priority'])

    # 2.9 Polity Relationships table
    op.create_table(
        'polity_relationships',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('polity_id', sa.Integer(), sa.ForeignKey('polities.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('related_polity_id', sa.Integer(), sa.ForeignKey('polities.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('relationship_type', sa.String(50), nullable=False),
        sa.Column('valid_from', sa.Integer()),
        sa.Column('valid_until', sa.Integer()),
        sa.Column('strength', sa.Integer(), default=3),
        sa.Column('description', sa.Text()),
    )

    # 2.10 Person-Polity Affiliations table
    op.create_table(
        'person_polities',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('person_id', sa.Integer(), sa.ForeignKey('persons.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('polity_id', sa.Integer(), sa.ForeignKey('polities.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('role', sa.String(100)),
        sa.Column('valid_from', sa.Integer()),
        sa.Column('valid_until', sa.Integer()),
        sa.Column('is_primary', sa.Integer(), default=0),
    )

    # ===========================================
    # 3. Add columns to existing tables (with IF NOT EXISTS)
    # ===========================================

    # Helper function to add column if not exists
    def add_column_if_not_exists(table, column, column_def):
        op.execute(f"""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = '{table}' AND column_name = '{column}'
                ) THEN
                    ALTER TABLE {table} ADD COLUMN {column} {column_def};
                END IF;
            END
            $$;
        """)

    # 3.1 Extend persons table
    add_column_if_not_exists('persons', 'wikidata_id', 'VARCHAR(50)')
    add_column_if_not_exists('persons', 'canonical_id', 'INTEGER REFERENCES persons(id)')
    add_column_if_not_exists('persons', 'role', 'VARCHAR(255)')
    add_column_if_not_exists('persons', 'era', 'VARCHAR(100)')
    add_column_if_not_exists('persons', 'floruit_start', 'INTEGER')
    add_column_if_not_exists('persons', 'floruit_end', 'INTEGER')
    add_column_if_not_exists('persons', 'certainty', "VARCHAR(20) DEFAULT 'fact'")
    add_column_if_not_exists('persons', 'embedding', 'vector(1536)')
    add_column_if_not_exists('persons', 'primary_polity_id', 'INTEGER REFERENCES polities(id)')
    add_column_if_not_exists('persons', 'mention_count', 'INTEGER DEFAULT 0')
    add_column_if_not_exists('persons', 'avg_confidence', 'FLOAT DEFAULT 0.0')

    # Create index for canonical_id if column was just added
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_persons_canonical_id ON persons(canonical_id);
    """)

    # 3.2 Extend sources table
    add_column_if_not_exists('sources', 'document_id', 'VARCHAR(255)')
    add_column_if_not_exists('sources', 'document_path', 'VARCHAR(500)')
    add_column_if_not_exists('sources', 'title', 'VARCHAR(500)')
    add_column_if_not_exists('sources', 'original_year', 'INTEGER')
    add_column_if_not_exists('sources', 'language', 'VARCHAR(10)')

    op.execute('CREATE INDEX IF NOT EXISTS idx_sources_document_id ON sources(document_id);')

    # 3.3 Extend person_relationships table
    add_column_if_not_exists('person_relationships', 'strength', 'INTEGER DEFAULT 3')
    add_column_if_not_exists('person_relationships', 'valid_from', 'INTEGER')
    add_column_if_not_exists('person_relationships', 'valid_until', 'INTEGER')
    add_column_if_not_exists('person_relationships', 'confidence', 'FLOAT DEFAULT 1.0')
    add_column_if_not_exists('person_relationships', 'is_bidirectional', 'INTEGER DEFAULT 0')

    # 3.4 Extend event_relationships table
    add_column_if_not_exists('event_relationships', 'certainty', "VARCHAR(20) DEFAULT 'probable'")
    add_column_if_not_exists('event_relationships', 'evidence_type', 'VARCHAR(30)')
    add_column_if_not_exists('event_relationships', 'scholarly_citation', 'TEXT')
    add_column_if_not_exists('event_relationships', 'confidence', 'FLOAT DEFAULT 1.0')

    # 3.5 Extend events table (V1 columns)
    add_column_if_not_exists('events', 'temporal_scale', "VARCHAR(20) DEFAULT 'evenementielle'")
    add_column_if_not_exists('events', 'period_id', 'INTEGER REFERENCES periods(id)')
    add_column_if_not_exists('events', 'certainty', "VARCHAR(20) DEFAULT 'fact'")

    # ===========================================
    # 4. Create indexes for performance
    # ===========================================

    # 4.1 Temporal range queries (Historical Chain)
    op.execute('CREATE INDEX IF NOT EXISTS idx_events_temporal_range ON events(date_start, date_end);')
    op.execute('CREATE INDEX IF NOT EXISTS idx_events_period_date ON events(period_id, date_start);')

    # 4.2 Causal chain traversal
    op.execute('CREATE INDEX IF NOT EXISTS idx_event_rel_causal ON event_relationships(from_event_id, relationship_type);')

    # 4.3 Vector similarity search (pgvector) - only if embeddings exist and have data
    # Note: IVFFlat requires data in the table to build, so we use a try-catch approach
    op.execute("""
        DO $$
        BEGIN
            -- Try to create IVFFlat index on persons
            BEGIN
                CREATE INDEX IF NOT EXISTS idx_persons_embedding ON persons USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
            EXCEPTION WHEN OTHERS THEN
                -- Fall back to regular btree if ivfflat fails
                RAISE NOTICE 'Could not create IVFFlat index on persons.embedding: %', SQLERRM;
            END;
            -- Try to create IVFFlat index on polities
            BEGIN
                CREATE INDEX IF NOT EXISTS idx_polities_embedding ON polities USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
            EXCEPTION WHEN OTHERS THEN
                RAISE NOTICE 'Could not create IVFFlat index on polities.embedding: %', SQLERRM;
            END;
        END
        $$;
    """)

    # 4.4 Trigram search for fuzzy matching
    op.execute('CREATE INDEX IF NOT EXISTS idx_persons_name_trgm ON persons USING gin (name gin_trgm_ops);')
    op.execute('CREATE INDEX IF NOT EXISTS idx_locations_name_trgm ON locations USING gin (name gin_trgm_ops);')


def downgrade() -> None:
    # ===========================================
    # 1. Drop indexes
    # ===========================================
    op.execute('DROP INDEX IF EXISTS idx_persons_name_trgm')
    op.execute('DROP INDEX IF EXISTS idx_locations_name_trgm')
    op.execute('DROP INDEX IF EXISTS idx_persons_embedding')
    op.execute('DROP INDEX IF EXISTS idx_polities_embedding')
    op.execute('DROP INDEX IF EXISTS idx_event_rel_causal')
    op.execute('DROP INDEX IF EXISTS idx_events_period_date')
    op.execute('DROP INDEX IF EXISTS idx_events_temporal_range')
    op.execute('DROP INDEX IF EXISTS idx_persons_canonical_id')
    op.execute('DROP INDEX IF EXISTS idx_sources_document_id')

    # ===========================================
    # 2. Remove columns from existing tables
    # ===========================================

    # 2.1 Remove from event_relationships
    op.drop_column('event_relationships', 'confidence')
    op.drop_column('event_relationships', 'scholarly_citation')
    op.drop_column('event_relationships', 'evidence_type')
    op.drop_column('event_relationships', 'certainty')

    # 2.2 Remove from person_relationships
    op.drop_column('person_relationships', 'is_bidirectional')
    op.drop_column('person_relationships', 'confidence')
    op.drop_column('person_relationships', 'valid_until')
    op.drop_column('person_relationships', 'valid_from')
    op.drop_column('person_relationships', 'strength')

    # 2.3 Remove from sources
    op.drop_column('sources', 'language')
    op.drop_column('sources', 'original_year')
    op.drop_column('sources', 'title')
    op.drop_column('sources', 'document_path')
    op.drop_column('sources', 'document_id')

    # 2.4 Remove from persons
    op.drop_column('persons', 'avg_confidence')
    op.drop_column('persons', 'mention_count')
    op.drop_column('persons', 'primary_polity_id')
    op.drop_column('persons', 'embedding')
    op.drop_column('persons', 'certainty')
    op.drop_column('persons', 'floruit_end')
    op.drop_column('persons', 'floruit_start')
    op.drop_column('persons', 'era')
    op.drop_column('persons', 'role')
    op.drop_column('persons', 'canonical_id')
    op.drop_column('persons', 'wikidata_id')

    # ===========================================
    # 3. Drop new tables (in reverse order of dependencies)
    # ===========================================
    op.drop_table('person_polities')
    op.drop_table('polity_relationships')
    op.drop_table('pending_entities')
    op.drop_index('idx_entity_aliases', 'entity_aliases')
    op.drop_table('entity_aliases')
    op.drop_index('idx_text_mentions_confidence', 'text_mentions')
    op.drop_index('idx_text_mentions_batch', 'text_mentions')
    op.drop_index('idx_text_mentions_entity', 'text_mentions')
    op.drop_table('text_mentions')
    op.drop_table('import_batches')
    op.drop_table('chain_entity_roles')
    op.drop_table('chain_segments')
    op.drop_table('historical_chains')
    op.drop_table('polities')
    op.drop_table('periods')
