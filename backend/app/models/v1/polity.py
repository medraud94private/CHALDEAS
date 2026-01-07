"""
Polity model.

Represents political entities (empires, kingdoms, republics, dynasties, etc.)
that existed in history. Supports temporal validity and succession relationships.

Theoretical Basis:
- CIDOC-CRM: E74 Group (political entities as organized groups)
- Historical GIS: Temporal validity for changing political boundaries
"""
from sqlalchemy import Column, Integer, String, Text, ForeignKey, CheckConstraint, Float
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector

from app.models.base import Base, TimestampMixin


class Polity(Base, TimestampMixin):
    __tablename__ = "polities"

    id = Column(Integer, primary_key=True, index=True)

    # Identity
    name = Column(String(255), nullable=False, index=True)
    name_ko = Column(String(255))
    name_original = Column(String(255))  # Original language name
    slug = Column(String(255), unique=True, nullable=False, index=True)

    # Classification
    polity_type = Column(
        String(50),
        CheckConstraint(
            "polity_type IN ('empire', 'kingdom', 'republic', 'dynasty', "
            "'city_state', 'tribe', 'confederation', 'caliphate', 'shogunate', 'other')"
        ),
        nullable=True,
        index=True
    )

    # Temporal existence (BCE as negative integers)
    start_year = Column(Integer, index=True)
    start_year_precision = Column(String(20), default="year")  # exact, year, decade, century
    end_year = Column(Integer)  # NULL if still exists
    end_year_precision = Column(String(20), default="year")

    # Geography
    capital_id = Column(Integer, ForeignKey("locations.id"), nullable=True)
    region = Column(String(100))  # Europe, Middle East, East Asia, etc.

    # Succession relationships
    predecessor_id = Column(Integer, ForeignKey("polities.id"), nullable=True)
    successor_id = Column(Integer, ForeignKey("polities.id"), nullable=True)
    parent_polity_id = Column(Integer, ForeignKey("polities.id"), nullable=True)  # For vassals/tributaries

    # Certainty (same as Event)
    certainty = Column(
        String(20),
        CheckConstraint(
            "certainty IN ('fact', 'probable', 'legendary', 'mythological')"
        ),
        default="fact",
        nullable=True
    )

    # Content
    description = Column(Text)
    description_ko = Column(Text)

    # Vector embedding for semantic search (pgvector)
    embedding = Column(Vector(1536), nullable=True)

    # Statistics
    mention_count = Column(Integer, default=0)
    avg_confidence = Column(Float, default=0.0)

    # Media
    image_url = Column(String(500))
    wikipedia_url = Column(String(500))
    wikidata_id = Column(String(50))  # Q-number for entity linking

    # Relationships
    capital = relationship("Location", foreign_keys=[capital_id])
    predecessor = relationship(
        "Polity",
        remote_side=[id],
        foreign_keys=[predecessor_id],
        backref="successors_of_predecessor"
    )
    successor = relationship(
        "Polity",
        remote_side=[id],
        foreign_keys=[successor_id],
        backref="predecessors_of_successor"
    )
    parent_polity = relationship(
        "Polity",
        remote_side=[id],
        foreign_keys=[parent_polity_id],
        backref="vassal_polities"
    )

    def __repr__(self):
        return f"<Polity(id={self.id}, name='{self.name}', type='{self.polity_type}')>"

    @property
    def lifespan_display(self) -> str:
        """Human-readable lifespan string."""
        if not self.start_year and not self.end_year:
            return "Unknown"

        def format_year(year: int) -> str:
            if year is None:
                return "?"
            era = "BCE" if year < 0 else "CE"
            return f"{abs(year)} {era}"

        start = format_year(self.start_year) if self.start_year else "?"
        end = format_year(self.end_year) if self.end_year else "present"

        # Simplify if same era
        if self.start_year and self.end_year:
            if (self.start_year < 0) == (self.end_year < 0):
                era = "BCE" if self.start_year < 0 else "CE"
                return f"{abs(self.start_year)}-{abs(self.end_year)} {era}"

        return f"{start} - {end}"

    def was_active_in(self, year: int) -> bool:
        """Check if polity existed in a given year."""
        if self.start_year is not None and year < self.start_year:
            return False
        if self.end_year is not None and year > self.end_year:
            return False
        return True
