from pathlib import Path

import pytest
from pydantic import BaseModel

from app.assistant import (
    ColumnMappingResponse,
    MatchVerdictsResponse,
    ReviewResponse,
    candidate_pairs,
    projected_schedule,
    review_schedule,
    suggest_column_mapping,
    suggest_matches,
)
from app.ingest import (
    MissingColumnsError,
    apply_accepted_matches,
    diff_schedule,
    parse_csv,
    read_header_and_samples,
    row_key,
)
from tests.test_ingest import _showtimes_from_csv

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


# A respelling the normalizer cannot bridge: "Spiderman" vs "Spider-Man".
RESPELLED_CSV = (
    "theater_name,movie_title,auditorium,start_time,end_time,language,format,rating\n"
    "Downtown Cinema 7,Spiderman Homecoming,Auditorium 1,2025-03-15T18:00:00Z,2025-03-15T20:13:00Z,EN,2D,PG-13\n"
    "Downtown Cinema 7,Inside Out 2,Auditorium 2,2025-03-15T17:30:00Z,2025-03-15T19:20:00Z,EN,3D,PG\n"
    "Downtown Cinema 7,Dune: Part Two,Auditorium 1,2025-03-15T20:00:00Z,2025-03-15T22:46:00Z,EN,2D,PG-13\n"
    "Downtown Cinema 7,Dune: Part Two,Auditorium 1,2025-03-15T22:45:00Z,2025-03-16T01:31:00Z,EN,2D,PG-13\n"
    "Downtown Cinema 7,Wonka,Auditorium 3,2025-03-15T16:00:00Z,2025-03-15T17:56:00Z,EN,2D,PG\n"
    "Downtown Cinema 7,Oppenheimer,Auditorium 4,2025-03-15T21:00:00Z,2025-03-16T00:00:00Z,EN,IMAX,PG-13\n"
)


@pytest.fixture
def respelled_diff():
    existing = _showtimes_from_csv(SAMPLES / "existing.csv")
    rows = parse_csv(RESPELLED_CSV, "Downtown Cinema 7")
    return diff_schedule(existing, rows)


def test_candidate_pairs_are_adds_and_archives_at_the_same_start(respelled_diff):
    pairs = candidate_pairs(respelled_diff)
    assert [(row.movie_title, st.movie_title) for row, st in pairs] == [
        ("Spiderman Homecoming", "Spider‑Man: Homecoming")
    ]


def test_suggest_matches_filters_low_confidence_and_bad_indexes(respelled_diff):
    response = MatchVerdictsResponse(
        verdicts=[
            {"pair_index": 0, "same_movie": True, "confidence": 0.95, "reason": "Same film, hyphen dropped."},
            {"pair_index": 7, "same_movie": True, "confidence": 0.99, "reason": "bogus index"},
        ]
    )
    suggestions = suggest_matches(FakeAi(response), respelled_diff)
    assert len(suggestions) == 1
    assert suggestions[0].csv_title == "Spiderman Homecoming"
    assert suggestions[0].showtime_id == respelled_diff.archives[0].id

    weak = MatchVerdictsResponse(
        verdicts=[{"pair_index": 0, "same_movie": True, "confidence": 0.4, "reason": "unsure"}]
    )
    assert suggest_matches(FakeAi(weak), respelled_diff) == []


def test_suggest_matches_skips_model_when_nothing_to_ask():
    existing = _showtimes_from_csv(SAMPLES / "existing.csv")
    unchanged = parse_csv((SAMPLES / "existing.csv").read_text(encoding="utf-8"), "Downtown Cinema 7")
    ai = FakeAi(None)
    assert suggest_matches(ai, diff_schedule(existing, unchanged)) == []
    assert ai.prompts == []


def test_apply_accepted_matches_turns_add_and_archive_into_update(respelled_diff):
    add = respelled_diff.adds[0]
    archived = respelled_diff.archives[0]

    result = apply_accepted_matches(respelled_diff, {row_key(add): archived.id})

    assert result.adds == []
    assert result.archives == []
    (showtime, row, changes) = result.updates[-1]
    assert showtime is archived and row is add
    assert {c.field for c in changes} == {"movieTitle"}


def test_apply_accepted_matches_ignores_stale_pairs(respelled_diff):
    add = respelled_diff.adds[0]
    result = apply_accepted_matches(respelled_diff, {row_key(add): "no-such-id"})
    assert len(result.adds) == 1 and len(result.archives) == 1


def test_projected_schedule_reflects_adds_updates_and_archives():
    existing = _showtimes_from_csv(SAMPLES / "existing.csv")
    rows = parse_csv((SAMPLES / "new-drop.csv").read_text(encoding="utf-8"), "Downtown Cinema 7")
    schedule = projected_schedule(existing, diff_schedule(existing, rows))

    titles = [entry["title"] for entry in schedule]
    assert "Kung Fu Panda 4" in titles  # added
    assert "Wonka" not in titles and "Oppenheimer" not in titles  # archived
    assert "DUNE PART 2" in titles and "Dune: Part Two" not in titles[:3]  # updated spelling
    assert schedule == sorted(schedule, key=lambda e: (e["start"], e["auditorium"]))


def test_review_schedule_passes_through_and_caps_warnings(respelled_diff):
    existing = _showtimes_from_csv(SAMPLES / "existing.csv")
    warning = {"movie_title": "Wonka", "start_time": "2025-03-15T16:00:00+00:00", "message": "x"}
    response = ReviewResponse(summary="  Two sentences.  ", warnings=[warning] * 30)

    ai = FakeAi(response)
    review = review_schedule(ai, "Downtown Cinema 7", respelled_diff, existing)

    assert review is not None
    assert review.summary == "Two sentences."
    assert len(review.warnings) == 20
    assert "Spiderman Homecoming" in ai.prompts[0] and "Downtown Cinema 7" in ai.prompts[0]


def test_review_schedule_is_none_when_disabled_or_failing(respelled_diff):
    existing = _showtimes_from_csv(SAMPLES / "existing.csv")
    assert review_schedule(FakeAi(None, enabled=False), "T", respelled_diff, existing) is None
    assert review_schedule(FakeAi(None), "T", respelled_diff, existing) is None
