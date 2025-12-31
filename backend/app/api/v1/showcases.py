"""
Showcase API - Curated content like Singularities, Lostbelts, Historical Articles
Supports multilingual content (EN, KO, JA)
Last updated: 2024-12-31
"""
import json
from pathlib import Path
from typing import List, Optional, Literal
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

router = APIRouter()

# Data directory
DATA_DIR = Path(__file__).parent.parent.parent / "data" / "showcases"


class RelatedServant(BaseModel):
    name: str
    class_: str  # 'class' is reserved in Python
    rarity: int

    class Config:
        populate_by_name = True
        # Allow 'class' from JSON to map to 'class_'

    @classmethod
    def from_dict(cls, data: dict):
        return cls(
            name=data.get("name", ""),
            class_=data.get("class", ""),
            rarity=data.get("rarity", 0)
        )


class Section(BaseModel):
    title: str
    title_ko: Optional[str] = None
    title_ja: Optional[str] = None
    content: str
    content_ko: Optional[str] = None
    content_ja: Optional[str] = None


class ShowcaseItem(BaseModel):
    id: str
    type: Literal["singularity", "lostbelt", "servant", "article"]
    title: str
    title_ko: Optional[str] = None
    title_ja: Optional[str] = None
    subtitle: Optional[str] = None
    subtitle_ko: Optional[str] = None
    subtitle_ja: Optional[str] = None
    chapter: Optional[str] = None
    era: Optional[str] = None
    year: Optional[int] = None
    location: Optional[str] = None
    description: str
    description_ko: Optional[str] = None
    description_ja: Optional[str] = None
    sections: List[Section] = []
    historical_basis: Optional[str] = None
    historical_basis_ko: Optional[str] = None
    historical_basis_ja: Optional[str] = None
    related_servants: List[RelatedServant] = []
    related_event_ids: List[int] = []
    sources: List[str] = []


class ShowcaseListResponse(BaseModel):
    items: List[ShowcaseItem]
    total: int
    category: str


def load_showcase_file(filename: str) -> List[dict]:
    """Load a showcase JSON file."""
    filepath = DATA_DIR / filename
    if not filepath.exists():
        return []
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def parse_showcase_item(data: dict) -> ShowcaseItem:
    """Parse a raw dict into ShowcaseItem, handling 'class' field."""
    servants = [RelatedServant.from_dict(s) for s in data.get("related_servants", [])]
    sections = [Section(**s) for s in data.get("sections", [])]

    return ShowcaseItem(
        id=data["id"],
        type=data["type"],
        title=data["title"],
        title_ko=data.get("title_ko"),
        title_ja=data.get("title_ja"),
        subtitle=data.get("subtitle"),
        subtitle_ko=data.get("subtitle_ko"),
        subtitle_ja=data.get("subtitle_ja"),
        chapter=data.get("chapter"),
        era=data.get("era"),
        year=data.get("year"),
        location=data.get("location"),
        description=data["description"],
        description_ko=data.get("description_ko"),
        description_ja=data.get("description_ja"),
        sections=sections,
        historical_basis=data.get("historical_basis"),
        historical_basis_ko=data.get("historical_basis_ko"),
        historical_basis_ja=data.get("historical_basis_ja"),
        related_servants=servants,
        related_event_ids=data.get("related_event_ids", []),
        sources=data.get("sources", [])
    )


def get_all_showcases() -> List[ShowcaseItem]:
    """Load all showcase items from all files."""
    all_items = []
    files = ["singularities.json", "lostbelts.json", "servants.json",
             "history.json", "literature.json", "music.json"]

    for filename in files:
        raw_items = load_showcase_file(filename)
        for item in raw_items:
            all_items.append(parse_showcase_item(item))

    return all_items


# === FGO Content ===

@router.get("/fgo/singularities", response_model=ShowcaseListResponse)
def list_singularities():
    """List all FGO Singularities."""
    items = [parse_showcase_item(i) for i in load_showcase_file("singularities.json")]
    return ShowcaseListResponse(items=items, total=len(items), category="singularity")


@router.get("/fgo/lostbelts", response_model=ShowcaseListResponse)
def list_lostbelts():
    """List all FGO Lostbelts."""
    items = [parse_showcase_item(i) for i in load_showcase_file("lostbelts.json")]
    return ShowcaseListResponse(items=items, total=len(items), category="lostbelt")


@router.get("/fgo/servants", response_model=ShowcaseListResponse)
def list_servant_articles():
    """List all Servant column articles."""
    items = [parse_showcase_item(i) for i in load_showcase_file("servants.json")]
    return ShowcaseListResponse(items=items, total=len(items), category="servant")


# === Pan-Human History ===

@router.get("/history", response_model=ShowcaseListResponse)
def list_history_articles():
    """List all historical articles."""
    items = [parse_showcase_item(i) for i in load_showcase_file("history.json")]
    return ShowcaseListResponse(items=items, total=len(items), category="history")


@router.get("/literature", response_model=ShowcaseListResponse)
def list_literature_articles():
    """List all literature articles."""
    items = [parse_showcase_item(i) for i in load_showcase_file("literature.json")]
    return ShowcaseListResponse(items=items, total=len(items), category="literature")


@router.get("/music", response_model=ShowcaseListResponse)
def list_music_articles():
    """List all music articles."""
    items = [parse_showcase_item(i) for i in load_showcase_file("music.json")]
    return ShowcaseListResponse(items=items, total=len(items), category="music")


# === Generic Endpoints ===

@router.get("/", response_model=ShowcaseListResponse)
def list_all_showcases(
    type: Optional[str] = Query(None, description="Filter by type: singularity, lostbelt, servant, article"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0)
):
    """List all showcase items with optional filtering."""
    all_items = get_all_showcases()

    if type:
        all_items = [i for i in all_items if i.type == type]

    total = len(all_items)
    items = all_items[offset:offset + limit]

    return ShowcaseListResponse(items=items, total=total, category="all")


@router.get("/{showcase_id}", response_model=ShowcaseItem)
def get_showcase_by_id(showcase_id: str):
    """Get a specific showcase item by ID."""
    all_items = get_all_showcases()

    for item in all_items:
        if item.id == showcase_id:
            return item

    raise HTTPException(status_code=404, detail=f"Showcase '{showcase_id}' not found")


# === Stats ===

@router.get("/stats/summary")
def get_showcase_stats():
    """Get summary statistics of all showcases."""
    return {
        "fgo": {
            "singularities": len(load_showcase_file("singularities.json")),
            "lostbelts": len(load_showcase_file("lostbelts.json")),
            "servants": len(load_showcase_file("servants.json"))
        },
        "pan_human_history": {
            "history": len(load_showcase_file("history.json")),
            "literature": len(load_showcase_file("literature.json")),
            "music": len(load_showcase_file("music.json"))
        }
    }
