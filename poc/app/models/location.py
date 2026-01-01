"""
Location Model for PoC
Represents places with dual hierarchy (modern + historical)
"""
from sqlalchemy import Column, Integer, String, Text, Float, ForeignKey, CheckConstraint
from sqlalchemy.orm import relationship
from typing import List

from app.database import Base, TimestampMixin


class Location(Base, TimestampMixin):
    """Historical/geographical location with dual hierarchy."""
    __tablename__ = "locations"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False, index=True)
    name_ko = Column(String(200))

    # Coordinates
    latitude = Column(Float)
    longitude = Column(Float)

    # Location type
    location_type = Column(String(50))  # city, country, region, etc.

    # Hierarchy level
    hierarchy_level = Column(
        String(30),
        CheckConstraint("hierarchy_level IN ('site', 'city', 'region', 'country', 'continent', 'civilization_area')")
    )

    # Dual hierarchy: modern administrative vs historical political
    modern_parent_id = Column(Integer, ForeignKey("locations.id"), nullable=True)
    historical_parent_id = Column(Integer, ForeignKey("locations.id"), nullable=True)

    # Temporal validity (for historical entities)
    valid_from = Column(Integer)  # BCE as negative
    valid_until = Column(Integer)

    # Description
    description = Column(Text)
    description_ko = Column(Text)

    # Relationships
    modern_parent = relationship(
        "Location",
        remote_side=[id],
        foreign_keys=[modern_parent_id],
        backref="modern_children"
    )
    historical_parent = relationship(
        "Location",
        remote_side=[id],
        foreign_keys=[historical_parent_id],
        backref="historical_children"
    )
    events = relationship("EventLocation", back_populates="location")
    chains = relationship("HistoricalChain", back_populates="location")
    mentions = relationship("TextMention", back_populates="location")

    def __repr__(self):
        return f"<Location(id={self.id}, name='{self.name}')>"

    def was_valid_in(self, year: int) -> bool:
        """Check if this location entity was valid in a given year."""
        if self.valid_from is None and self.valid_until is None:
            return True  # Always valid if no temporal bounds
        if self.valid_from is not None and year < self.valid_from:
            return False
        if self.valid_until is not None and year > self.valid_until:
            return False
        return True

    def get_modern_ancestors(self) -> List["Location"]:
        """Get all ancestors in modern hierarchy."""
        ancestors = []
        current = self.modern_parent
        while current:
            ancestors.append(current)
            current = current.modern_parent
        return ancestors

    def get_historical_ancestors(self) -> List["Location"]:
        """Get all ancestors in historical hierarchy."""
        ancestors = []
        current = self.historical_parent
        while current:
            ancestors.append(current)
            current = current.historical_parent
        return ancestors


class EventLocation(Base):
    """Association table for Event-Location many-to-many relationship."""
    __tablename__ = "event_locations"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(Integer, ForeignKey("events.id"), index=True, nullable=False)
    location_id = Column(Integer, ForeignKey("locations.id"), index=True, nullable=False)
    role = Column(String(100))  # location, origin, destination, etc.
    description = Column(Text)

    # Relationships
    location = relationship("Location", back_populates="events")
