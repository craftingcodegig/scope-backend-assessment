from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.ingest import CsvError, diff_schedule, parse_csv
from app.models import Showtime
from app.normalize import normalize_title

SAMPLES = Path(__file__).resolve().parents[2] / "sample-data"
THEATER = "Downtown Cinema 7"


def _showtimes_from_csv(path: Path) -> list[Showtime]:
    """Turn the 'existing.csv' sample into ORM rows as they would be stored."""
    return [
        Showtime(
            id=f"st-{index}",
            theater_id="theater-downtown",
            movie_title=row.movie_title,
            normalized_title=row.normalized_title,
            movie_status="approved",
            auditorium=row.auditorium,
            start_time=row.start_time,
            end_time=row.end_time,
            language=row.language,
            format=row.format,
            rating=row.rating,
            status="active",
            last_updated=datetime(2025, 3, 10, tzinfo=timezone.utc),
        )
        for index, row in enumerate(parse_csv(path.read_text(encoding="utf-8"), THEATER))
    ]


@pytest.fixture
def existing() -> list[Showtime]:
    return _showtimes_from_csv(SAMPLES / "existing.csv")


@pytest.fixture
def new_drop():
    return parse_csv((SAMPLES / "new-drop.csv").read_text(encoding="utf-8"), THEATER)


def test_parse_csv_cleans_and_deduplicates(new_drop):
    titles = [row.movie_title for row in new_drop]
    assert titles == [
        "Spider Man - Homecoming",
        "Inside Out 2",
        "DUNE PART 2",
        "Dune: Part Two",
        "Kung Fu Panda 4",
    ]


def test_parse_csv_rejects_other_theaters():
    content = (SAMPLES / "new-drop.csv").read_text(encoding="utf-8")
    with pytest.raises(CsvError, match="does not match"):
        parse_csv(content, "Riverside Multiplex")


def test_parse_csv_requires_known_columns():
    with pytest.raises(CsvError, match="Missing columns"):
        parse_csv("theater_name,movie_title\nDowntown Cinema 7,Wonka\n", THEATER)


def test_diff_against_sample_drop(existing, new_drop):
    diff = diff_schedule(existing, new_drop)

    assert [row.movie_title for row in diff.adds] == ["Kung Fu Panda 4"]
    assert sorted(row.movie_title for row in diff.archives) == ["Oppenheimer", "Wonka"]

    updates = {showtime.movie_title: changes for showtime, _, changes in diff.updates}
    assert set(updates) == {"Spider\u2011Man: Homecoming", "Inside Out 2", "Dune: Part Two"}
    assert {c.field for c in updates["Spider\u2011Man: Homecoming"]} == {"movieTitle", "auditorium"}
    assert {c.field for c in updates["Inside Out 2"]} == {"auditorium"}
    assert {c.field for c in updates["Dune: Part Two"]} == {"movieTitle", "auditorium", "format"}


def test_diff_is_empty_when_nothing_changed(existing):
    unchanged = parse_csv((SAMPLES / "existing.csv").read_text(encoding="utf-8"), THEATER)
    diff = diff_schedule(existing, unchanged)
    assert (diff.adds, diff.updates, diff.archives) == ([], [], [])


def test_diff_reactivates_archived_showtime(existing, new_drop):
    existing[0].status = "archived"  # Spider-Man at 18:00 was archived earlier
    diff = diff_schedule(existing, new_drop)
    spider = next(changes for st, _, changes in diff.updates if st.id == existing[0].id)
    assert any(c.field == "status" and c.new_value == "active" for c in spider)


def test_diff_prefers_active_row_when_duplicates_exist(existing, new_drop):
    ghost = Showtime(**{k: v for k, v in vars(existing[0]).items() if not k.startswith("_")})
    ghost.id = "ghost"
    ghost.status = "archived"
    ghost.last_updated = datetime(2025, 3, 20, tzinfo=timezone.utc)  # newer, but archived
    diff = diff_schedule(existing + [ghost], new_drop)
    assert {st.id for st, _, _ in diff.updates} >= {existing[0].id}
    assert "ghost" not in {st.id for st, _, _ in diff.updates}


def test_normalized_titles_in_both_samples_line_up(existing, new_drop):
    assert {normalize_title(s.movie_title) for s in existing[:4]} == {r.normalized_title for r in new_drop[:4]}
