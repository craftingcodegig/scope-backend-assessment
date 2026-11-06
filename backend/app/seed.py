"""Load the sample theaters, users and showtimes into the database.

Run from the backend directory:  python -m app.seed
Existing rows with the same ids are replaced so the script is safe to re-run.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from . import models
from .db import Base, SessionLocal, engine
from .normalize import normalize_title

SEED_FILE = Path(__file__).with_name("seed_data.json")


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def seed(db: Session) -> None:
    data = json.loads(SEED_FILE.read_text(encoding="utf-8"))

    theaters = {
        row["id"]: db.merge(models.Theater(**row)) for row in data["theaters"]
    }

    for row in data["users"]:
        user = db.merge(
            models.User(
                id=row["id"], name=row["name"], email=row["email"], role=row["role"]
            )
        )
        user.theaters = [theaters[theater_id] for theater_id in row["theaterIds"]]

    # Showtimes reference theaters by foreign key only, so flush parents first.
    db.flush()

    for row in data["showtimes"]:
        db.merge(
            models.Showtime(
                id=row["id"],
                theater_id=row["theaterId"],
                movie_title=row["movieTitle"],
                normalized_title=normalize_title(row["movieTitle"]),
                movie_status=row["movieStatus"],
                auditorium=row["auditorium"],
                start_time=_dt(row["startTime"]),
                end_time=_dt(row["endTime"]),
                language=row["language"],
                format=row["format"],
                rating=row["rating"],
                status=row["status"],
                last_updated=_dt(row["lastUpdated"]),
            )
        )

    db.commit()


if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as session:
        seed(session)
    print("Seed complete.")
