from __future__ import annotations

import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .models import create_schema
from .routers import schedule, showtimes, users


class HealthResponse(BaseModel):
    status: str = "ok"
    timestamp: datetime


@asynccontextmanager
async def lifespan(_: FastAPI):
    create_schema()
    yield


app = FastAPI(
    title="Scope Backend Assessment API",
    version="0.1.0",
    description="Showtime schedule API for the backend assessment.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("FRONTEND_ORIGIN", "http://localhost:3000").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(timestamp=datetime.now(timezone.utc))


app.include_router(users.router)
app.include_router(showtimes.router)
app.include_router(schedule.router)
