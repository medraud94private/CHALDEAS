"""
Location model.

Represents geographical locations where historical events occurred.
Supports both ancient and modern naming.

V1 Extension:
- Dual hierarchy: modern (current administrative) and historical (period-specific)
- Temporal validity: when a historical entity existed
- Hierarchy levels: site, city, region, country, continent, civilization_area
"""
from sqlalchemy import Column, Integer, String, Numeric, Text, ForeignKey, CheckConstraint
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

    # V1: Hierarchy Level
    # site < city < region < country < continent < civilization_area
    hierarchy_level = Column(
        String(30),
        CheckConstraint(
            "hierarchy_level IN ('site', 'city', 'region', 'country', 'continent', 'civilization_area')"
        ),
        nullable=True  # nullable for V0 compatibility
    )

    # V1: Dual Hierarchy
    # Modern hierarchy: Naples → Campania → Italy → Europe
    modern_parent_id = Column(Integer, ForeignKey("locations.id"), nullable=True)
    # Historical hierarchy (time-dependent): Naples → Kingdom of Two Sicilies → Europe (in 1843)
    historical_parent_id = Column(Integer, ForeignKey("locations.id"), nullable=True)

    # V1: Temporal Validity (for historical entities)
    # When did this location exist under this name/political entity?
    valid_from = Column(Integer, nullable=True)  # BCE as negative, e.g., -753 for Rome's founding
    valid_until = Column(Integer, nullable=True)  # null = still exists

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

    # V1: Hierarchy relationships
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

    def __repr__(self):
        return f"<Location(id={self.id}, name='{self.name}')>"

    @property
    def coords(self) -> tuple[float, float]:
        """Return (latitude, longitude) tuple."""
        return (float(self.latitude), float(self.longitude))

    # V1: Helper methods
    def get_modern_ancestors(self) -> list["Location"]:
        """Get all ancestors in modern hierarchy (city → region → country → continent)."""
        ancestors = []
        current = self.modern_parent
        while current:
            ancestors.append(current)
            current = current.modern_parent
        return ancestors

    def get_historical_ancestors(self) -> list["Location"]:
        """Get all ancestors in historical hierarchy."""
        ancestors = []
        current = self.historical_parent
        while current:
            ancestors.append(current)
            current = current.historical_parent
        return ancestors

    def was_valid_in(self, year: int) -> bool:
        """Check if this location entity existed in a given year."""
        if self.valid_from is not None and year < self.valid_from:
            return False
        if self.valid_until is not None and year > self.valid_until:
            return False
        return True
