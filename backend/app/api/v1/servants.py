"""
FGO Servant API - 서번트와 역사적 원전 연결
"""
import json
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, text
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.db.session import get_db
from app.models.person import Person
from app.models.v1.text_mention import TextMention
from app.models.source import Source

router = APIRouter(prefix="/servants", tags=["servants"])

# Load servant mapping
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent
MAPPING_PATH = PROJECT_ROOT / "data/raw/atlas_academy/servant_db_mapping.json"
FGO_DATA_PATH = PROJECT_ROOT / "data/raw/atlas_academy/fgo_historical_figures.json"

_servant_mapping = None
_fgo_data = None


def get_servant_mapping():
    global _servant_mapping
    if _servant_mapping is None:
        if MAPPING_PATH.exists():
            with open(MAPPING_PATH, encoding='utf-8') as f:
                _servant_mapping = json.load(f)
        else:
            _servant_mapping = {"mapped": [], "fgo_original": [], "not_found": []}
    return _servant_mapping


def get_fgo_data():
    global _fgo_data
    if _fgo_data is None:
        if FGO_DATA_PATH.exists():
            with open(FGO_DATA_PATH, encoding='utf-8') as f:
                _fgo_data = json.load(f)
        else:
            _fgo_data = []
    return _fgo_data


class ServantSummary(BaseModel):
    fgo_name: str
    fgo_class: Optional[str] = None
    rarity: Optional[int] = None
    origin: Optional[str] = None
    person_id: Optional[int] = None
    person_name: Optional[str] = None
    wikidata_id: Optional[str] = None
    mention_count: int = 0
    is_fgo_original: bool = False


class ServantDetail(BaseModel):
    fgo_name: str
    fgo_class: Optional[str] = None
    rarity: Optional[int] = None
    origin: Optional[str] = None
    person_id: Optional[int] = None
    person_name: Optional[str] = None
    person_name_ko: Optional[str] = None
    wikidata_id: Optional[str] = None
    biography: Optional[str] = None
    birth_year: Optional[int] = None
    death_year: Optional[int] = None
    is_fgo_original: bool = False
    mention_count: int = 0
    book_mentions: list = []


class BookMention(BaseModel):
    source_id: int
    source_title: str
    source_author: Optional[str] = None
    mention_count: int
    sample_contexts: list[str] = []


@router.get("/", response_model=list[ServantSummary])
def list_servants(
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    origin: Optional[str] = None,
    has_books: Optional[bool] = None,
    search: Optional[str] = None,
):
    """
    List all FGO servants with their historical counterparts
    """
    mapping = get_servant_mapping()
    fgo_data = get_fgo_data()

    # Create FGO name -> data lookup
    fgo_lookup = {s['fgo_name']: s for s in fgo_data}

    # Build result list
    results = []

    # Process mapped servants
    for m in mapping.get('mapped', []):
        fgo_name = m['fgo_name']
        fgo_info = fgo_lookup.get(fgo_name, {})

        # Get mention count
        mention_count = 0
        if m.get('person_id'):
            mention_count = db.query(func.count(TextMention.id)).filter(
                TextMention.entity_type == 'person',
                TextMention.entity_id == m['person_id']
            ).scalar() or 0

        results.append(ServantSummary(
            fgo_name=fgo_name,
            fgo_class=fgo_info.get('fgo_class'),
            rarity=fgo_info.get('rarity'),
            origin=fgo_info.get('origin'),
            person_id=m.get('person_id'),
            person_name=m.get('person_name'),
            wikidata_id=m.get('qid'),
            mention_count=mention_count,
            is_fgo_original=False
        ))

    # Process FGO originals
    for fgo_name in mapping.get('fgo_original', []):
        fgo_info = fgo_lookup.get(fgo_name, {})
        results.append(ServantSummary(
            fgo_name=fgo_name,
            fgo_class=fgo_info.get('fgo_class'),
            rarity=fgo_info.get('rarity'),
            origin=fgo_info.get('origin'),
            person_id=None,
            person_name=None,
            wikidata_id=None,
            mention_count=0,
            is_fgo_original=True
        ))

    # Apply filters
    if origin:
        results = [r for r in results if r.origin and origin.lower() in r.origin.lower()]

    if has_books is True:
        results = [r for r in results if r.mention_count > 0]
    elif has_books is False:
        results = [r for r in results if r.mention_count == 0]

    if search:
        search_lower = search.lower()
        results = [r for r in results if
                   search_lower in r.fgo_name.lower() or
                   (r.person_name and search_lower in r.person_name.lower())]

    # Sort by mention count (descending), then by name
    results.sort(key=lambda x: (-x.mention_count, x.fgo_name))

    # Paginate
    return results[skip:skip + limit]


