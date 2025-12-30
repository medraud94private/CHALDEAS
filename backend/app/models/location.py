"""
Location model.

Represents geographical locations where historical events occurred.
Supports both ancient and modern naming.
"""
from sqlalchemy import Column, Integer, String, Numeric, Text
from sqlalchemy.orm import relationship

from app.models.base import Base, TimestampMixin


class Location(Base, TimestampMixin):
    __tablename__ = "locations"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    name_ko = Column(String(255))
    name_original = Column(String(255))  # Original language name

    # Coordinates
    latitude = Column(Numeric(10, 8), nullable=False)
    longitude = Column(Numeric(11, 8), nullable=False)

    # Classification
    type = Column(String(50), nullable=False)  # city, region, landmark, battle_site
    modern_name = Column(String(255))  # Modern equivalent name
    country = Column(String(100))
    region = Column(String(100))

    # Description
    description = Column(Text)
    description_ko = Column(Text)

    # Relationships
    events = relationship(
        "Event",
        secondary="event_locations",
        back_populates="locations"
    )
    primary_events = relationship(
        "Event",
        back_populates="primary_location",
        foreign_keys="Event.primary_location_id"
    )
    birthplace_of = relationship(
        "Person",
        back_populates="birthplace",
        foreign_keys="Person.birthplace_id"
    )

    def __repr__(self):
        return f"<Location(id={self.id}, name='{self.name}')>"

    @property
    def coords(self) -> tuple[float, float]:
        """Return (latitude, longitude) tuple."""
        return (float(self.latitude), float(self.longitude))
