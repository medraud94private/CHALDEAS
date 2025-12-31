"""Category service."""
from sqlalchemy.orm import Session
from app.models.category import Category


def get_category_tree(db: Session) -> list[Category]:
    """Get all categories as a hierarchical tree."""
    # Get root categories (no parent)
    roots = db.query(Category).filter(Category.parent_id.is_(None)).all()
    return roots


def get_category_by_slug(db: Session, slug: str) -> Category | None:
    """Get category by slug."""
    return db.query(Category).filter(Category.slug == slug).first()
