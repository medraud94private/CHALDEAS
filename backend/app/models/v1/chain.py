"""
Historical Chain models.

Represents curated narratives connecting historical entities.

4 Chain Types:
1. Person Story: Biographical events in chronological order
2. Place Story: Events at a location over time
3. Era Story: All persons, places, events of a period
4. Causal Chain: Events linked by causation

Theoretical Basis:
- CIDOC-CRM: Event-centric narrative structure
- Braudel/Annales: temporal_scale integration
- Prosopography: Person networks
"""
from sqlalchemy import (
    Column, Integer, String, Text, Boolean, Float, ForeignKey,
    CheckConstraint, DateTime, UniqueConstraint
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.models.base import Base, TimestampMixin


class HistoricalChain(Base, TimestampMixin):
    """
    A curated narrative connecting historical entities.

    Represents one of four curation types:
    - person_story: Life journey of a historical figure
    - place_story: Historical timeline of a location
    - era_story: Comprehensive view of a historical period
    - causal_chain: Cause-effect linked events
    """
    __tablename__ = "historical_chains"

    id = Column(Integer, primary_key=True, index=True)

    # Type classification
    chain_type = Column(
        String(20),
        CheckConstraint(
            "chain_type IN ('person_story', 'place_story', 'era_story', 'causal_chain')"
        ),
        nullable=False,
        index=True
    )
    slug = Column(String(500), unique=True, nullable=False, index=True)

    # Titles (multilingual)
    title = Column(String(500), nullable=False)
    title_ko = Column(String(500))

    # Summary narrative
    summary = Column(Text)
    summary_ko = Column(Text)

    # Focal entity (depends on chain_type)
    # person_story: focal_person_id
    # place_story: focal_location_id
    # era_story: focal_period_id
    # causal_chain: focal_event_id (terminal event)
    focal_person_id = Column(Integer, ForeignKey("persons.id"), nullable=True, index=True)
    focal_location_id = Column(Integer, ForeignKey("locations.id"), nullable=True, index=True)
    focal_period_id = Column(Integer, ForeignKey("periods.id"), nullable=True, index=True)
    focal_event_id = Column(Integer, ForeignKey("events.id"), nullable=True, index=True)

    # Temporal bounds (computed from segments or explicit)
    year_start = Column(Integer, nullable=False, index=True)
    year_end = Column(Integer)
    temporal_scale = Column(String(20))  # Inherited from dominant segment scale

    # Geographic scope
    region = Column(String(100))

    # Statistics
    segment_count = Column(Integer, default=0)
    entity_count = Column(Integer, default=0)  # Total unique entities involved

    # Promotion system: user -> cached -> featured -> system
    status = Column(
        String(20),
        CheckConstraint("status IN ('user', 'cached', 'featured', 'system')"),
        default='user',
        index=True
    )
    access_count = Column(Integer, default=0, index=True)
    last_accessed_at = Column(DateTime)

    # Generation metadata
    is_auto_generated = Column(Boolean, default=False)
    generation_model = Column(String(50))  # gpt-5-nano, manual, etc.
    generation_prompt_hash = Column(String(64))  # For cache invalidation

    # Quality metrics
    quality_score = Column(Float)  # AI-assessed coherence (0-1)
    human_reviewed = Column(Boolean, default=False)

    # Creator info (optional)
    created_by_master_id = Column(Integer, ForeignKey("masters.id"), nullable=True)

    # Relationships
    focal_person = relationship("Person", foreign_keys=[focal_person_id])
    focal_location = relationship("Location", foreign_keys=[focal_location_id])
    focal_period = relationship("Period", foreign_keys=[focal_period_id])
    focal_event = relationship("Event", foreign_keys=[focal_event_id])
    segments = relationship(
        "ChainSegment",
        back_populates="chain",
        order_by="ChainSegment.sequence_number",
        cascade="all, delete-orphan"
    )
    entity_roles = relationship(
        "ChainEntityRole",
        back_populates="chain",
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<HistoricalChain(id={self.id}, type='{self.chain_type}', title='{self.title[:30]}...')>"

    @property
    def focal_entity(self):
        """Return the focal entity based on chain type."""
        mapping = {
            'person_story': self.focal_person,
            'place_story': self.focal_location,
            'era_story': self.focal_period,
            'causal_chain': self.focal_event,
        }
        return mapping.get(self.chain_type)

    @property
    def date_range_display(self) -> str:
        """Human-readable date range."""
        if not self.year_start:
            return "Unknown"

        def format_year(year: int) -> str:
            if year is None:
                return "?"
            era = "BCE" if year < 0 else "CE"
            return f"{abs(year)} {era}"

        start = format_year(self.year_start)
        end = format_year(self.year_end) if self.year_end else "?"

        return f"{start} - {end}"


class ChainSegment(Base):
    """
    A segment within a Historical Chain.

    Each segment represents a node in the chain, typically linked to
    an event but can also reference other entity types.
    """
    __tablename__ = "chain_segments"

    id = Column(Integer, primary_key=True, index=True)
    chain_id = Column(
        Integer,
        ForeignKey("historical_chains.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Position in chain (0-indexed)
    sequence_number = Column(Integer, nullable=False)

    # Segment content
    title = Column(String(500))  # Optional segment title
    narrative = Column(Text)  # AI-generated connecting narrative
    narrative_ko = Column(Text)

    # Linked entity (at least one required)
    event_id = Column(Integer, ForeignKey("events.id"), nullable=True, index=True)
    person_id = Column(Integer, ForeignKey("persons.id"), nullable=True, index=True)
    location_id = Column(Integer, ForeignKey("locations.id"), nullable=True, index=True)
    period_id = Column(Integer, ForeignKey("periods.id"), nullable=True, index=True)

    # Temporal data (derived from entity or explicit)
    year_start = Column(Integer)
    year_end = Column(Integer)
    temporal_scale = Column(String(20))

    # Transition from previous segment
    transition_type = Column(
        String(30),
        CheckConstraint(
            "transition_type IN ('causes', 'follows', 'parallel', 'background', "
            "'consequence', 'enables', 'opposes', NULL)"
        ),
        nullable=True
    )
    transition_strength = Column(Integer)  # 1-5: causal strength
    transition_narrative = Column(Text)  # "This led to..." connector text

    # Importance within chain context
    importance = Column(
        Integer,
        CheckConstraint("importance >= 1 AND importance <= 5"),
        default=3
    )
    is_keystone = Column(Boolean, default=False)  # Critical segment

    # Timestamps
    created_at = Column(DateTime, default=func.now())

    # Relationships
    chain = relationship("HistoricalChain", back_populates="segments")
    event = relationship("Event")
    person = relationship("Person")
    location = relationship("Location")
    period = relationship("Period")

    __table_args__ = (
        UniqueConstraint('chain_id', 'sequence_number', name='uq_chain_segment_order'),
        CheckConstraint(
            "(event_id IS NOT NULL) OR (person_id IS NOT NULL) OR "
            "(location_id IS NOT NULL) OR (period_id IS NOT NULL)",
            name="segment_has_entity"
        ),
    )

    def __repr__(self):
        return f"<ChainSegment(id={self.id}, chain_id={self.chain_id}, seq={self.sequence_number})>"

    @property
    def primary_entity(self):
        """Return the primary linked entity."""
        if self.event:
            return ('event', self.event)
        if self.person:
            return ('person', self.person)
        if self.location:
            return ('location', self.location)
        if self.period:
            return ('period', self.period)
        return None


class ChainEntityRole(Base):
    """
    Tracks entities involved in a chain with their roles.

    Used to quickly identify all persons/locations/events
    that participate in a chain without scanning all segments.
    """
    __tablename__ = "chain_entity_roles"

    id = Column(Integer, primary_key=True, index=True)
    chain_id = Column(
        Integer,
        ForeignKey("historical_chains.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Entity reference (exactly one should be set)
    person_id = Column(Integer, ForeignKey("persons.id"), nullable=True, index=True)
    location_id = Column(Integer, ForeignKey("locations.id"), nullable=True, index=True)
    event_id = Column(Integer, ForeignKey("events.id"), nullable=True, index=True)

    # Role in chain narrative
    role = Column(
        String(50),
        CheckConstraint(
            "role IN ('protagonist', 'antagonist', 'supporting', 'setting', "
            "'catalyst', 'witness', 'context', 'outcome')"
        ),
        nullable=False
    )
    importance = Column(Integer, default=3)  # 1-5
    first_appearance = Column(Integer)  # segment sequence_number

    # Timestamps
    created_at = Column(DateTime, default=func.now())

    # Relationships
    chain = relationship("HistoricalChain", back_populates="entity_roles")
    person = relationship("Person")
    location = relationship("Location")
    event = relationship("Event")

    __table_args__ = (
        CheckConstraint(
            "((person_id IS NOT NULL)::int + "
            "(location_id IS NOT NULL)::int + "
            "(event_id IS NOT NULL)::int) = 1",
            name="exactly_one_entity"
        ),
    )

    def __repr__(self):
        entity_type = 'person' if self.person_id else 'location' if self.location_id else 'event'
        entity_id = self.person_id or self.location_id or self.event_id
        return f"<ChainEntityRole(chain={self.chain_id}, {entity_type}={entity_id}, role='{self.role}')>"
