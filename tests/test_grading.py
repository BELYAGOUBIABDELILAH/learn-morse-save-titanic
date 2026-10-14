"""Tests for answer normalization and grading logic (grading.py)."""

from morse_titanic.grading import grade, normalize


def test_normalize_whitespace_and_casing() -> None:
    """Whitespace collapsed, surrounding stripped, casing uppercased."""
    assert normalize("  hello   world  ") == "HELLO WORLD"
    assert normalize("cqd   mgy") == "CQD MGY"


def test_normalize_dashes_and_quotes() -> None:
    """Dash and quote variations normalized to standard ASCII characters."""
    assert normalize("41–46 N — 50−14 W") == "41-46 N - 50-14 W"
    assert normalize("‘SOS’ “TITANIC”") == "'SOS' \"TITANIC\""


def test_normalize_preserves_punctuation() -> None:
    """Critical punctuation in messages (periods, commas, slashes) is kept."""
    text = "WE ARE SINKING FAST. BOATS NEEDED IMMEDIATELY/SOS?"
    assert normalize(text) == text


def test_grade_exact_match() -> None:
    """Exact match yields score 1.0 and exact=True."""
    res = grade("CQD", "cqd")
    assert res.exact is True
    assert res.score == 1.0
    assert res.diff_summary == "Exact match."


def test_grade_partial_match_single_word() -> None:
    """Single character difference produces informative, constructive feedback."""
    res = grade("E", "T")
    assert res.exact is False
    assert "Expected 'E', got 'T'" in res.diff_summary


def test_grade_multi_word_diff() -> None:
    """Multi-word answers report number of matching words."""
    res = grade("CQD MGY TITANIC", "CQD MGY CARPATHIA")
    assert res.exact is False
    assert "2 of 3 words matched." in res.diff_summary
