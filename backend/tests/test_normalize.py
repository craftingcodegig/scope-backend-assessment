import pytest

from app.normalize import clean_text, normalize_title


@pytest.mark.parametrize(
    ("left", "right"),
    [
        ("Spider\u2011Man: Homecoming", "  Spider Man - Homecoming  "),
        ("Inside Out 2", "Inside   Out  2"),
        ("Dune: Part Two", "DUNE PART 2"),
        ("Rocky II", "Rocky 2"),
    ],
)
def test_variants_normalize_to_same_key(left, right):
    assert normalize_title(left) == normalize_title(right)


def test_different_titles_stay_different():
    assert normalize_title("Dune: Part Two") != normalize_title("Dune: Part One")


def test_normalize_title_handles_empty_values():
    assert normalize_title(None) == ""
    assert normalize_title("   ") == ""


def test_clean_text_collapses_whitespace_only():
    assert clean_text("  Auditorium   1 (Laser) ") == "Auditorium 1 (Laser)"
    assert clean_text(None) == ""
