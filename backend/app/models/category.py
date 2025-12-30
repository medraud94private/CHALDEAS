"""
Category model.

Represents the classification taxonomy:
- History (Military, Political, Cultural)
- Philosophy
- Science
- Mythology
- Literature
"""
from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship

from app.models.base import Base, TimestampMixin


class Category(Base, TimestampMixin):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    name_ko = Column(String(100))
    slug = Column(String(100), unique=True, nullable=False, index=True)
    color = Column(String(7), default="#3B82F6")  # HEX color for markers
    icon = Column(String(50))  # Icon name

    # Self-referential for hierarchy
    parent_id = Column(Integer, ForeignKey("categories.id"))
    sort_order = Column(Integer, default=0)

    # Relationships
    parent = relationship("Category", remote_side=[id], backref="children")
    events = relationship("Event", back_populates="category")
    persons = relationship("Person", back_populates="category")

    def __repr__(self):
        return f"<Category(id={self.id}, name='{self.name}')>"
