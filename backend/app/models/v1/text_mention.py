"""
Text Mention and Entity Alias models.

Tracks NER extraction provenance and handles entity deduplication.

TextMention: Records where each entity was mentioned in source documents.
EntityAlias: Maps alternate names/spellings to canonical entities.

This enables LAPLACE to provide source attribution for any historical fact.
"""
from sqlalchemy import (
    Column, Integer, String, Text, Float, ForeignKey,
    CheckConstraint, DateTime, Index, UniqueConstraint
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.models.base import Base


class TextMention(Base):
    """
    Records where an entity was mentioned in a source document.

    Used for:
    - Source attribution (LAPLACE)
    - Confidence aggregation
    - Entity verification
    - Batch import tracking
    """
    __tablename__ = "text_mentions"

    id = Column(Integer, primary_key=True, index=True)

    # Which entity was mentioned
    entity_type = Column(
        String(50),
        CheckConstraint(
            "entity_type IN ('person', 'location', 'event', 'polity', 'period')"
        ),
        nullable=False,
        index=True
    )
    entity_id = Column(Integer, nullable=False, index=True)

    # Where it was mentioned
    source_id = Column(Integer, ForeignKey("sources.id", ondelete="CASCADE"), nullable=False, index=True)

    # Context of mention
    mention_text = Column(String(500))  # The exact extracted text
    context_text = Column(Text)  # Surrounding text for disambiguation
    position_start = Column(Integer)  # Character offset in document
    position_end = Column(Integer)
    chunk_index = Column(Integer)  # If document was chunked for processing

    # Extraction metadata
    confidence = Column(Float, nullable=False, default=1.0)
    extraction_model = Column(String(100))  # gpt-5-nano, spacy, etc.
    extracted_at = Column(DateTime, default=func.now())

    # Batch processing tracking
    batch_id = Column(String(100), index=True)  # Batch job identifier
    request_id = Column(String(100))  # Individual request within batch

    # Manual verification
    is_verified = Column(Integer, default=0)  # 0=unverified, 1=confirmed, -1=rejected
    verified_by = Column(String(100))
    verified_at = Column(DateTime)

    # Relationships
    source = relationship("Source")

    __table_args__ = (
        # Composite index for entity lookup
        Index('idx_text_mentions_entity', 'entity_type', 'entity_id'),
        # Index for batch tracking
        Index('idx_text_mentions_batch', 'batch_id', 'request_id'),
        # Index for confidence filtering
        Index('idx_text_mentions_confidence', 'confidence'),
    )

    def __repr__(self):
        return f"<TextMention({self.entity_type}:{self.entity_id} in source:{self.source_id})>"


class EntityAlias(Base):
    """
    Maps alternate names, spellings, and translations to canonical entities.

    Used for:
    - Entity deduplication during NER import
    - Multi-language search
    - Historical name variations
    - Common misspellings
    """
    __tablename__ = "entity_aliases"

    id = Column(Integer, primary_key=True, index=True)

    # Which entity this alias points to
    entity_type = Column(
        String(50),
        CheckConstraint(
            "entity_type IN ('person', 'location', 'event', 'polity', 'period')"
        ),
        nullable=False,
        index=True
    )
    entity_id = Column(Integer, nullable=False, index=True)

    # The alias text
    alias = Column(String(500), nullable=False, index=True)

    # Classification of alias type
    alias_type = Column(
        String(50),
        CheckConstraint(
            "alias_type IN ('canonical', 'alternate', 'abbreviation', 'translation', "
            "'misspelling', 'historical', 'latinized', 'romanized')"
        ),
        default='alternate'
    )

    # Language of alias (ISO 639-1)
    language = Column(String(10))  # en, ko, la, gr, ar, zh, etc.

    # Source of this alias
    source_id = Column(Integer, ForeignKey("sources.id"), nullable=True)

    # Metadata
    created_at = Column(DateTime, default=func.now())
    is_primary = Column(Integer, default=0)  # 1 if this is the display name for this language

    # Relationships
    source = relationship("Source")

    __table_args__ = (
        # Ensure unique alias per entity (same alias can point to different entities)
        UniqueConstraint('entity_type', 'entity_id', 'alias', name='uq_entity_alias'),
        # Index for alias lookup (case-insensitive search done at query level)
        Index('idx_alias_lookup', 'alias'),
        # Index for finding all aliases of an entity
        Index('idx_entity_aliases', 'entity_type', 'entity_id'),
    )

    def __repr__(self):
        return f"<EntityAlias('{self.alias}' -> {self.entity_type}:{self.entity_id})>"


class ImportBatch(Base):
    """
    Tracks NER batch processing jobs.

    Used for:
    - Resumable imports
    - Error tracking
    - Statistics reporting
    """
    __tablename__ = "import_batches"

    id = Column(Integer, primary_key=True, index=True)

    # Batch identification
    batch_name = Column(String(255), nullable=False, unique=True)
    batch_type = Column(String(50))  # ner_extraction, enrichment, linking

    # Status
    status = Column(
        String(50),
        CheckConstraint(
            "status IN ('pending', 'processing', 'completed', 'failed', 'partial')"
        ),
        default='pending',
        index=True
    )

    # Statistics
    total_documents = Column(Integer, default=0)
    processed_documents = Column(Integer, default=0)
    failed_documents = Column(Integer, default=0)
    total_entities = Column(Integer, default=0)
    new_entities = Column(Integer, default=0)
    linked_entities = Column(Integer, default=0)

    # Timing
    started_at = Column(DateTime)
    completed_at = Column(DateTime)

    # Configuration
    model_used = Column(String(100))
    config_json = Column(Text)  # JSON string of batch configuration

    # Error tracking
    error_log = Column(Text)
    last_error = Column(Text)

    # Timestamps
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<ImportBatch('{self.batch_name}', status='{self.status}')>"

    @property
    def progress_percent(self) -> float:
        """Calculate processing progress."""
        if self.total_documents == 0:
            return 0.0
        return (self.processed_documents / self.total_documents) * 100


class PendingEntity(Base):
    """
    Entities awaiting resolution (link to existing or create new).

    Used for:
    - Archivist disambiguation queue
    - Human review queue
    - Batch entity linking
    """
    __tablename__ = "pending_entities"

    id = Column(Integer, primary_key=True, index=True)

    # Extracted data
    entity_type = Column(String(50), nullable=False, index=True)
    extracted_name = Column(String(500), nullable=False, index=True)
    extracted_data = Column(Text)  # JSON string of full extracted attributes

    # Source
    source_id = Column(Integer, ForeignKey("sources.id"), nullable=True)
    batch_id = Column(Integer, ForeignKey("import_batches.id"), nullable=True, index=True)

    # Matching candidates (JSON array)
    # [{entity_id, similarity, confidence}, ...]
    candidates = Column(Text)

    # Best match info (for quick filtering)
    best_match_id = Column(Integer)
    best_match_similarity = Column(Float)

    # Status
    status = Column(
        String(50),
        CheckConstraint(
            "status IN ('pending', 'resolved_link', 'resolved_new', 'rejected', 'needs_review')"
        ),
        default='pending',
        index=True
    )

    # Resolution
    resolved_entity_id = Column(Integer)
    resolved_at = Column(DateTime)
    resolved_by = Column(String(100))  # llm, manual, auto

    # Priority (higher = more urgent)
    priority = Column(Integer, default=0, index=True)

    # Timestamps
    created_at = Column(DateTime, default=func.now())

    # Relationships
    source = relationship("Source")
    batch = relationship("ImportBatch")

    __table_args__ = (
        Index('idx_pending_status_priority', 'status', 'priority'),
    )

    def __repr__(self):
        return f"<PendingEntity('{self.extracted_name}', type='{self.entity_type}', status='{self.status}')>"
