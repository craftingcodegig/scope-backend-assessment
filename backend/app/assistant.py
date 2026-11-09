"""AI upload assistant: the parts of CSV ingestion that need judgement.

Everything here is advisory. The deterministic pipeline in `ingest.py` does
the work; the assistant only proposes a header mapping when a file does not
use our column names. Results are validated before they are used, and the
admin sees them in the preview before anything is applied.
"""

from __future__ import annotations

import json

from pydantic import BaseModel

from .ai import AiClient
from .ingest import REQUIRED_COLUMNS, CsvRow, ScheduleDiff, row_key
from .models import Showtime

COLUMN_DESCRIPTIONS = {
    "theater_name": "name of the theater the showtime belongs to",
    "movie_title": "title of the film",
    "auditorium": "screen or auditorium name/number within the theater",
    "start_time": "when the screening starts (ISO 8601 datetime)",
    "end_time": "when the screening ends (ISO 8601 datetime)",
    "language": "spoken language code or name",
    "format": "projection format such as 2D, 3D or IMAX",
    "rating": "age rating such as PG or R",
}


class ColumnMatch(BaseModel):
    source: str
    target: str


class ColumnMappingResponse(BaseModel):
    mappings: list[ColumnMatch]


def suggest_column_mapping(
    ai: AiClient, headers: list[str], sample_rows: list[list[str]]
) -> dict[str, str] | None:
    """Ask the model which partner header corresponds to each required column.

    Returns {partner header: our column} covering every required column, or
    None when the assistant is disabled, fails, or cannot find them all.
    """
    if not ai.enabled or not headers:
        return None

    prompt = (
        "A cinema partner uploaded a CSV whose column names do not match ours.\n"
        "Map each of OUR columns to exactly one of THEIR headers. Use the sample "
        "rows to decide. Only map a column when you are confident; skip it otherwise.\n\n"
        "OUR columns:\n"
        + "\n".join(f"- {name}: {desc}" for name, desc in COLUMN_DESCRIPTIONS.items())
        + "\n\nTHEIR headers:\n"
        + json.dumps(headers)
        + "\n\nSample rows:\n"
        + "\n".join(json.dumps(row) for row in sample_rows)
        + "\n\nReturn mappings as {source: their header, target: our column}."
    )

    response = ai.generate(prompt, ColumnMappingResponse)
    if response is None:
        return None

    header_lookup = {h.strip().lower(): h for h in headers}
    mapping: dict[str, str] = {}
    for match in response.mappings:
        source = header_lookup.get(match.source.strip().lower())
        if source and match.target in REQUIRED_COLUMNS and source not in mapping:
            mapping[source] = match.target

    covered = set(mapping.values())
    if any(column not in covered for column in REQUIRED_COLUMNS):
        return None
    return mapping


# --- Match suggestions ------------------------------------------------------

MIN_MATCH_CONFIDENCE = 0.7


class MatchVerdict(BaseModel):
    pair_index: int
    same_movie: bool
    confidence: float
    reason: str


class MatchVerdictsResponse(BaseModel):
    verdicts: list[MatchVerdict]


class MatchSuggestion(BaseModel):
    row_key: str
    showtime_id: str
    csv_title: str
    existing_title: str
    confidence: float
    reason: str


def candidate_pairs(diff: ScheduleDiff) -> list[tuple[CsvRow, Showtime]]:
    """Adds and archives that share a start time are probably the same film."""
    archives_by_start: dict = {}
    for showtime in diff.archives:
        archives_by_start.setdefault(showtime.start_time, []).append(showtime)
    return [
        (row, showtime)
        for row in diff.adds
        for showtime in archives_by_start.get(row.start_time, [])
    ]


def suggest_matches(ai: AiClient, diff: ScheduleDiff) -> list[MatchSuggestion]:
    """Ask the model whether unmatched CSV rows are respellings of showtimes
    that would otherwise be archived. The admin decides what to accept."""
    pairs = candidate_pairs(diff)
    if not ai.enabled or not pairs:
        return []

    listing = "\n".join(
        f"{index}. CSV title: {json.dumps(row.movie_title)} in {json.dumps(row.auditorium)}"
        f" | existing title: {json.dumps(showtime.movie_title)} in {json.dumps(showtime.auditorium)}"
        f" | both start {row.start_time.isoformat()}"
        for index, (row, showtime) in enumerate(pairs)
    )
    prompt = (
        "We reconcile a cinema's schedule against a partner CSV. For each pair below, "
        "a CSV row did not match any stored showtime, but a stored showtime at the same "
        "start time would be archived. Decide whether the two titles refer to the same "
        "film (spelling, punctuation, abbreviations, sequel numbering, translations). "
        "Different films that merely share a start time are NOT the same.\n\n"
        + listing
        + "\n\nReturn one verdict per pair with pair_index, same_movie, confidence in [0,1] "
        "and a one-sentence reason."
    )

    response = ai.generate(prompt, MatchVerdictsResponse)
    if response is None:
        return []

    suggestions: list[MatchSuggestion] = []
    seen_rows: set[str] = set()
    for verdict in response.verdicts:
        if not (0 <= verdict.pair_index < len(pairs)):
            continue
        row, showtime = pairs[verdict.pair_index]
        key = row_key(row)
        if not verdict.same_movie or verdict.confidence < MIN_MATCH_CONFIDENCE or key in seen_rows:
            continue
        seen_rows.add(key)
        suggestions.append(
            MatchSuggestion(
                row_key=key,
                showtime_id=showtime.id,
                csv_title=row.movie_title,
                existing_title=showtime.movie_title,
                confidence=round(min(max(verdict.confidence, 0.0), 1.0), 2),
                reason=verdict.reason.strip(),
            )
        )
    return suggestions
