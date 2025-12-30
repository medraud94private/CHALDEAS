"""
Person model.

Represents historical figures with their biographical data.
"""
from sqlalchemy import Column, Integer, String, Text, ForeignKey
from sqlalchemy.orm import relationship

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

    # Foreign keys
    category_id = Column(Integer, ForeignKey("categories.id"), index=True)
    birthplace_id = Column(Integer, ForeignKey("locations.id"))
    deathplace_id = Column(Integer, ForeignKey("locations.id"))

    # Media
    image_url = Column(String(500))
    wikipedia_url = Column(String(500))

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
