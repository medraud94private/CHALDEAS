"""
Categories API endpoints.

Provides access to category taxonomy (History, Philosophy, Science, etc.)
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.category import CategoryTree
from app.services import category_service

router = APIRouter()


@router.get("", response_model=CategoryTree)
async def list_categories(
    db: Session = Depends(get_db),
):
    """
    Get all categories in a hierarchical tree structure.

    Categories include:
    - History (Military, Political, Cultural)
    - Philosophy
    - Science
    - Mythology
    - Literature
    """
    categories = category_service.get_category_tree(db)
    return CategoryTree(items=categories)
