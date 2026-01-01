"""
Person Model for PoC
Represents historical figures
"""
from sqlalchemy import Column, Integer, String, Text, ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base, TimestampMixin


class Person(Base, TimestampMixin):
    """Historical person/figure."""
    __tablename__ = "persons"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False, index=True)
    name_ko = Column(String(200))

    # Life span (BCE as negative)
    birth_year = Column(Integer)
    death_year = Column(Integer)
    birth_place = Column(String(200))
    death_place = Column(String(200))

    # Classification
    occupation = Column(String(200))
    nationality = Column(String(100))

    # Description
    description = Column(Text)
    description_ko = Column(Text)

    # Relationships
    events = relationship("EventPerson", back_populates="person")
    chains = relationship("HistoricalChain", back_populates="person")
    mentions = relationship("TextMention", back_populates="person")

    def __repr__(self):
        return f"<Person(id={self.id}, name='{self.name}')>"

    def was_alive_in(self, year: int) -> bool:
        """Check if person was alive in a given year."""
        if self.birth_year is None:
            return False
        if self.death_year is None:
            return year >= self.birth_year
        return self.birth_year <= year <= self.death_year


class EventPerson(Base):
    """Association table for Event-Person many-to-many relationship."""
    __tablename__ = "event_persons"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(Integer, ForeignKey("events.id"), index=True, nullable=False)
    person_id = Column(Integer, ForeignKey("persons.id"), index=True, nullable=False)
    role = Column(String(100))  # participant, leader, victim, etc.
    description = Column(Text)

    # Relationships
    person = relationship("Person", back_populates="events")
