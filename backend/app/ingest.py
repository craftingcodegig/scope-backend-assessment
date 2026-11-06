"""Partner CSV ingestion: parsing and cleaning."""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import datetime

from .normalize import clean_text, normalize_title

REQUIRED_COLUMNS = (
    "theater_name",
    "movie_title",
    "auditorium",
    "start_time",
    "end_time",
    "language",
    "format",
    "rating",
)


class CsvError(ValueError):
    """Raised for a malformed upload; the message is safe to show to users."""


@dataclass(frozen=True)
class CsvRow:
    movie_title: str
    normalized_title: str
    auditorium: str
    start_time: datetime
    end_time: datetime
    language: str
    format: str
    rating: str

    @property
    def key(self) -> tuple[str, datetime]:
        """Identity of a showtime within a theater: which movie, and when."""
        return (self.normalized_title, self.start_time)


def _parse_datetime(value: str, column: str, line: int) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise CsvError(f"Line {line}: invalid {column} '{value}'") from None
    if parsed.tzinfo is None:
        raise CsvError(f"Line {line}: {column} must include a timezone")
    return parsed


def parse_csv(content: str, theater_name: str) -> list[CsvRow]:
    """Parse a partner drop for one theater into cleaned, de-duplicated rows.

    Whitespace is trimmed and collapsed in every cell. Rows naming a different
    theater are rejected. When the same movie and start time appears more than
    once, the last row wins, so the result has at most one row per key.
    """
    reader = csv.DictReader(io.StringIO(content.lstrip("\ufeff")))
    header = [clean_text(name).lower() for name in reader.fieldnames or []]
    missing = [column for column in REQUIRED_COLUMNS if column not in header]
    if missing:
        raise CsvError(f"Missing columns: {', '.join(missing)}")

    expected_theater = clean_text(theater_name).casefold()
    rows: dict[tuple[str, datetime], CsvRow] = {}

    for line, raw in enumerate(reader, start=2):
        cells = {clean_text(k).lower(): clean_text(v) for k, v in raw.items() if k}
        if not any(cells.values()):
            continue  # blank line
        if cells["theater_name"].casefold() != expected_theater:
            raise CsvError(f"Line {line}: theater '{cells['theater_name']}' does not match")
        if not cells["movie_title"]:
            raise CsvError(f"Line {line}: movie_title is empty")

        row = CsvRow(
            movie_title=cells["movie_title"],
            normalized_title=normalize_title(cells["movie_title"]),
            auditorium=cells["auditorium"],
            start_time=_parse_datetime(cells["start_time"], "start_time", line),
            end_time=_parse_datetime(cells["end_time"], "end_time", line),
            language=cells["language"],
            format=cells["format"],
            rating=cells["rating"],
        )
        rows[row.key] = row

    return list(rows.values())
