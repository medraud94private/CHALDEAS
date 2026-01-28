"""
Person model.

Represents historical figures with their biographical data.

V1 Extension:
- canonical_id: Link to canonical entity for alias deduplication
- role, era: NER extraction fields
- floruit_start/end: For unknown birth/death dates (fl. notation)
- certainty: Same as Event (fact, probable, legendary, mythological)
- embedding: Vector embedding for semantic search (pgvector)
- primary_polity_id: Main political affiliation
- mention_count, avg_confidence: Statistics from NER extraction
"""
from sqlalchemy import Column, Integer, String, Text, ForeignKey, Float, CheckConstraint
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector

from app.models.base import Base, TimestampMixin


class Person(Base, TimestampMixin):
    __tablename__ = "persons"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    name_ko = Column(String(255))
    name_original = Column(String(255))  # Original language name
    slug = Column(String(255), unique=True, nullable=False, index=True)

    # Birth/Death (BCE support: negative numbers)
    birth_year = Column(Integer, index=True)
    birth_month = Column(Integer)
    birth_day = Column(Integer)
    death_year = Column(Integer)
    death_month = Column(Integer)
    death_day = Column(Integer)
    birth_date_precision = Column(String(20), default="year")
    death_date_precision = Column(String(20), default="year")

    # Biography
    biography = Column(Text)
    biography_ko = Column(Text)
    biography_ja = Column(Text)  # Japanese biography

    # Japanese name
    name_ja = Column(String(255))

    # Source tracking for biography
    biography_source = Column(String(50))  # wikipedia_en, wikipedia_ko, wikipedia_ja, llm, manual
    biography_source_url = Column(String(500))

    # Foreign keys
    category_id = Column(Integer, ForeignKey("categories.id"), index=True)
    birthplace_id = Column(Integer, ForeignKey("locations.id"))
    deathplace_id = Column(Integer, ForeignKey("locations.id"))

    # Media
    image_url = Column(String(500))
    wikipedia_url = Column(String(500))
    wikidata_id = Column(String(50))  # V1: Q-number for entity linking

    # V1: Alias deduplication (link to canonical entity)
    canonical_id = Column(Integer, ForeignKey("persons.id"), nullable=True, index=True)

    # V1: NER extraction fields
    role = Column(String(255))  # king, philosopher, general, etc.
    era = Column(String(100))   # Classical Antiquity, Medieval, etc.

    # V1: Floruit dates (for unknown birth/death - "fl." notation)
    floruit_start = Column(Integer)
    floruit_end = Column(Integer)

    # V1: Certainty level (same as Event)
    certainty = Column(
        String(20),
        CheckConstraint(
            "certainty IN ('fact', 'probable', 'legendary', 'mythological')"
        ),
        default="fact",
        nullable=True  # V0 compatibility
    )

    # V1: Vector embedding for semantic search (pgvector)
    embedding = Column(Vector(1536), nullable=True)

    # V1: Political affiliation
    primary_polity_id = Column(Integer, ForeignKey("polities.id"), nullable=True)

    # V1: Statistics from NER extraction
    mention_count = Column(Integer, default=0)
    avg_confidence = Column(Float, default=0.0)

    # Connection count for filtering orphans
    connection_count = Column(Integer, default=0, index=True)

    # Relationships
    category = relationship("Category", back_populates="persons")
    birthplace = relationship(
        "Location",
        back_populates="birthplace_of",
        foreign_keys=[birthplace_id]
    )
    deathplace = relationship("Location", foreign_keys=[deathplace_id])
    events = relationship(
        "Event",
        secondary="event_persons",
        back_populates="persons"
    )
    sources = relationship(
        "Source",
        secondary="person_sources",
        back_populates="persons"
    )

    # V1: Canonical entity relationship (for alias deduplication)
    canonical = relationship(
        "Person",
        remote_side=[id],
        foreign_keys=[canonical_id],
        backref="aliases"
    )

    # V1: Political affiliation
    primary_polity = relationship("Polity", foreign_keys=[primary_polity_id])

    def __repr__(self):
        return f"<Person(id={self.id}, name='{self.name}')>"

    @property
    def lifespan_display(self) -> str:
        """Human-readable lifespan string."""
        if not self.birth_year and not self.death_year:
            return "Unknown"

        def format_year(year: int) -> str:
            if year is None:
                return "?"
            era = "BCE" if year < 0 else "CE"
            return f"{abs(year)} {era}"

        birth = format_year(self.birth_year) if self.birth_year else "?"
        death = format_year(self.death_year) if self.death_year else "?"

        # Simplify if same era
        if self.birth_year and self.death_year:
            if (self.birth_year < 0) == (self.death_year < 0):
                era = "BCE" if self.birth_year < 0 else "CE"
                return f"{abs(self.birth_year)}-{abs(self.death_year)} {era}"

        return f"{birth} - {death}"

    def was_alive_in(self, year: int) -> bool:
        """Check if person was alive in a given year."""
        if self.birth_year is None:
            return False
        if self.death_year is None:
            # Assume alive for some reasonable period
            return self.birth_year <= year <= self.birth_year + 80
        return self.birth_year <= year <= self.death_year
