"""
Source model.

Represents references and sources for historical data.
Used by LAPLACE for explanation and attribution.

Supported archives:
- Perseus Digital Library (Greek/Roman classics)
- Chinese Text Project (Chinese classics)
- Internet Classics Archive
- Project Gutenberg
- The Latin Library
- BIBLIOTHECA AUGUSTANA
- British Library (V1)
- Open Library (V1)
- Wikidata (V1)
- DBpedia (V1)

V1 Extension:
- document_id: Original file identifier from batch download
- document_path: File path in data/raw/
- original_year: When the original text was written
- title: Full document title
- language: Document language
"""
from sqlalchemy import Column, Integer, String, Text, CheckConstraint
from sqlalchemy.orm import relationship

from app.models.base import Base, TimestampMixin


class Source(Base, TimestampMixin):
    __tablename__ = "sources"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    type = Column(String(50), nullable=False)  # primary, secondary, digital_archive

    # Reference details
    url = Column(String(500))
    author = Column(String(255))
    publication_year = Column(Integer)
    description = Column(Text)

    # Archive identification
    archive_type = Column(
        String(50),
        index=True
    )  # perseus, ctext, gutenberg, latin_library, augustana, british_library, open_library, wikidata, dbpedia

    # V1: Document tracking for NER batch processing
    document_id = Column(String(255), index=True)  # Original file ID from batch download
    document_path = Column(String(500))  # File path in data/raw/
    title = Column(String(500))  # Full document title
    original_year = Column(Integer)  # When the original text was written (BCE as negative)
    language = Column(String(10))  # en, la, gr, zh, etc.

    # V1: Extended archive types
    # british_library, open_library, wikidata, dbpedia, pleiades, pantheon,
    # sacred_texts, avalon, fordham, theoi, world_history, stanford_enc, atlas_academy

    # Reliability score (1-5) for LAPLACE weighting
    reliability = Column(
        Integer,
        CheckConstraint("reliability >= 1 AND reliability <= 5"),
        default=3
    )

    # Relationships
    events = relationship(
        "Event",
        secondary="event_sources",
        back_populates="sources"
    )
    persons = relationship(
        "Person",
        secondary="person_sources",
        back_populates="sources"
    )

    def __repr__(self):
        return f"<Source(id={self.id}, name='{self.name}')>"

    @property
    def archive_url(self) -> str | None:
        """Generate URL for known archives."""
        if not self.archive_type:
            return self.url

        archive_bases = {
            "perseus": "https://www.perseus.tufts.edu/hopper/text?doc=",
            "ctext": "https://ctext.org/",
            "gutenberg": "https://www.gutenberg.org/ebooks/",
            "latin_library": "https://thelatinlibrary.com/",
            "augustana": "https://www.hs-augsburg.de/~harsch/augustana.html",
            "internet_classics": "http://classics.mit.edu/",
        }

        base = archive_bases.get(self.archive_type)
        if base and self.url:
            return f"{base}{self.url}"
        return self.url
