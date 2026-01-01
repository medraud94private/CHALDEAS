"""
Event Model for PoC
Represents historical events with Braudel's temporal scale
"""
from sqlalchemy import Column, Integer, String, Text, ForeignKey, CheckConstraint
from sqlalchemy.orm import relationship

from app.database import Base, TimestampMixin


class Event(Base, TimestampMixin):
    """Historical event with temporal scale classification."""
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(500), nullable=False, index=True)
    name_ko = Column(String(500))

    # Time range (BCE as negative)
    date_start = Column(Integer, nullable=False, index=True)
    date_end = Column(Integer)

    # Braudel's temporal scale
    temporal_scale = Column(
        String(20),
        CheckConstraint("temporal_scale IN ('evenementielle', 'conjuncture', 'longue_duree')"),
        default="evenementielle"
    )

    # Certainty level
    certainty = Column(
        String(20),
        CheckConstraint("certainty IN ('fact', 'probable', 'legendary', 'mythological')"),
        default="fact"
    )

    # Link to Period
    period_id = Column(Integer, ForeignKey("periods.id"), nullable=True, index=True)

    # Category
    category = Column(String(100))

    # Importance (1-10)
    importance = Column(Integer, default=5)

    # Description
    description = Column(Text)
    description_ko = Column(Text)

    # Relationships
    period = relationship("Period", back_populates="events")
    persons = relationship("EventPerson", backref="event")
    locations = relationship("EventLocation", backref="event")
    segments = relationship("ChainSegment", back_populates="event")
    mentions = relationship("TextMention", back_populates="event")

    # Self-referential relationships for causality
    caused_by_id = Column(Integer, ForeignKey("events.id"), nullable=True)
    caused_by = relationship("Event", remote_side=[id], backref="caused_events")

    def __repr__(self):
        return f"<Event(id={self.id}, name='{self.name[:50]}...', {self.date_start})>"

    def duration_years(self) -> int:
        """Get duration in years."""
        if self.date_end is None:
            return 0
        return self.date_end - self.date_start
