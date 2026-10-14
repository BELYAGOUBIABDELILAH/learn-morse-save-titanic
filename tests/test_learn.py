"""Tests for the learning engine flow and curriculum loaders (learn.py)."""

from morse_titanic.learn import load_curriculum, pattern_phonetic


def test_pattern_phonetic() -> None:
    """Pattern phonetics convert dots and dashes to dits and dahs."""
    assert pattern_phonetic(".-") == "dit dah"
    assert pattern_phonetic("...") == "dit dit dit"
    assert pattern_phonetic("---") == "dah dah dah"
    assert pattern_phonetic("-.-.") == "dah dit dah dit"


def test_curriculum_loader() -> None:
    """Curriculum loader returns non-empty list of stages."""
    stages = load_curriculum()
    assert len(stages) == 8
    assert stages[0]["stage"] == 1
    assert "E" in stages[0]["characters"]
    assert "T" in stages[0]["characters"]
