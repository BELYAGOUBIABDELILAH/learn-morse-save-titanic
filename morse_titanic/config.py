"""Application configuration and default settings."""

import os
import sys
from pathlib import Path

# Paths
PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_DIR.parent
DATA_DIR = PROJECT_ROOT / "data"

MORSE_TABLE_PATH = DATA_DIR / "morse_table.json"
CURRICULUM_PATH = DATA_DIR / "curriculum.json"
TITANIC_MESSAGES_PATH = DATA_DIR / "titanic_messages.json"

# Audio defaults
DEFAULT_WPM = 8
DEFAULT_CHAR_SPEED = 18
DEFAULT_FREQUENCY = 650
DEFAULT_AMPLITUDE = 0.50
MAX_AMPLITUDE = 0.60
SAMPLE_RATE = 44100
FADE_SECONDS = 0.008
LEADING_SILENCE_SECONDS = 0.150

# Learning & Mastery thresholds
MIN_ATTEMPTS = 10
MASTERY_ACCURACY = 0.90
MASTERY_WINDOW = 20


def get_default_user_data_dir() -> Path:
    """Return the platform-specific directory for saving user progress."""
    app_name = "learn-morse-save-titanic"
    if sys.platform == "win32":
        base = os.environ.get("APPDATA")
        if base:
            return Path(base) / app_name
        return Path.home() / f".{app_name}"
    elif sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / app_name

    # Linux and generic POSIX
    xdg_data = os.environ.get("XDG_DATA_HOME")
    if xdg_data:
        return Path(xdg_data) / app_name
    return Path.home() / ".local" / "share" / app_name
