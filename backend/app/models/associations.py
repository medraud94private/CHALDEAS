"""
Association tables for many-to-many relationships.
"""
from sqlalchemy import Table, Column, Integer, String, Text, ForeignKey

from app.models.base import Base

# Event <-> Location (with role)
event_locations = Table(
    "event_locations",
    Base.metadata,
    Column("event_id", Integer, ForeignKey("events.id", ondelete="CASCADE"), primary_key=True),
    Column("location_id", Integer, ForeignKey("locations.id", ondelete="CASCADE"), primary_key=True),
    Column("role", String(50), primary_key=True, default="location"),  # location, origin, destination
)

# Event <-> Person (with role)
event_persons = Table(
    "event_persons",
    Base.metadata,
    Column("event_id", Integer, ForeignKey("events.id", ondelete="CASCADE"), primary_key=True),
    Column("person_id", Integer, ForeignKey("persons.id", ondelete="CASCADE"), primary_key=True),
    Column("role", String(100)),  # participant, leader, victim, etc.
    Column("description", Text),
)

# Event <-> Source (with reference)
event_sources = Table(
    "event_sources",
    Base.metadata,
    Column("event_id", Integer, ForeignKey("events.id", ondelete="CASCADE"), primary_key=True),
    Column("source_id", Integer, ForeignKey("sources.id", ondelete="CASCADE"), primary_key=True),
    Column("page_reference", String(100)),
    Column("quote", Text),
)

# Person <-> Source
person_sources = Table(
    "person_sources",
    Base.metadata,
    Column("person_id", Integer, ForeignKey("persons.id", ondelete="CASCADE"), primary_key=True),
    Column("source_id", Integer, ForeignKey("sources.id", ondelete="CASCADE"), primary_key=True),
    Column("page_reference", String(100)),
)

# Person <-> Person (relationships)
person_relationships = Table(
    "person_relationships",
    Base.metadata,
    Column("person_id", Integer, ForeignKey("persons.id", ondelete="CASCADE"), primary_key=True),
    Column("related_person_id", Integer, ForeignKey("persons.id", ondelete="CASCADE"), primary_key=True),
    Column("relationship_type", String(50)),  # teacher, student, rival, ally, family
    Column("description", Text),
)
