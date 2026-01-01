"""
TextMention Models for PoC
Tracks entity mentions extracted from text sources
"""
from sqlalchemy import Column, Integer, String, Text, Float, ForeignKey, Boolean, CheckConstraint
from sqlalchemy.orm import relationship

from app.database import Base, TimestampMixin


class TextSource(Base, TimestampMixin):
    """
    Source text document (from Gutenberg, CText, Perseus, etc.)
    """
    __tablename__ = "text_sources"

    id = Column(Integer, primary_key=True, index=True)

    # Source identification
    source_type = Column(String(50), nullable=False)  # gutenberg, ctext, perseus
    external_id = Column(String(100))  # Original ID (PG123, etc.)

    # Metadata
    title = Column(String(500))
    author = Column(String(200))
    language = Column(String(10))
    publication_year = Column(Integer)

    # Content
    content = Column(Text)

    # Processing status
    processed = Column(Boolean, default=False)

    # Relationships
    mentions = relationship("TextMention", back_populates="source")

    def __repr__(self):
        return f"<TextSource(id={self.id}, type='{self.source_type}', title='{self.title[:30] if self.title else '?'}...')>"


class TextMention(Base, TimestampMixin):
    """
    An entity mention extracted from a text source.
    Links text fragments to entities (persons, locations, events).
    """
    __tablename__ = "text_mentions"

    id = Column(Integer, primary_key=True, index=True)
    text_source_id = Column(Integer, ForeignKey("text_sources.id", ondelete="CASCADE"), nullable=False, index=True)

    # Position in source
    chunk_start = Column(Integer)
    chunk_end = Column(Integer)

    # Entity type and reference
    entity_type = Column(
        String(20),
        CheckConstraint("entity_type IN ('person', 'location', 'event', 'time')"),
        nullable=False
    )
    entity_id = Column(Integer)  # FK to persons/locations/events based on entity_type

    # Extracted text
    entity_text = Column(String(500))  # Original text
    normalized_text = Column(String(500))  # Normalized name

    # Extraction metadata
    confidence = Column(Float, default=0.0)  # 0.0 - 1.0
    extraction_model = Column(String(50))  # spacy, gpt-5-nano, etc.

    # Context
    quote = Column(Text)  # Surrounding context

    # Relationships
    source = relationship("TextSource", back_populates="mentions")

    # Polymorphic relationships (based on entity_type)
    person_id = Column(Integer, ForeignKey("persons.id"), nullable=True, index=True)
    location_id = Column(Integer, ForeignKey("locations.id"), nullable=True, index=True)
    event_id = Column(Integer, ForeignKey("events.id"), nullable=True, index=True)

    person = relationship("Person", back_populates="mentions")
    location = relationship("Location", back_populates="mentions")
    event = relationship("Event", back_populates="mentions")

    def __repr__(self):
        return f"<TextMention(id={self.id}, type='{self.entity_type}', text='{self.entity_text[:30] if self.entity_text else '?'}...')>"
