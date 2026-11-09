from pathlib import Path

import pytest
from pydantic import BaseModel

from app.assistant import ColumnMappingResponse, suggest_column_mapping
from app.ingest import MissingColumnsError, parse_csv, read_header_and_samples

SAMPLES = Path(__file__).resolve().parents[2] / "sample-data"

PARTNER_CSV = (
    "Cinema,Film,Screen,Starts,Ends,Lang,Projection,Cert\n"
    "Downtown Cinema 7,Wonka,Screen 3,2025-03-15T16:00:00Z,2025-03-15T17:56:00Z,EN,2D,PG\n"
    "Downtown Cinema 7,Dune: Part Two,Screen 1,2025-03-15T20:00:00Z,2025-03-15T22:46:00Z,EN,IMAX,PG-13\n"
)

PARTNER_MAPPING = {
    "Cinema": "theater_name",
    "Film": "movie_title",
    "Screen": "auditorium",
    "Starts": "start_time",
    "Ends": "end_time",
    "Lang": "language",
    "Projection": "format",
    "Cert": "rating",
}


class FakeAi:
    """Returns canned responses and records the prompts it was given."""

    def __init__(self, response: BaseModel | None, enabled: bool = True):
        self.response = response
        self.enabled = enabled
        self.prompts: list[str] = []

    def generate(self, prompt, schema):
        self.prompts.append(prompt)
        return self.response if isinstance(self.response, schema) else None


def test_unknown_headers_raise_missing_columns():
    with pytest.raises(MissingColumnsError) as info:
        parse_csv(PARTNER_CSV, "Downtown Cinema 7")
    assert info.value.headers == list(PARTNER_MAPPING)
    assert "movie_title" in info.value.missing


def test_parse_csv_accepts_a_column_mapping():
    rows = parse_csv(PARTNER_CSV, "Downtown Cinema 7", column_mapping=PARTNER_MAPPING)
    assert [r.movie_title for r in rows] == ["Wonka", "Dune: Part Two"]
    assert rows[0].auditorium == "Screen 3"


def test_read_header_and_samples_limits_rows():
    headers, samples = read_header_and_samples(PARTNER_CSV, limit=1)
    assert headers == list(PARTNER_MAPPING)
    assert samples == [["Downtown Cinema 7", "Wonka", "Screen 3", "2025-03-15T16:00:00Z",
                        "2025-03-15T17:56:00Z", "EN", "2D", "PG"]]


def test_suggest_column_mapping_uses_model_answer():
    response = ColumnMappingResponse(
        mappings=[{"source": s, "target": t} for s, t in PARTNER_MAPPING.items()]
    )
    ai = FakeAi(response)
    headers, samples = read_header_and_samples(PARTNER_CSV)

    mapping = suggest_column_mapping(ai, headers, samples)

    assert mapping == PARTNER_MAPPING
    assert "Projection" in ai.prompts[0] and "movie_title" in ai.prompts[0]


def test_suggest_column_mapping_rejects_incomplete_or_bogus_answers():
    headers, samples = read_header_and_samples(PARTNER_CSV)

    partial = ColumnMappingResponse(mappings=[{"source": "Film", "target": "movie_title"}])
    assert suggest_column_mapping(FakeAi(partial), headers, samples) is None

    bogus = ColumnMappingResponse(
        mappings=[{"source": s, "target": t} for s, t in PARTNER_MAPPING.items()]
        + [{"source": "Nope", "target": "rating"}, {"source": "Film", "target": "id"}]
    )
    assert suggest_column_mapping(FakeAi(bogus), headers, samples) == PARTNER_MAPPING


def test_suggest_column_mapping_is_skipped_when_disabled():
    ai = FakeAi(None, enabled=False)
    assert suggest_column_mapping(ai, ["Film"], []) is None
    assert ai.prompts == []
