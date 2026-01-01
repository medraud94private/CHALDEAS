"""
Period Model for PoC
Represents historical eras with Braudel's temporal scales
"""
from sqlalchemy import Column, Integer, String, Text, Boolean, ForeignKey, CheckConstraint
from sqlalchemy.orm import relationship

from app.database import Base, TimestampMixin


class Period(Base, TimestampMixin):
    """Historical period/era with temporal scale classification."""
    __tablename__ = "periods"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    name_ko = Column(String(200))
    slug = Column(String(200), unique=True, index=True)

    # Time range (BCE as negative)
    year_start = Column(Integer, nullable=False)
    year_end = Column(Integer)

    # Braudel's temporal scale
    scale = Column(
        String(20),
        CheckConstraint("scale IN ('evenementielle', 'conjuncture', 'longue_duree')"),
        default="conjuncture"
    )

    # Hierarchy
    parent_id = Column(Integer, ForeignKey("periods.id"), nullable=True)

    # Description
    description = Column(Text)
    description_ko = Column(Text)

    # Manual vs AI-generated
    is_manual = Column(Boolean, default=True)

    # Relationships
    parent = relationship("Period", remote_side=[id], backref="children")
    events = relationship("Event", back_populates="period")
    chains = relationship("HistoricalChain", back_populates="period")

    def __repr__(self):
        return f"<Period(id={self.id}, name='{self.name}', {self.year_start}-{self.year_end})>"

    def contains_year(self, year: int) -> bool:
        """Check if a year falls within this period."""
        if self.year_end is None:
            return year >= self.year_start
        return self.year_start <= year <= self.year_end
