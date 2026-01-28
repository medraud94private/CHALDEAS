"""Source schemas."""
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class SourceBase(BaseModel):
    name: str
    type: str  # primary, secondary, digital_archive, gutenberg, wikipedia
    url: Optional[str] = None
    author: Optional[str] = None
    archive_type: Optional[str] = None
    reliability: Optional[int] = 3


class Source(SourceBase):
    id: int
    page_reference: Optional[str] = None
    quote: Optional[str] = None

    class Config:
        from_attributes = True


class SourceDetail(SourceBase):
    """Full source details for book page."""
    id: int
    title: Optional[str] = None
    description: Optional[str] = None
    publication_year: Optional[int] = None
    original_year: Optional[int] = None
    language: Optional[str] = None
    document_id: Optional[str] = None
    mention_count: int = 0
    person_count: int = 0
    location_count: int = 0
    event_count: int = 0

    class Config:
        from_attributes = True


class SourceSummary(BaseModel):
    """Source summary for list view."""
    id: int
    name: str
    title: Optional[str] = None
    type: str
    author: Optional[str] = None
    mention_count: int = 0
    person_count: int = 0

    class Config:
        from_attributes = True


class SourceList(BaseModel):
    """Paginated list of sources."""
    items: List[SourceSummary]
    total: int


class MentionContext(BaseModel):
    """A single mention context."""
    mention_text: str
    context_text: Optional[str] = None
    confidence: float = 1.0
    chunk_index: Optional[int] = None


class SourceWithMentions(SourceSummary):
    """Source with mention details for person page."""
    mentions: List[MentionContext] = []


class PersonSourceList(BaseModel):
    """Sources that mention a person."""
    person_id: int
    sources: List[SourceWithMentions]
    total: int


class SourcePersonSummary(BaseModel):
    """Person summary for source page."""
    id: int
    name: str
    name_ko: Optional[str] = None
    birth_year: Optional[int] = None
    death_year: Optional[int] = None
    mention_count: int = 0
    wikidata_id: Optional[str] = None


class SourcePersonList(BaseModel):
    """Persons mentioned in a source."""
    source_id: int
    persons: List[SourcePersonSummary]
    total: int
