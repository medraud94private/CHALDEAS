"""
Period model.

Represents historical periods/eras following Braudel's temporal scales:
- evenementielle: Short-term events (days to years)
- conjuncture: Medium-term cycles (decades to centuries)
- longue_duree: Long-term structures (centuries to millennia)

Examples:
- Classical Greece (-500 to -323): conjuncture
- Renaissance (1400 to 1600): conjuncture
- Mediterranean Trade Culture (-3000 to 1500): longue_duree
"""
from sqlalchemy import Column, Integer, String, Text, Boolean, ForeignKey, CheckConstraint
from sqlalchemy.orm import relationship

from app.models.base import Base, TimestampMixin


class Period(Base, TimestampMixin):
    __tablename__ = "periods"

    id = Column(Integer, primary_key=True, index=True)

    # Names (multilingual)
    name = Column(String(200), nullable=False)
    name_ko = Column(String(200))
    slug = Column(String(200), unique=True, index=True)

    # Time range (BCE as negative)
    year_start = Column(Integer, nullable=False)  # -500 = 500 BCE
    year_end = Column(Integer)  # nullable for ongoing periods

    # Braudel's temporal scale
    scale = Column(
        String(20),
        CheckConstraint("scale IN ('evenementielle', 'conjuncture', 'longue_duree')"),
        default="conjuncture"
    )

    # Hierarchy (e.g., "Ancient Greece" → "Classical Period" → "Peloponnesian War")
    parent_id = Column(Integer, ForeignKey("periods.id"))

    # Description
    description = Column(Text)
    description_ko = Column(Text)

    # Metadata
    is_manual = Column(Boolean, default=True)  # True if manually defined, False if AI-generated

    # Relationships
    parent = relationship("Period", remote_side=[id], backref="children")
    events = relationship("Event", back_populates="period", foreign_keys="Event.period_id")

    def __repr__(self):
        return f"<Period(id={self.id}, name='{self.name}', {self.year_start} to {self.year_end})>"

    @property
    def year_display(self) -> str:
        """Human-readable year range."""
        start = f"{abs(self.year_start)} BCE" if self.year_start < 0 else f"{self.year_start} CE"
        if self.year_end is None:
            return f"{start} - present"
        end = f"{abs(self.year_end)} BCE" if self.year_end < 0 else f"{self.year_end} CE"
        return f"{start} - {end}"

    @property
    def duration_years(self) -> int:
        """Duration in years."""
        if self.year_end is None:
            from datetime import datetime
            return datetime.now().year - self.year_start
        return self.year_end - self.year_start
