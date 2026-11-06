from __future__ import annotations

from sqlalchemy import Column, ForeignKey, String, Table
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base

user_theaters = Table(
    "user_theaters",
    Base.metadata,
    Column("user_id", ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("theater_id", ForeignKey("theaters.id", ondelete="CASCADE"), primary_key=True),
)


class Theater(Base):
    __tablename__ = "theaters"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    location: Mapped[str] = mapped_column(String, nullable=False)
    timezone: Mapped[str] = mapped_column(String, nullable=False)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    role: Mapped[str] = mapped_column(String, nullable=False)  # "admin" | "viewer"

    theaters: Mapped[list[Theater]] = relationship(
        secondary=user_theaters, lazy="selectin", order_by=Theater.name
    )

    @property
    def theater_ids(self) -> list[str]:
        return [theater.id for theater in self.theaters]

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"
