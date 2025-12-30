"""Location schemas."""
from pydantic import BaseModel
from typing import Optional


class LocationBase(BaseModel):
    name: str
    name_ko: Optional[str] = None
    latitude: float
    longitude: float
    type: str
    modern_name: Optional[str] = None


class Location(LocationBase):
    id: int

    class Config:
        from_attributes = True


class LocationDetail(Location):
    name_original: Optional[str] = None
    country: Optional[str] = None
    region: Optional[str] = None
    description: Optional[str] = None
    description_ko: Optional[str] = None


class LocationList(BaseModel):
    items: list[Location]
    total: int
