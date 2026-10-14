"""Main application menu loop and command-line entry point."""

import argparse
import sys
from pathlib import Path

from morse_titanic import __version__
from morse_titanic.audio import (
    audio_check,
    get_active_backend,
    stop_audio,
)
from morse_titanic.learn import run_learn_mode
from morse_titanic.progress import ProgressManager
from morse_titanic.titanic import (
    display_sources_and_limitations,
    run_titanic_simulation,
)
from morse_titanic.ui import (
    BOLD,
    CYAN,
    configure_color,
    print_header,
    print_info,
    print_success,
    print_warning,
    safe_input,
    style,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        prog="morse-titanic",
        description=(
            "Learn International Morse code and decode "
            "historical Titanic wireless transmissions."
        ),
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable ANSI color output.",
    )
    parser.add_argument(
        "--no-audio",
        action="store_true",
        help="Disable audio output entirely.",
    )
    parser.add_argument(
        "--visual",
        action="store_true",
        help="Force visual Morse flash fallback instead of audio.",
    )
    parser.add_argument(
        "--backend",
        type=str,
        default=None,
        choices=["winsound", "winbeep", "afplay", "paplay", "aplay", "visual", "none"],
        help="Force specific audio playback backend.",
    )
    parser.add_argument(
        "--wpm",
        type=int,
        default=8,
        help="Overall Morse playback speed in words per minute (default: 8).",
    )
    parser.add_argument(
        "--freq",
        type=int,
        default=650,
        help="Tone frequency in Hertz (default: 650).",
    )
    parser.add_argument(
        "--data-dir",
        type=str,
        default=None,
        help="Override path to directory for user progress data.",
    )
    parser.add_argument(
        "--reset-progress",
        action="store_true",
        help="Reset user progress data.",
    )
    return parser.parse_args(argv)


def display_main_menu(backend_name: str) -> None:
    """Print the atmospheric 1912 wireless station menu."""
    print_header("LEARN MORSE, SAVE TITANIC", "WIRELESS STATION -- 1912")
    print(f" {style('[1]', CYAN, BOLD)} Learn Morse")
    print(f" {style('[2]', CYAN, BOLD)} Titanic Transmissions")
    print(f" {style('[3]', CYAN, BOLD)} My Progress")
    print(f" {style('[4]', CYAN, BOLD)} Sources & Limitations")
    print(f" {style('[T]', CYAN, BOLD)} Audio Check [Current: {backend_name}]")
    print(f" {style('[0]', CYAN, BOLD)} Exit")
    print()


def display_progress_screen(progress: ProgressManager) -> None:
    """Display player's learning progress and weak signals."""
    print_header("OPERATOR LOGBOOK", "PROGRESS & SIGNAL ACCURACY")
    print(f" Current Stage:     {progress.current_stage}")
    print(f" Signals Mastered: {len(progress.learned_characters)}")
    if progress.learned_characters:
        print(f" Mastered List:    {', '.join(progress.learned_characters)}")
    print()

    if not progress.characters:
        print_info("No drill attempts logged yet. Start with [1] Learn Morse.")
    else:
        print(" Signal  Attempts  Overall Acc  Recent Acc  Common Mistake")
        print(" ------  --------  -----------  ----------  --------------")
        for char, stats in sorted(progress.characters.items()):
            attempts = stats.get("attempts", 0)
            overall = int(progress.get_accuracy(char) * 100)
            recent = int(progress.get_recent_accuracy(char) * 100)
            confusions = stats.get("confusions", {})
            mistake = max(confusions.items(), key=lambda x: x[1])[0] if confusions else "-"
            print(f"   {char:<4}  {attempts:<8}  {overall:>9}%  {recent:>8}%  {mistake}")
    print()
    safe_input("Press Enter to return to main menu...")


def menu_loop(args: argparse.Namespace) -> int:
    """Run the main interactive menu loop."""
    configure_color(force_disabled=args.no_color)
    backend = get_active_backend(
        requested_backend=args.backend,
        force_visual=args.visual,
        disable_audio=args.no_audio,
    )

    data_dir = Path(args.data_dir) if args.data_dir else None
    progress = ProgressManager(data_dir=data_dir)

    if progress.last_backup_path:
        print_warning(
            f"Corrupt or incompatible save file was backed up to:\n"
            f"  {progress.last_backup_path}\n"
            f"A fresh logbook has been created."
        )

    if args.reset_progress:
        confirm = safe_input("Confirm reset of all progress data? [y/N]: ")
        if confirm and confirm.strip().lower() in ("y", "yes"):
            progress.reset()
            print_success("Progress logbook has been reset.")
        else:
            print_info("Reset canceled.")

    while True:
        display_main_menu(backend.value)
        choice = safe_input("Select an option [0-4, T]: ")

        if choice is None or choice == "0":
            stop_audio()
            print("\nStation log closed. Signal terminated.\n")
            return 0

        choice_upper = choice.upper()
        if choice_upper == "1":
            run_learn_mode(
                progress,
                wpm=args.wpm,
                frequency=args.freq,
                force_visual=(backend.value == "visual"),
                disable_audio=(backend.value == "none"),
            )
        elif choice_upper == "2":
            run_titanic_simulation(
                progress,
                wpm=args.wpm,
                frequency=args.freq,
                force_visual=(backend.value == "visual"),
                disable_audio=(backend.value == "none"),
            )
        elif choice_upper == "3":
            display_progress_screen(progress)
        elif choice_upper == "4":
            display_sources_and_limitations()
        elif choice_upper == "T":
            audio_check(safe_input)
            backend = get_active_backend()
            safe_input("Press Enter to return to menu...")
        else:
            print_info("Invalid option. Enter a valid menu selection.")


def main(argv: list[str] | None = None) -> int:
    """Application entry point."""
    args = parse_args(argv)
    try:
        return menu_loop(args)
    except KeyboardInterrupt:
        stop_audio()
        print("\nSession interrupted. Exiting.\n")
        return 0


if __name__ == "__main__":
    sys.exit(main())
