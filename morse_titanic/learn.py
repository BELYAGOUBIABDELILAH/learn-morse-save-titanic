"""Interactive learning mode with staged curriculum and mastery gate (learn.py)."""

import json
import random
from pathlib import Path

from morse_titanic.audio import play_morse
from morse_titanic.config import (
    CURRICULUM_PATH,
    DEFAULT_CHAR_SPEED,
    DEFAULT_FREQUENCY,
    DEFAULT_WPM,
)
from morse_titanic.grading import grade
from morse_titanic.morse import get_table
from morse_titanic.progress import ProgressManager
from morse_titanic.ui import (
    BOLD,
    CYAN,
    print_error,
    print_header,
    print_info,
    print_success,
    print_warning,
    safe_input,
    style,
)


def pattern_phonetic(pattern: str) -> str:
    """Convert pattern to rhythmic verbal description (e.g. '.-' -> 'dit dah')."""
    elements = []
    total = len(pattern)
    for idx, sym in enumerate(pattern):
        if sym == ".":
            elements.append("dit" if idx < total - 1 else "dit")
        elif sym == "-":
            elements.append("dah")
    return " ".join(elements)


def load_curriculum(path: Path | None = None) -> list[dict]:
    """Load curriculum stages from JSON file."""
    c_path = path or CURRICULUM_PATH
    with open(c_path, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("stages", [])


def run_learn_mode(
    progress: ProgressManager,
    wpm: int = DEFAULT_WPM,
    char_wpm: int = DEFAULT_CHAR_SPEED,
    frequency: int = DEFAULT_FREQUENCY,
    force_visual: bool = False,
    disable_audio: bool = False,
) -> None:
    """Run interactive Morse learning session."""
    stages = load_curriculum()
    if not stages:
        print_error("No curriculum found.")
        return

    table = get_table()
    current_wpm = wpm
    drill_counter = 0

    while True:
        # Determine current stage and character
        stage_idx = progress.current_stage - 1
        if stage_idx >= len(stages):
            print_header("CURRICULUM COMPLETE", "All signals mastered")
            print_success("You have mastered all characters in the curriculum!")
            safe_input("Press Enter to return to main menu...")
            return

        stage_data = stages[stage_idx]
        stage_num = stage_data.get("stage", 1)
        stage_title = stage_data.get("title", "")
        stage_chars = stage_data.get("characters", [])

        # Find first unmastered character in current stage
        target_char = None
        for ch in stage_chars:
            if not progress.is_mastered(ch):
                target_char = ch
                break

        if target_char is None:
            # Advance to next stage
            progress.current_stage += 1
            progress.save()
            print_success(
                f"Stage {stage_num} complete! Advancing to Stage {progress.current_stage}."
            )
            continue

        target_pattern = table.char_to_pattern.get(target_char, "")

        # Introduce target character if not yet attempted
        stats = progress.characters.get(target_char, {})
        if stats.get("attempts", 0) == 0:
            print_header(f"STAGE {stage_num}: {stage_title.upper()}", f"Signal: {target_char}")
            phonetic = pattern_phonetic(target_pattern)
            print(f" Signal:  {style(target_char, CYAN, BOLD)}")
            print(f" Pattern: {style(target_pattern, BOLD)} ({phonetic})")
            print()
            print_info("Playing reference tone...")
            play_morse(
                [target_pattern],
                char_wpm=char_wpm,
                overall_wpm=current_wpm,
                frequency=frequency,
                force_visual=force_visual,
                disable_audio=disable_audio,
            )
            print()
            cmd = safe_input("Press Enter to begin practice drills (or :r replay, :q menu): ")
            if cmd is None or cmd.strip() == ":q":
                return
            if cmd.strip() == ":r":
                play_morse(
                    [target_pattern],
                    char_wpm=char_wpm,
                    overall_wpm=current_wpm,
                    frequency=frequency,
                    force_visual=force_visual,
                    disable_audio=disable_audio,
                )

        # Decide whether to test the target character or run an interleaved review
        drill_counter += 1
        active_char = target_char
        is_review = False

        learned_others = [c for c in progress.learned_characters if c != target_char]
        if drill_counter % 3 == 0 and learned_others:
            # Interleave review: pick from weak characters
            weak_pool = progress.get_weak_characters(pool=learned_others)
            active_char = (
                random.choice(weak_pool[:3]) if weak_pool else random.choice(learned_others)
            )
            is_review = True

        active_pattern = table.char_to_pattern.get(active_char, "")

        # Play quiz tone
        print()
        if is_review:
            print(style(f"[Review Drill: Stage 1-{stage_num}]", CYAN))
        else:
            acc = int(progress.get_recent_accuracy(target_char) * 100)
            attempts = stats.get("attempts", 0)
            status_line = f"[Target: '{target_char}' | Attempts: {attempts} | Accuracy: {acc}%]"
            print(style(status_line, CYAN))

        print_info("Playing signal...")
        play_morse(
            [active_pattern],
            char_wpm=char_wpm,
            overall_wpm=current_wpm,
            frequency=frequency,
            force_visual=force_visual,
            disable_audio=disable_audio,
        )

        # Input loop for this drill
        while True:
            response = safe_input("Decode signal (:r replay, :h hint, :s skip, :q menu): ")
            if response is None or response == ":q":
                progress.save()
                return

            if response == ":r":
                print_info("Replaying...")
                play_morse(
                    [active_pattern],
                    char_wpm=char_wpm,
                    overall_wpm=current_wpm,
                    frequency=frequency,
                    force_visual=force_visual,
                    disable_audio=disable_audio,
                )
                continue

            if response == ":h":
                elem_count = len(active_pattern)
                print_info(f"Hint: Signal contains {elem_count} elements.")
                continue

            if response == ":s":
                print_info(f"Skipped. The signal was '{active_char}' ({active_pattern}).")
                break

            if response.startswith(":speed"):
                parts = response.split()
                if len(parts) == 2 and parts[1].isdigit():
                    current_wpm = max(4, min(30, int(parts[1])))
                    print_info(f"Speed updated to {current_wpm} WPM.")
                    play_morse(
                        [active_pattern],
                        char_wpm=char_wpm,
                        overall_wpm=current_wpm,
                        frequency=frequency,
                        force_visual=force_visual,
                        disable_audio=disable_audio,
                    )
                else:
                    print_warning("Usage: :speed <number>")
                continue

            # Grade the answer
            res = grade(active_char, response)
            if res.exact:
                print_success(f"Correct! '{active_char}' ({active_pattern})")
                progress.record_attempt(active_char, is_correct=True)
            else:
                print_warning(
                    f"Incorrect. Expected '{active_char}' ({active_pattern}), got '{response}'."
                )
                progress.record_attempt(active_char, is_correct=False, typed=response.upper())

            progress.save()

            # Check mastery of target character
            if progress.is_mastered(target_char):
                print()
                print_success(f"Mastery gate cleared for '{target_char}'! Signal mastered.")
                progress.unlock_character(target_char)
                progress.save()
            break
