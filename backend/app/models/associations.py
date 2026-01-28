"""
Association tables for many-to-many relationships.

V1 Extension:
- event_relationships: Added certainty, evidence_type for Causal Chain support
- person_relationships: Added strength, valid_from/until, confidence for Prosopography
- polity_relationships: New table for political succession and relationships
"""
from sqlalchemy import Table, Column, Integer, String, Text, ForeignKey, Float
from sqlalchemy.dialects.postgresql import JSONB

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
    Column("chunk_references", JSONB, default=[]),  # All chunk positions where entity appears
)

# Person <-> Source
person_sources = Table(
    "person_sources",
    Base.metadata,
    Column("person_id", Integer, ForeignKey("persons.id", ondelete="CASCADE"), primary_key=True),
    Column("source_id", Integer, ForeignKey("sources.id", ondelete="CASCADE"), primary_key=True),
    Column("page_reference", String(100)),
    Column("chunk_references", JSONB, default=[]),  # All chunk positions where entity appears
)

# Person <-> Person (relationships) - Enhanced for Prosopography
person_relationships = Table(
    "person_relationships",
    Base.metadata,
    Column("person_id", Integer, ForeignKey("persons.id", ondelete="CASCADE"), primary_key=True),
    Column("related_person_id", Integer, ForeignKey("persons.id", ondelete="CASCADE"), primary_key=True),
    Column("relationship_type", String(50)),  # teacher, student, rival, ally, family, mentor, patron, etc.
    Column("description", Text),
    # V1: Prosopography enhancements
    Column("strength", Integer, default=3),  # 1-5: relationship strength
    Column("valid_from", Integer),  # When relationship started (BCE as negative)
    Column("valid_until", Integer),  # When relationship ended
    Column("confidence", Float, default=1.0),  # Extraction confidence
    Column("is_bidirectional", Integer, default=0),  # 1 if symmetric (e.g., siblings)
)

# Event <-> Event (relationships) - Enhanced for Causal Chain
event_relationships = Table(
    "event_relationships",
    Base.metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("from_event_id", Integer, ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True),
    Column("to_event_id", Integer, ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True),
    Column("relationship_type", String(50), nullable=False),  # causes, follows, part_of, related_to, opposes, enables, prevents
    Column("strength", Integer, default=3),  # 1-5: 관계 강도
    Column("description", Text),
    Column("source_query", String(500)),  # 이 관계를 발견한 검색 쿼리
    # V1: Causal Chain enhancements
    Column("certainty", String(20), default="probable"),  # certain, probable, possible, disputed
    Column("evidence_type", String(30)),  # primary_source, scholarly_consensus, inference, tradition
    Column("scholarly_citation", Text),  # Academic source for causal claim
    Column("confidence", Float, default=1.0),  # Extraction confidence
)

# V1: Polity <-> Polity (relationships)
polity_relationships = Table(
    "polity_relationships",
    Base.metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("polity_id", Integer, ForeignKey("polities.id", ondelete="CASCADE"), nullable=False, index=True),
    Column("related_polity_id", Integer, ForeignKey("polities.id", ondelete="CASCADE"), nullable=False, index=True),
    Column("relationship_type", String(50), nullable=False),  # successor, predecessor, vassal, suzerain, ally, enemy, trade_partner
    Column("valid_from", Integer),  # When relationship started
    Column("valid_until", Integer),  # When relationship ended
    Column("strength", Integer, default=3),
    Column("description", Text),
)

# V1: Person <-> Polity (affiliation over time)
person_polities = Table(
    "person_polities",
    Base.metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("person_id", Integer, ForeignKey("persons.id", ondelete="CASCADE"), nullable=False, index=True),
    Column("polity_id", Integer, ForeignKey("polities.id", ondelete="CASCADE"), nullable=False, index=True),
    Column("role", String(100)),  # ruler, general, minister, citizen, etc.
    Column("valid_from", Integer),  # When affiliation started
    Column("valid_until", Integer),  # When affiliation ended
    Column("is_primary", Integer, default=0),  # 1 if main affiliation
)

# Person <-> Location (Wikipedia link based)
person_locations = Table(
    "person_locations",
    Base.metadata,
    Column("person_id", Integer, ForeignKey("persons.id", ondelete="CASCADE"), primary_key=True),
    Column("location_id", Integer, ForeignKey("locations.id", ondelete="CASCADE"), primary_key=True),
    Column("role", String(50), default="mentioned"),  # mentioned, birthplace, deathplace, residence, visited
    Column("confidence", Float, default=0.5),
)

# Location <-> Location (relationships)
location_relationships = Table(
    "location_relationships",
    Base.metadata,
    Column("location_id", Integer, ForeignKey("locations.id", ondelete="CASCADE"), primary_key=True),
    Column("related_location_id", Integer, ForeignKey("locations.id", ondelete="CASCADE"), primary_key=True),
    Column("relationship_type", String(50), default="related_to"),  # related_to, part_of, near, contains
    Column("strength", Integer, default=2),
    Column("confidence", Float, default=0.5),
)

# Location <-> Source
location_sources = Table(
    "location_sources",
    Base.metadata,
    Column("location_id", Integer, ForeignKey("locations.id", ondelete="CASCADE"), primary_key=True),
    Column("source_id", Integer, ForeignKey("sources.id", ondelete="CASCADE"), primary_key=True),
    Column("page_reference", String(100)),
    Column("chunk_references", JSONB, default=[]),  # All chunk positions where entity appears
)
