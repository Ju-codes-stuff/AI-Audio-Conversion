"""
Departments API — department and category reference data.
"""
from __future__ import annotations

from typing import List

from fastapi import APIRouter
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.dependencies import DBSession
from app.models.department import Category, Department
from pydantic import BaseModel


class CategoryOut(BaseModel):
    id: str
    name: str
    code: str
    description: str | None = None
    is_active: bool
    model_config = {"from_attributes": True}


class DepartmentOut(BaseModel):
    id: str
    name: str
    code: str
    description: str | None = None
    is_active: bool
    model_config = {"from_attributes": True}


class DepartmentWithCategories(DepartmentOut):
    categories: List[CategoryOut] = []


router = APIRouter(prefix="/departments", tags=["Departments"])


@router.get("/", response_model=List[DepartmentOut])
async def list_departments(db: DBSession):
    """Return all active top-level departments."""
    result = await db.execute(
        select(Department)
        .where(Department.is_active == True, Department.parent_id.is_(None))  # noqa: E712
        .order_by(Department.name)
    )
    return list(result.scalars().all())


@router.get("/{department_id}", response_model=DepartmentWithCategories)
async def get_department(department_id: str, db: DBSession):
    """Return a department with its categories."""
    result = await db.execute(
        select(Department)
        .where(Department.id == department_id)
        .options(selectinload(Department.categories))
    )
    dept = result.scalar_one_or_none()
    if dept is None:
        from app.core.exceptions import NotFoundError
        raise NotFoundError("Department")
    return dept


@router.get("/{department_id}/categories", response_model=List[CategoryOut])
async def list_categories(department_id: str, db: DBSession):
    """Return all active categories for a given department."""
    result = await db.execute(
        select(Category)
        .where(
            Category.department_id == department_id,
            Category.is_active == True,  # noqa: E712
        )
        .order_by(Category.name)
    )
    return list(result.scalars().all())
