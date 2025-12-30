"""
Event model.

The core data type in CHALDEAS, representing historical occurrences
in time and space. Supports BCE dates using negative integers.
"""
from sqlalchemy import Column, Integer, String, Text, ForeignKey, CheckConstraint
from sqlalchemy.orm import relationship

from app.models.base import Base, TimestampMixin


class Event(Base, TimestampMixin):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(500), nullable=False)
    title_ko = Column(String(500))
    slug = Column(String(500), unique=True, nullable=False, index=True)

    # Content
    description = Column(Text)
    description_ko = Column(Text)

    # Temporal data (BCE support: negative numbers)
    # -490 = 490 BCE, 476 = 476 CE
    date_start = Column(Integer, nullable=False, index=True)
    date_start_month = Column(Integer)  # 1-12, nullable
    date_start_day = Column(Integer)    # 1-31, nullable
    date_end = Column(Integer)          # For events spanning time
    date_end_month = Column(Integer)
    date_end_day = Column(Integer)
    date_precision = Column(String(20), default="year")  # exact, year, decade, century

    # Importance (1-5, higher = more significant)
    importance = Column(
        Integer,
        CheckConstraint("importance >= 1 AND importance <= 5"),
        default=3,
        index=True
    )

    # Foreign keys
    category_id = Column(Integer, ForeignKey("categories.id"), index=True)
    primary_location_id = Column(Integer, ForeignKey("locations.id"))

    # Source reliability for LAPLACE
    source_reliability = Column(Integer, default=3)

    # Media
    image_url = Column(String(500))
    wikipedia_url = Column(String(500))

    # Relationships
    category = relationship("Category", back_populates="events")
    primary_location = relationship(
        "Location",
        back_populates="primary_events",
        foreign_keys=[primary_location_id]
    )
    locations = relationship(
        "Location",
        secondary="event_locations",
        back_populates="events"
    )
    persons = relationship(
        "Person",
        secondary="event_persons",
        back_populates="events"
    )
    sources = relationship(
        "Source",
        secondary="event_sources",
        back_populates="events"
    )

    def __repr__(self):
        return f"<Event(id={self.id}, title='{self.title}', year={self.date_start})>"

    @property
    def date_display(self) -> str:
        """Human-readable date string."""
        year = abs(self.date_start)
        era = "BCE" if self.date_start < 0 else "CE"

        if self.date_precision == "century":
            century = (year // 100) + 1
            return f"{century}th century {era}"
        elif self.date_precision == "decade":
            decade = (year // 10) * 10
            return f"{decade}s {era}"
        elif self.date_precision == "exact" and self.date_start_month:
            if self.date_start_day:
                return f"{year}-{self.date_start_month:02d}-{self.date_start_day:02d} {era}"
            return f"{year}-{self.date_start_month:02d} {era}"

        return f"{year} {era}"

    @property
    def is_bce(self) -> bool:
        """Check if event occurred in BCE."""
        return self.date_start < 0
