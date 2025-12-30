"""Person schemas."""
from pydantic import BaseModel
from typing import Optional

from app.schemas.category import Category
from app.schemas.location import Location
from app.schemas.source import Source


class PersonBase(BaseModel):
    name: str
    name_ko: Optional[str] = None
    birth_year: Optional[int] = None
    death_year: Optional[int] = None
    lifespan_display: str


class Person(PersonBase):
    """Person for list view."""
    id: int
    category: Optional[Category] = None
    birthplace: Optional[Location] = None

    class Config:
        from_attributes = True


class PersonDetail(Person):
    """Full person details for wiki panel."""
    slug: str
    name_original: Optional[str] = None
    biography: Optional[str] = None
    biography_ko: Optional[str] = None
    birth_date_precision: str = "year"
    death_date_precision: str = "year"
    deathplace: Optional[Location] = None
    sources: list[Source] = []
    image_url: Optional[str] = None
    wikipedia_url: Optional[str] = None


class PersonList(BaseModel):
    items: list[Person]
    total: int
