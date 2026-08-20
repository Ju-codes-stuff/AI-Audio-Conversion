"""
Department and Category ORM models.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Department(Base):
    __tablename__ = "departments"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    parent_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("departments.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    parent: Mapped["Department | None"] = relationship(
        "Department", remote_side="Department.id", back_populates="children"
    )
    children: Mapped[list["Department"]] = relationship(
        "Department", back_populates="parent"
    )
    categories: Mapped[list["Category"]] = relationship(
        "Category", back_populates="department", cascade="all, delete-orphan"
    )
    grievances: Mapped[list["Grievance"]] = relationship(  # noqa: F821
        "Grievance", back_populates="department"
    )
    government_services: Mapped[list["GovernmentService"]] = relationship(  # noqa: F821
        "GovernmentService", back_populates="department"
    )

    def __repr__(self) -> str:
        return f"<Department code={self.code} name={self.name}>"


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    department_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("departments.id", ondelete="CASCADE"), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    department: Mapped["Department"] = relationship("Department", back_populates="categories")

    def __repr__(self) -> str:
        return f"<Category code={self.code}>"
