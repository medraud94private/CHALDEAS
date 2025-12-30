"""Category schemas."""
from pydantic import BaseModel
from typing import Optional


class CategoryBase(BaseModel):
    name: str
    name_ko: Optional[str] = None
    slug: str
    color: str = "#3B82F6"
    icon: Optional[str] = None


class Category(CategoryBase):
    id: int

    class Config:
        from_attributes = True


class CategoryWithChildren(Category):
    children: list["CategoryWithChildren"] = []


class CategoryTree(BaseModel):
    items: list[CategoryWithChildren]