@router.get("/stats")
def get_servant_stats(db: Session = Depends(get_db)):
    """
    Get statistics about servant-book connections
    """
    mapping = get_servant_mapping()

    mapped_count = len(mapping.get('mapped', []))
    original_count = len(mapping.get('fgo_original', []))

    # Count servants with book mentions
    person_ids = [m['person_id'] for m in mapping.get('mapped', []) if m.get('person_id')]

    servants_with_books = 0
    total_mentions = 0

    if person_ids:
        mention_stats = db.query(
            TextMention.entity_id,
            func.count(TextMention.id).label('count')
        ).filter(
            TextMention.entity_type == 'person',
            TextMention.entity_id.in_(person_ids)
        ).group_by(TextMention.entity_id).all()

        servants_with_books = len(mention_stats)
        total_mentions = sum(m.count for m in mention_stats)

    return {
        "total_servants": mapped_count + original_count,
        "mapped_to_history": mapped_count,
        "fgo_original": original_count,
        "servants_with_books": servants_with_books,
        "total_book_mentions": total_mentions
    }


@router.get("/{fgo_name}", response_model=ServantDetail)
def get_servant_detail(
    fgo_name: str,
    db: Session = Depends(get_db)
):
    """
    Get detailed information about a servant including book mentions
    """
    mapping = get_servant_mapping()
    fgo_data = get_fgo_data()

    # Find servant in mapping
    fgo_lookup = {s['fgo_name']: s for s in fgo_data}
    fgo_info = fgo_lookup.get(fgo_name, {})

    # Check if FGO original
    if fgo_name in mapping.get('fgo_original', []):
        return ServantDetail(
            fgo_name=fgo_name,
            fgo_class=fgo_info.get('fgo_class'),
            rarity=fgo_info.get('rarity'),
            origin=fgo_info.get('origin'),
            is_fgo_original=True
        )

    # Find in mapped
    servant_map = None
    for m in mapping.get('mapped', []):
        if m['fgo_name'] == fgo_name:
            servant_map = m
            break

    if not servant_map:
        raise HTTPException(status_code=404, detail="Servant not found")

    # Get person details
    person = None
    if servant_map.get('person_id'):
        person = db.query(Person).filter(Person.id == servant_map['person_id']).first()

    # Get book mentions
    book_mentions = []
    mention_count = 0

    if person:
        # Get mentions grouped by source
        mentions_by_source = db.query(
            TextMention.source_id,
            Source.title,
            Source.author,
            func.count(TextMention.id).label('count')
        ).join(
            Source, TextMention.source_id == Source.id
        ).filter(
            TextMention.entity_type == 'person',
            TextMention.entity_id == person.id
        ).group_by(
            TextMention.source_id, Source.title, Source.author
        ).order_by(
            func.count(TextMention.id).desc()
        ).limit(20).all()

        for m in mentions_by_source:
            # Get sample contexts
            samples = db.query(TextMention.context_text).filter(
                TextMention.entity_type == 'person',
                TextMention.entity_id == person.id,
                TextMention.source_id == m.source_id
            ).limit(3).all()

            book_mentions.append(BookMention(
                source_id=m.source_id,
                source_title=m.title or "Unknown",
                source_author=m.author,
                mention_count=m.count,
                sample_contexts=[s.context_text for s in samples if s.context_text]
            ))
            mention_count += m.count

    return ServantDetail(
        fgo_name=fgo_name,
        fgo_class=fgo_info.get('fgo_class'),
        rarity=fgo_info.get('rarity'),
        origin=fgo_info.get('origin'),
        person_id=servant_map.get('person_id'),
        person_name=person.name if person else servant_map.get('person_name'),
        person_name_ko=person.name_ko if person else None,
        wikidata_id=servant_map.get('qid'),
        biography=person.biography if person else None,
        birth_year=person.birth_year if person else None,
        death_year=person.death_year if person else None,
        is_fgo_original=False,
        mention_count=mention_count,
        book_mentions=book_mentions
    )


@router.get("/by-person/{person_id}", response_model=list[ServantSummary])
def get_servants_by_person(
    person_id: int,
    db: Session = Depends(get_db)
):
    """
    Get all servants connected to a specific historical person
    """
    mapping = get_servant_mapping()
    fgo_data = get_fgo_data()
    fgo_lookup = {s['fgo_name']: s for s in fgo_data}

    # Get mention count for this person
    mention_count = db.query(func.count(TextMention.id)).filter(
        TextMention.entity_type == 'person',
        TextMention.entity_id == person_id
    ).scalar() or 0

    results = []
    for m in mapping.get('mapped', []):
        if m.get('person_id') == person_id:
            fgo_info = fgo_lookup.get(m['fgo_name'], {})
            results.append(ServantSummary(
                fgo_name=m['fgo_name'],
                fgo_class=fgo_info.get('fgo_class'),
                rarity=fgo_info.get('rarity'),
                origin=fgo_info.get('origin'),
                person_id=m.get('person_id'),
                person_name=m.get('person_name'),
                wikidata_id=m.get('qid'),
                mention_count=mention_count,
                is_fgo_original=False
            ))

    return results
