"""Tests for progress persistence, atomic writes, and mastery gate (progress.py)."""

from pathlib import Path

from morse_titanic.progress import ProgressManager


def test_progress_round_trip(tmp_path: Path) -> None:
    """Progress saves and reloads state accurately."""
    mgr = ProgressManager(data_dir=tmp_path)
    mgr.current_stage = 2
    mgr.unlock_character("E")
    mgr.unlock_character("T")
    mgr.record_attempt("E", is_correct=True)
    mgr.record_attempt("E", is_correct=False, typed="I")
    mgr.save()

    # Re-instantiate from same directory
    mgr2 = ProgressManager(data_dir=tmp_path)
    assert mgr2.current_stage == 2
    assert mgr2.learned_characters == ["E", "T"]
    assert mgr2.characters["E"]["attempts"] == 2
    assert mgr2.characters["E"]["correct"] == 1
    assert mgr2.characters["E"]["confusions"]["I"] == 1


def test_mastery_gate_thresholds(tmp_path: Path) -> None:
    """Mastery requires >= 10 attempts and >= 90% accuracy in recent window."""
    mgr = ProgressManager(data_dir=tmp_path)

    # 9 correct in a row: 100% accuracy but < 10 attempts -> NOT mastered
    for _ in range(9):
        mgr.record_attempt("A", is_correct=True)
    assert mgr.is_mastered("A") is False

    # 10th attempt correct -> 10/10 (100%) -> MASTERED
    mgr.record_attempt("A", is_correct=True)
    assert mgr.is_mastered("A") is True

    # Add 2 mistakes -> 10 correct, 2 mistakes = 10/12 (83.3%) -> NOT mastered
    mgr.record_attempt("A", is_correct=False, typed="N")
    mgr.record_attempt("A", is_correct=False, typed="N")
    assert mgr.is_mastered("A") is False


def test_weak_character_ranking(tmp_path: Path) -> None:
    """Weak characters are sorted ascending by recent accuracy."""
    mgr = ProgressManager(data_dir=tmp_path)
    # Character 'E': 9 correct, 1 wrong (90%)
    for _ in range(9):
        mgr.record_attempt("E", is_correct=True)
    mgr.record_attempt("E", is_correct=False, typed="I")

    # Character 'T': 5 correct, 5 wrong (50%)
    for _ in range(5):
        mgr.record_attempt("T", is_correct=True)
    for _ in range(5):
        mgr.record_attempt("T", is_correct=False, typed="M")

    weak = mgr.get_weak_characters(["E", "T"])
    assert weak == ["T", "E"]


def test_corrupt_file_recovery(tmp_path: Path) -> None:
    """Corrupted save file is backed up and a fresh progress state initialized."""
    save_file = tmp_path / "progress.json"
    save_file.write_text("{ this is not valid json }", encoding="utf-8")

    mgr = ProgressManager(data_dir=tmp_path)
    assert mgr.current_stage == 1
    assert mgr.learned_characters == []
    assert mgr.last_backup_path is not None
    assert mgr.last_backup_path.exists()
