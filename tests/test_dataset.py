"""Tests for Titanic dataset schema validation and verified filtering (dataset.py)."""

from morse_titanic.config import PROJECT_ROOT, TITANIC_MESSAGES_PATH
from morse_titanic.dataset import (
    compute_required_characters,
    compute_segments,
    load_messages,
)

FIXTURES_DIR = PROJECT_ROOT / "tests" / "fixtures"


def test_real_shipped_dataset_validates_cleanly() -> None:
    """The authentic shipped dataset passes all schema and normalization checks."""
    messages, errors = load_messages(TITANIC_MESSAGES_PATH, allow_unverified=True)
    assert not errors, f"Shipped dataset failed validation: {errors}"
    assert len(messages) >= 3


def test_shipped_dataset_yields_zero_verified_messages_for_player() -> None:
    """Shipped dataset has only pending research drafts; default loader returns 0 verified."""
    messages, errors = load_messages(TITANIC_MESSAGES_PATH, allow_unverified=False)
    assert not errors
    assert len(messages) == 0, "Agent must never ship auto-verified messages to the player."


def test_valid_synthetic_fixture_loads_successfully() -> None:
    """Valid synthetic verified fixture loads properly with computed segments."""
    fixture = FIXTURES_DIR / "valid_verified_dataset.json"
    messages, errors = load_messages(fixture, allow_unverified=False)
    assert not errors
    assert len(messages) == 1

    msg = messages[0]
    assert msg.id == "synthetic_test_signal"
    assert msg.verification_status == "verified"
    assert msg.segments == ["TEST CQD"]
    assert "C" in msg.required_characters
    assert "Q" in msg.required_characters


def test_segmentation_math() -> None:
    """Messages are properly split into chunks of at most max_words."""
    text = "WE ARE SINKING FAST SEND BOATS IMMEDIATELY"
    segments = compute_segments(text, max_words=4)
    assert segments == ["WE ARE SINKING FAST", "SEND BOATS IMMEDIATELY"]


def test_required_characters_extraction() -> None:
    """Extracts characters and prosigns without punctuation loss."""
    req = compute_required_characters("CQD 41.46 <SOS>")
    assert req == {"C", "Q", "D", "4", "1", ".", "6", "<SOS>"}




def test_validator_rejects_placeholder_markers() -> None:
    """Entries containing TODO, PLACEHOLDER, or XXX markers are rejected."""
    fixture = FIXTURES_DIR / "invalid_placeholder.json"
    messages, errors = load_messages(fixture, allow_unverified=False)
    assert len(messages) == 0
    assert any("Placeholder marker found" in e for e in errors)


def test_validator_rejects_unsupported_characters() -> None:
    """Entries with characters not in the ITU Morse table are rejected."""
    fixture = FIXTURES_DIR / "invalid_bad_chars.json"
    messages, errors = load_messages(fixture, allow_unverified=False)
    assert len(messages) == 0
    assert any("not in Morse table" in e for e in errors)
