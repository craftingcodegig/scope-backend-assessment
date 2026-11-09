from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import NullPool

# The frontend and backend share the repository-level .env file.
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

DATABASE_URL = os.environ["DATABASE_URL"].replace(
    "postgresql://", "postgresql+psycopg://", 1
)

# Serverless functions are short-lived, so holding a connection pool open only
# wastes database connections; open one per request there instead.
IS_SERVERLESS = bool(os.environ.get("VERCEL"))

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    poolclass=NullPool if IS_SERVERLESS else None,
    # Serve timestamps in UTC regardless of the host machine timezone.
    connect_args={"options": "-c timezone=utc"},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Iterator[Session]:
    with SessionLocal() as db:
        yield db
