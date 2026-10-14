"""Tests for the Morse engine (morse.py) and data integrity."""

import json

import pytest

from morse_titanic.config import CURRICULUM_PATH
from morse_titanic.morse import (
    WORD_SEPARATOR,
    UnknownCharacterError,
    decode_pattern,
    encode,
    get_table,
    normalize_pattern,
)


def test_table_loading() -> None:
    """Assert Morse table loads successfully and has ITU standard defined."""
    table = get_table()
    assert table.standard == "ITU-R M.1677-1"
    assert len(table.char_to_pattern) >= 40
    assert len(table.pattern_to_char) == len(table.char_to_pattern)


def test_no_duplicate_patterns() -> None:
    """Assert every character has a unique pattern (injective mapping)."""
    table = get_table()
    patterns = list(table.char_to_pattern.values())
    unique_patterns = set(patterns)
    assert len(patterns) == len(unique_patterns), "Duplicate Morse patterns detected in table."


def test_round_trip_for_all_table_entries() -> None:
    """Assert each character encodes and decodes back identically."""
    table = get_table()
    for char, pattern in table.char_to_pattern.items():
        # Test encode
        encoded = encode(char, table)
        assert encoded == [pattern], f"Encoding failed for '{char}'"

        # Test decode
        decoded = decode_pattern(pattern, table)
        assert decoded == char, f"Decoding failed for pattern '{pattern}'"


def test_pattern_normalization_variants() -> None:
    """Assert pattern normalizer handles lookalike characters and whitespace."""
    assert normalize_pattern(" . - . ") == ".-."
    assert normalize_pattern("• − •") == ".-."
    assert normalize_pattern("· – ·") == ".-."
    assert normalize_pattern("... ___ ...") == "...---..."
    assert normalize_pattern("— — —") == "---"


def test_encode_words_and_separators() -> None:
    """Assert sentences encode with proper word separator tokens."""
    res = encode("CQD MGY")
    assert res == ["-.-.", "--.-", "-..", WORD_SEPARATOR, "--", "--.", "-.--"]

    # Multiple spaces collapse into a single word separator
    res2 = encode("CQD   MGY")
    assert res2 == ["-.-.", "--.-", "-..", WORD_SEPARATOR, "--", "--.", "-.--"]

    # Leading and trailing spaces don't produce boundary separators
    res3 = encode("  E T  ")
    assert res3 == [".", WORD_SEPARATOR, "-"]


def test_encode_prosign() -> None:
    """Assert prosigns in brackets are treated as a single symbol."""
    res = encode("<SOS>")
    assert res == ["...---..."]

    res_mixed = encode("CQD <SOS>")
    assert res_mixed == ["-.-.", "--.-", "-..", WORD_SEPARATOR, "...---..."]


def test_unknown_character_raises_typed_error() -> None:
    """Assert unknown characters raise UnknownCharacterError without crashing."""
    with pytest.raises(UnknownCharacterError) as exc_info:
        encode("HELLO ~ WORLD")
    assert exc_info.value.char == "~"


def test_curriculum_integrity() -> None:
    """Assert curriculum contains valid, unique characters and covers all 26 letters."""
    table = get_table()

    with open(CURRICULUM_PATH, encoding="utf-8") as f:
        curriculum = json.load(f)

    seen_chars: set[str] = set()
    stages = curriculum.get("stages", [])

    assert len(stages) == 8, "Expected 8 stages in lean curriculum."

    for stage_data in stages:
        chars = stage_data.get("characters", [])
        assert chars, f"Stage {stage_data.get('stage')} has no characters."
        for ch in chars:
            assert ch not in seen_chars, f"Character '{ch}' duplicated in curriculum."
            assert ch in table.char_to_pattern, f"Character '{ch}' not in Morse table."
            seen_chars.add(ch)

    # All 26 letters must be present
    alphabet = {chr(code) for code in range(ord("A"), ord("Z") + 1)}
    assert alphabet.issubset(seen_chars), "Not all letters A-Z are covered in the curriculum."
