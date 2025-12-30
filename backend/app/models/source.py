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
    archive_type = Column(String(50))  # perseus, ctext, gutenberg, latin_library, augustana

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
