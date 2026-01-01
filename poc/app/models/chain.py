"""
HistoricalChain Models for PoC
Represents curated historical narratives (chains of connected events)
"""
from sqlalchemy import Column, Integer, String, Text, ForeignKey, CheckConstraint, UniqueConstraint
from sqlalchemy.orm import relationship

from app.database import Base, TimestampMixin


class HistoricalChain(Base, TimestampMixin):
    """
    A curated chain of historical events forming a narrative.

    4 Chain Types:
    - person_story: Biography/life story of a person
    - place_story: History of a location over time
    - era_story: Overview of a period with key events/figures
    - causal_chain: Cause-and-effect sequence of events
    """
    __tablename__ = "historical_chains"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(500), nullable=False)
    title_ko = Column(String(500))
    description = Column(Text)

    # Chain type
    chain_type = Column(
        String(30),
        CheckConstraint("chain_type IN ('person_story', 'place_story', 'era_story', 'causal_chain')"),
        nullable=False
    )

    # Entity references (based on chain_type)
    person_id = Column(Integer, ForeignKey("persons.id"), nullable=True, index=True)
    location_id = Column(Integer, ForeignKey("locations.id"), nullable=True, index=True)
    period_id = Column(Integer, ForeignKey("periods.id"), nullable=True, index=True)

    # Promotion system
    visibility = Column(
        String(20),
        CheckConstraint("visibility IN ('user', 'cached', 'featured', 'system')"),
        default="user"
    )
    access_count = Column(Integer, default=0)

    # Relationships
    person = relationship("Person", back_populates="chains")
    location = relationship("Location", back_populates="chains")
    period = relationship("Period", back_populates="chains")
    segments = relationship("ChainSegment", back_populates="chain", order_by="ChainSegment.segment_order")

    def __repr__(self):
        return f"<HistoricalChain(id={self.id}, type='{self.chain_type}', title='{self.title[:30]}...')>"

    def increment_access(self):
        """Increment access count and check for promotion."""
        self.access_count += 1
        self._check_promotion()

    def _check_promotion(self):
        """Promote visibility based on access count."""
        THRESHOLDS = {
            'user': (5, 'cached'),
            'cached': (50, 'featured'),
            'featured': (200, 'system')
        }
        if self.visibility in THRESHOLDS:
            threshold, next_level = THRESHOLDS[self.visibility]
            if self.access_count >= threshold:
                self.visibility = next_level


class ChainSegment(Base, TimestampMixin):
    """
    A segment (node) in a historical chain.
    Each segment links to one event and includes narrative context.
    """
    __tablename__ = "chain_segments"

    id = Column(Integer, primary_key=True, index=True)
    chain_id = Column(Integer, ForeignKey("historical_chains.id", ondelete="CASCADE"), nullable=False, index=True)
    segment_order = Column(Integer, nullable=False)
    event_id = Column(Integer, ForeignKey("events.id"), nullable=False, index=True)

    # AI-generated narrative
    narrative = Column(Text)
    narrative_ko = Column(Text)

    # Connection to previous segment
    connection_type = Column(String(30))  # causes, follows, parallel, etc.

    # Relationships
    chain = relationship("HistoricalChain", back_populates="segments")
    event = relationship("Event", back_populates="segments")

    __table_args__ = (
        UniqueConstraint('chain_id', 'segment_order', name='uix_chain_segment_order'),
    )

    def __repr__(self):
        return f"<ChainSegment(chain={self.chain_id}, order={self.segment_order}, event={self.event_id})>"
