"""Terminal UI formatting, colors, and robust input handling."""

import os
import sys
from typing import Final

# Check color capability
_COLOR_ENABLED: bool = True


def configure_color(force_disabled: bool = False) -> None:
    """Configure whether ANSI colors are emitted."""
    global _COLOR_ENABLED
    if force_disabled or os.environ.get("NO_COLOR") is not None:
        _COLOR_ENABLED = False
        return

    # Check if stdout is a terminal
    is_tty = hasattr(sys.stdout, "isatty") and sys.stdout.isatty()
    if not is_tty:
        _COLOR_ENABLED = False
        return

    # Enable Virtual Terminal Processing on Windows if possible
    if sys.platform == "win32":
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            handle = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
            mode = ctypes.c_ulong()
            if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
                # ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
                kernel32.SetConsoleMode(handle, mode.value | 0x0004)
                _COLOR_ENABLED = True
            else:
                _COLOR_ENABLED = False
        except Exception:
            _COLOR_ENABLED = False
    else:
        _COLOR_ENABLED = True


# ANSI codes
RESET: Final = "\033[0m"
BOLD: Final = "\033[1m"
DIM: Final = "\033[2m"
CYAN: Final = "\033[36m"
GREEN: Final = "\033[32m"
YELLOW: Final = "\033[33m"
RED: Final = "\033[31m"
MAGENTA: Final = "\033[35m"


def style(text: str, *codes: str) -> str:
    """Apply ANSI codes if coloring is active."""
    if not _COLOR_ENABLED or not codes:
        return text
    return "".join(codes) + text + RESET


def print_header(title: str, subtitle: str | None = None) -> None:
    """Print a standardized station header."""
    width = 50
    border = "=" * width
    print()
    print(style(border, CYAN, BOLD))
    print(style(title.center(width), CYAN, BOLD))
    if subtitle:
        print(style(subtitle.center(width), DIM))
    print(style(border, CYAN, BOLD))
    print()


def safe_input(prompt: str = "> ") -> str | None:
    """Read a line of input safely.

    Returns the stripped input string, or None if interrupted via Ctrl+C or EOF.
    """
    try:
        raw = input(prompt)
        return raw.strip()
    except (KeyboardInterrupt, EOFError):
        print()
        return None


def print_error(message: str) -> None:
    """Print an error message."""
    print(style(f"[!] {message}", RED, BOLD))


def print_success(message: str) -> None:
    """Print a success message."""
    print(style(f"[+] {message}", GREEN))


def print_info(message: str) -> None:
    """Print an informational message."""
    print(style(f"[*] {message}", CYAN))


def print_warning(message: str) -> None:
    """Print a warning message."""
    print(style(f"[-] {message}", YELLOW))
