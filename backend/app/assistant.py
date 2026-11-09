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
from .ingest import REQUIRED_COLUMNS

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
