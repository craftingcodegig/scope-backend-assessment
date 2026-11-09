"""Vercel entry point: serves the FastAPI backend as one Python function.

Vercel routes every /api/* request here (see vercel.json). The backend app is
mounted under /api so its routes keep the same paths they have locally, just
prefixed; the frontend uses NEXT_PUBLIC_API_URL=/api to reach them.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from fastapi import FastAPI  # noqa: E402

from app.main import app as backend  # noqa: E402

app = FastAPI()
app.mount("/api", backend)
