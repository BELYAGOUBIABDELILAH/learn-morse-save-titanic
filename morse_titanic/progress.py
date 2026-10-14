"""User progress persistence, atomic writes, and character mastery tracking (progress.py).

Pure logic module: independent of UI and audio.
"""

import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any

from morse_titanic.config import (
    MASTERY_ACCURACY,
    MASTERY_WINDOW,
    MIN_ATTEMPTS,
    get_default_user_data_dir,
)

SCHEMA_VERSION = 1


class ProgressManager:
    """Manages player learning progress with atomic writes and schema safety."""

    def __init__(self, data_dir: Path | None = None) -> None:
        self.data_dir = data_dir or get_default_user_data_dir()
        self.file_path = self.data_dir / "progress.json"
        self.schema_version = SCHEMA_VERSION
        self.current_stage: int = 1
        self.learned_characters: list[str] = []
        self.characters: dict[str, dict[str, Any]] = {}
        self.completed_messages: list[str] = []
        self.last_backup_path: Path | None = None
        self.load()

    def _init_character_entry(self, char: str) -> None:
        if char not in self.characters:
            self.characters[char] = {
                "attempts": 0,
                "correct": 0,
                "recent": [],
                "confusions": {},
            }

    def load(self) -> None:
        """Load user progress from disk or initialize fresh state on error."""
        if not self.file_path.exists():
            return

        try:
            with open(self.file_path, encoding="utf-8") as f:
                data = json.load(f)

            if data.get("schema_version") != SCHEMA_VERSION:
                self._backup_corrupt_file()
                return

            self.current_stage = int(data.get("current_stage", 1))
            self.learned_characters = list(data.get("learned_characters", []))
            self.characters = dict(data.get("characters", {}))
            self.completed_messages = list(data.get("completed_messages", []))
        except Exception:
            self._backup_corrupt_file()

    def _backup_corrupt_file(self) -> None:
        """Backup an unreadable or incompatible save file and start fresh."""
        timestamp = int(time.time())
        backup_path = self.data_dir / f"progress.json.bak.{timestamp}"
        try:
            if self.file_path.exists():
                os.replace(self.file_path, backup_path)
                self.last_backup_path = backup_path
        except Exception:
            pass

        self.current_stage = 1
        self.learned_characters = []
        self.characters = {}
        self.completed_messages = []

    def save(self) -> None:
        """Atomically save progress to disk using a temporary file."""
        self.data_dir.mkdir(parents=True, exist_ok=True)

        payload = {
            "schema_version": self.schema_version,
            "current_stage": self.current_stage,
            "learned_characters": self.learned_characters,
            "characters": self.characters,
            "completed_messages": self.completed_messages,
        }

        # Write to temporary file in the same directory for atomic replace
        fd, tmp_path_str = tempfile.mkstemp(dir=self.data_dir, prefix="prog_tmp_", suffix=".json")
        tmp_path = Path(tmp_path_str)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
                f.flush()
                os.fsync(f.fileno())

            os.replace(tmp_path, self.file_path)
        except Exception:
            if tmp_path.exists():
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
            raise

    def record_attempt(self, char: str, is_correct: bool, typed: str = "") -> None:
        """Record a single quiz attempt for a character."""
        self._init_character_entry(char)
        entry = self.characters[char]
        entry["attempts"] += 1
        if is_correct:
            entry["correct"] += 1

        recent = entry.get("recent", [])
        recent.append(is_correct)
        if len(recent) > MASTERY_WINDOW:
            recent.pop(0)
        entry["recent"] = recent

        if not is_correct and typed and typed != char:
            confusions = entry.get("confusions", {})
            confusions[typed] = confusions.get(typed, 0) + 1
            entry["confusions"] = confusions

    def is_mastered(self, char: str) -> bool:
        """Check if character meets the mastery gate criteria."""
        entry = self.characters.get(char)
        if not entry:
            return False

        if entry["attempts"] < MIN_ATTEMPTS:
            return False

        recent = entry.get("recent", [])
        if len(recent) < MIN_ATTEMPTS:
            return False

        recent_accuracy = sum(1 for x in recent if x) / len(recent)
        return recent_accuracy >= MASTERY_ACCURACY

    def unlock_character(self, char: str) -> None:
        """Add character to learned set if not already present."""
        if char not in self.learned_characters:
            self.learned_characters.append(char)

    def get_accuracy(self, char: str) -> float:
        """Return overall accuracy for a character (0.0 to 1.0)."""
        entry = self.characters.get(char)
        if not entry or entry["attempts"] == 0:
            return 0.0
        return entry["correct"] / entry["attempts"]

    def get_recent_accuracy(self, char: str) -> float:
        """Return recent window accuracy for a character (0.0 to 1.0)."""
        entry = self.characters.get(char)
        if not entry or not entry.get("recent"):
            return 0.0
        recent = entry["recent"]
        return sum(1 for x in recent if x) / len(recent)

    def get_weak_characters(self, pool: list[str] | None = None) -> list[str]:
        """Return characters sorted from lowest recent accuracy to highest."""
        candidates = pool if pool is not None else self.learned_characters
        if not candidates:
            return []

        # Sort by (recent_accuracy, total_accuracy)
        return sorted(
            candidates,
            key=lambda c: (self.get_recent_accuracy(c), self.get_accuracy(c)),
        )

    def reset(self) -> None:
        """Reset progress in memory and remove saved file."""
        self.current_stage = 1
        self.learned_characters = []
        self.characters = {}
        self.completed_messages = []
        if self.file_path.exists():
            try:
                os.remove(self.file_path)
            except OSError:
                pass
