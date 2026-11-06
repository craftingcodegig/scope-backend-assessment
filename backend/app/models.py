from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import Column, DateTime, ForeignKey, String, Table
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


class Showtime(Base):
    __tablename__ = "showtimes"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: uuid4().hex)
    theater_id: Mapped[str] = mapped_column(ForeignKey("theaters.id"), nullable=False)
    movie_title: Mapped[str] = mapped_column(String, nullable=False)
    # Lower-cased, punctuation-free title used for matching and search.
    normalized_title: Mapped[str] = mapped_column(String, nullable=False)
    movie_status: Mapped[str] = mapped_column(String, nullable=False, default="draft")
    auditorium: Mapped[str] = mapped_column(String, nullable=False)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    language: Mapped[str] = mapped_column(String, nullable=False)
    format: Mapped[str] = mapped_column(String, nullable=False)
    rating: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="active")
    last_updated: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
