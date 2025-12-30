"""Source schemas."""
from pydantic import BaseModel
from typing import Optional


class SourceBase(BaseModel):
    name: str
    type: str  # primary, secondary, digital_archive
    url: Optional[str] = None
    author: Optional[str] = None
    archive_type: Optional[str] = None
    reliability: int = 3


class Source(SourceBase):
    id: int
    page_reference: Optional[str] = None
    quote: Optional[str] = None

    class Config:
        from_attributes = True
