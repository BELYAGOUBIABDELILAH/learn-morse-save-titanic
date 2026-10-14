"""Morse code table, encoding, decoding, and pattern normalization."""

import json
from pathlib import Path

from morse_titanic.config import MORSE_TABLE_PATH

WORD_SEPARATOR = "/"


class MorseError(Exception):
    """Base exception for Morse engine errors."""


class UnknownCharacterError(MorseError):
    """Raised when an input character cannot be represented in Morse code."""

    def __init__(self, char: str) -> None:
        super().__init__(f"Character '{char}' is not in the Morse code table.")
        self.char = char


class UnknownPatternError(MorseError):
    """Raised when a Morse pattern does not map to any known character."""

    def __init__(self, pattern: str) -> None:
        super().__init__(f"Pattern '{pattern}' does not map to any known character.")
        self.pattern = pattern


class MorseTable:
    """Represents an ITU-R M.1677-1 Morse code specification table."""

    def __init__(self, table_path: Path | None = None) -> None:
        self.path = table_path or MORSE_TABLE_PATH
        self.standard: str = ""
        self.char_to_pattern: dict[str, str] = {}
        self.pattern_to_char: dict[str, str] = {}
        self.char_to_kind: dict[str, str] = {}
        self.prosigns: set[str] = set()
        self._load()

    def _load(self) -> None:
        with open(self.path, encoding="utf-8") as f:
            data = json.load(f)

        self.standard = data.get("standard", "ITU-R M.1677-1")
        for entry in data.get("characters", []):
            char = entry["char"]
            pattern = entry["pattern"]
            kind = entry.get("kind", "letter")

            self.char_to_pattern[char] = pattern
            self.pattern_to_char[pattern] = char
            self.char_to_kind[char] = kind

            if kind == "prosign":
                self.prosigns.add(char)


_DEFAULT_TABLE: MorseTable | None = None


def get_table() -> MorseTable:
    """Return the singleton MorseTable instance."""
    global _DEFAULT_TABLE
    if _DEFAULT_TABLE is None:
        _DEFAULT_TABLE = MorseTable()
    return _DEFAULT_TABLE


def normalize_pattern(user_input: str) -> str:
    """Normalize user-typed dots and dashes to standard '.' and '-'.

    Replaces common lookalikes:
    - Bullet '•', middle dot '·' -> '.'
    - Minus '−', en-dash '–', em-dash '—', underscore '_' -> '-'
    Strips internal and surrounding whitespace.
    """
    cleaned = user_input.strip()
    # Remove all whitespace
    cleaned = "".join(cleaned.split())

    substitutions = {
        "•": ".",
        "·": ".",
        "−": "-",
        "–": "-",
        "—": "-",
        "_": "-",
    }
    for old, new in substitutions.items():
        cleaned = cleaned.replace(old, new)

    return cleaned


def encode(text: str, table: MorseTable | None = None) -> list[str]:
    """Encode text to a list of Morse patterns.

    Word boundaries are represented by WORD_SEPARATOR ('/').
    Prosigns enclosed in angle brackets (e.g. '<SOS>') are treated as single symbols.
    Raises UnknownCharacterError if a character cannot be mapped.
    """
    tbl = table or get_table()
    patterns: list[str] = []

    i = 0
    length = len(text)
    last_was_space = False

    while i < length:
        ch = text[i]

        if ch.isspace():
            if not last_was_space and patterns:
                patterns.append(WORD_SEPARATOR)
            last_was_space = True
            i += 1
            continue

        last_was_space = False

        # Check for prosigns enclosed in <...>
        if ch == "<":
            end_idx = text.find(">", i)
            if end_idx != -1:
                candidate = text[i : end_idx + 1].upper()
                if candidate in tbl.char_to_pattern:
                    patterns.append(tbl.char_to_pattern[candidate])
                    i = end_idx + 1
                    continue

        char_upper = ch.upper()
        if char_upper in tbl.char_to_pattern:
            patterns.append(tbl.char_to_pattern[char_upper])
        else:
            raise UnknownCharacterError(ch)

        i += 1

    # Remove trailing word separator if present
    if patterns and patterns[-1] == WORD_SEPARATOR:
        patterns.pop()

    return patterns


def decode_pattern(pattern: str, table: MorseTable | None = None) -> str | None:
    """Decode a single Morse pattern to its character or prosign.

    Returns None if pattern is unrecognized.
    """
    tbl = table or get_table()
    normalized = normalize_pattern(pattern)
    return tbl.pattern_to_char.get(normalized)
