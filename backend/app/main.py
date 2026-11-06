from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from pydantic import BaseModel

from . import models  # noqa: F401  (registers tables on Base.metadata)
from .db import Base, engine


class HealthResponse(BaseModel):
    status: str = "ok"
    timestamp: datetime


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="Scope Backend Assessment API",
    version="0.1.0",
    description="Showtime schedule API for the backend assessment.",
    lifespan=lifespan,
)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(timestamp=datetime.now(timezone.utc))
