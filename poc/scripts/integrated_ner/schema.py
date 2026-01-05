"""
Integrated NER Pipeline - Pydantic Schemas
Structured Output을 위한 스키마 정의
"""
from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum


class YearPrecision(str, Enum):
    EXACT = "exact"          # 정확한 년도: "331 BCE"
    CIRCA = "circa"          # 대략: "around 330 BCE"
    DECADE = "decade"        # 10년 단위: "330s BCE"
    CENTURY = "century"      # 세기: "4th century BCE"
    PERIOD = "period"        # 시대: "Hellenistic period"
    UNKNOWN = "unknown"      # 불명


class LocationType(str, Enum):
    CITY = "city"
    REGION = "region"
    COUNTRY = "country"
    CONTINENT = "continent"
    LANDMARK = "landmark"
    BODY_OF_WATER = "body_of_water"
    OTHER = "other"


class PolityType(str, Enum):
    EMPIRE = "empire"
    KINGDOM = "kingdom"
    REPUBLIC = "republic"
    DYNASTY = "dynasty"
    CITY_STATE = "city_state"
    TRIBE = "tribe"
    OTHER = "other"


# === 추출 엔티티 ===

class ExtractedPerson(BaseModel):
    """역사적 인물"""
    name: str = Field(description="Full name of the person")
    role: Optional[str] = Field(None, description="Role or occupation: king, philosopher, general")
    birth_year: Optional[int] = Field(None, description="Birth year (negative for BCE)")
    death_year: Optional[int] = Field(None, description="Death year (negative for BCE)")
    era: Optional[str] = Field(None, description="Historical era: Classical Antiquity, Medieval")
    nationality: Optional[str] = Field(None, description="Nationality or origin")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score")


class ExtractedLocation(BaseModel):
    """역사적 장소"""
    name: str = Field(description="Name of the location")
    location_type: Optional[LocationType] = Field(None, description="Type of location")
    modern_name: Optional[str] = Field(None, description="Modern name if different")
    parent_region: Optional[str] = Field(None, description="Parent region or country")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score")


class ExtractedPolity(BaseModel):
    """국가/제국/왕조"""
    name: str = Field(description="Name: Roman Empire, Qing Dynasty")
    polity_type: Optional[PolityType] = Field(None, description="Type of polity")
    start_year: Optional[int] = Field(None, description="Founding year (negative for BCE)")
    end_year: Optional[int] = Field(None, description="End year (negative for BCE)")
    capital: Optional[str] = Field(None, description="Capital city")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score")


class ExtractedPeriod(BaseModel):
    """역사적 시대/시기"""
    name: str = Field(description="Name: Renaissance, Victorian Era")
    start_year: Optional[int] = Field(None, description="Start year (negative for BCE)")
    end_year: Optional[int] = Field(None, description="End year (negative for BCE)")
    year_precision: YearPrecision = Field(default=YearPrecision.UNKNOWN)
    region: Optional[str] = Field(None, description="Geographic scope: Europe, China")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score")


class ExtractedEvent(BaseModel):
    """역사적 사건"""
    name: str = Field(description="Event name: Battle of Gaugamela")
    description: Optional[str] = Field(None, description="Brief description")
    year: Optional[int] = Field(None, description="Year (negative for BCE)")
    year_precision: YearPrecision = Field(default=YearPrecision.UNKNOWN)
    persons_involved: List[str] = Field(default_factory=list, description="Names of persons involved")
    locations_involved: List[str] = Field(default_factory=list, description="Names of locations")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score")


# === 문서 전체 추출 결과 ===

class DocumentExtraction(BaseModel):
    """문서에서 추출한 모든 엔티티"""
    persons: List[ExtractedPerson] = Field(default_factory=list)
    locations: List[ExtractedLocation] = Field(default_factory=list)
    polities: List[ExtractedPolity] = Field(default_factory=list)
    periods: List[ExtractedPeriod] = Field(default_factory=list)
    events: List[ExtractedEvent] = Field(default_factory=list)

    # 문서 메타데이터
    document_era: Optional[str] = Field(None, description="Overall era of the document")
    document_time_range: Optional[str] = Field(None, description="Time range covered: '500 BCE - 300 BCE'")
    primary_region: Optional[str] = Field(None, description="Primary geographic focus")
