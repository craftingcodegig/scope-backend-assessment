from __future__ import annotations

import re
import unicodedata

# Partner feeds spell numbers inconsistently ("Part Two" vs "Part 2").
NUMBER_WORDS = {
    "one": "1",
    "two": "2",
    "three": "3",
    "four": "4",
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8",
    "nine": "9",
    "ten": "10",
    "ii": "2",
    "iii": "3",
    "iv": "4",
}

_NON_ALNUM = re.compile(r"[^a-z0-9]+")
_WHITESPACE = re.compile(r"\s+")


def clean_text(value: str | None) -> str:
    """Trim and collapse internal whitespace, keeping the original spelling."""
    if value is None:
        return ""
    return _WHITESPACE.sub(" ", value).strip()


def normalize_title(title: str | None) -> str:
    """Reduce a movie title to a comparison key.

    Unicode is folded to ASCII-compatible forms, case and punctuation are
    dropped, and number words are replaced with digits so that
    "Spider‑Man: Homecoming", "  Spider Man - Homecoming  " and
    "DUNE PART 2" / "Dune: Part Two" compare equal.
    """
    text = unicodedata.normalize("NFKC", title or "").lower()
    text = _NON_ALNUM.sub(" ", text)
    words = [NUMBER_WORDS.get(word, word) for word in text.split()]
    return " ".join(words)
