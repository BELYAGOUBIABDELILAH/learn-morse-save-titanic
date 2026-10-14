"""Titanic historical simulation mode and sources/limitations viewer (titanic.py)."""

from morse_titanic.audio import play_morse
from morse_titanic.config import (
    DEFAULT_CHAR_SPEED,
    DEFAULT_FREQUENCY,
    DEFAULT_WPM,
)
from morse_titanic.dataset import TitanicMessage, load_messages
from morse_titanic.grading import grade
from morse_titanic.morse import encode
from morse_titanic.progress import ProgressManager
from morse_titanic.ui import (
    BOLD,
    CYAN,
    DIM,
    print_error,
    print_header,
    print_info,
    print_success,
    print_warning,
    safe_input,
    style,
)

LIMITATION_NOTICE = (
    "Titanic's own wireless logs did not survive the sinking. Messages are reconstructed\n"
    "from other ships' logs, inquiry testimony, and surviving telegrams. Wording, order,\n"
    "and timestamps can differ between historical sources, and ship time, GMT, and\n"
    "New York time are easy to confuse. Audio transmissions are generated Morse reconstructions,\n"
    "not original 1912 recordings."
)


def display_sources_and_limitations() -> None:
    """Display educational purpose, historical context, and limitations."""
    print_header("LEARNING PROJECT & HISTORICAL CONTEXT", "EDUCATIONAL NOTICE")
    print("This project is designed strictly for learning and educational purposes.")
    print()
    print("Historical Context:")
    print("Titanic's wireless logs were lost during the sinking. The transmissions")
    print("featured in this simulator are reconstructions derived from historical inquiry")
    print("records and surviving station reports. Audio signals are generated Morse")
    print("reconstructions intended to practice ear-training on authentic historical messages.")
    print()
    safe_input("Press Enter to return to main menu...")


def run_single_transmission(
    msg: TitanicMessage,
    progress: ProgressManager,
    wpm: int = DEFAULT_WPM,
    char_wpm: int = DEFAULT_CHAR_SPEED,
    frequency: int = DEFAULT_FREQUENCY,
    force_visual: bool = False,
    disable_audio: bool = False,
) -> bool:
    hdr_title = f"TRANSMISSION #{msg.order}: {msg.event.upper()}"
    print_header(hdr_title, f"Status: {msg.verification_status}")
    print(f" Date & Time: {msg.date or 'Unknown'} {msg.time.value or ''} ({msg.time.reference})")
    print(f" From:        {msg.sender or 'Unknown'}")
    print(f" To:          {msg.recipient or 'All Stations'}")
    print(f" Context:     {msg.context}")
    print(f" {style('[Historical Transcript Reconstruction | Audio: Generated Morse]', DIM)}")
    print()

    # Readiness check
    learned_set = set(progress.learned_characters)
    missing = msg.required_characters - learned_set
    if missing:
        missing_str = ", ".join(sorted(missing))
        print_warning(f"This message requires characters you have not learned yet: {missing_str}")
        print(" [C] Continue anyway")
        print(" [L] Return to Learn Morse to practice them")
        print(" [Q] Back to menu")
        choice = safe_input("Choice [C/L/Q]: ")
        if choice is None or choice.strip().upper() in ("Q", "L"):
            return False

    current_wpm = wpm

    # Play and decode segment by segment
    total_segments = len(msg.segments)
    for seg_idx, segment in enumerate(msg.segments, start=1):
        print()
        print(style(f"--- Segment {seg_idx} of {total_segments} ---", CYAN))
        print_info("Receiving Morse signal...")

        pattern_list = encode(segment)
        play_morse(
            pattern_list,
            char_wpm=char_wpm,
            overall_wpm=current_wpm,
            frequency=frequency,
            force_visual=force_visual,
            disable_audio=disable_audio,
        )

        while True:
            prompt = f"Decode segment {seg_idx}/{total_segments} (:r replay, :s skip, :q quit): "
            response = safe_input(prompt)
            if response is None or response == ":q":
                return False

            if response == ":r":
                print_info("Replaying segment...")
                play_morse(
                    pattern_list,
                    char_wpm=char_wpm,
                    overall_wpm=current_wpm,
                    frequency=frequency,
                    force_visual=force_visual,
                    disable_audio=disable_audio,
                )
                continue

            if response == ":s":
                print_info(f"Skipped segment. Expected: '{segment}'")
                break

            res = grade(segment, response)
            if res.exact:
                print_success(f"Segment verified: '{segment}'")
                break
            else:
                print_warning(f"Incomplete. {res.diff_summary}")
                retry = safe_input("Try this segment again? [Y/n]: ")
                if retry and retry.strip().lower() in ("n", "no"):
                    break
                # Replay for retry
                play_morse(
                    pattern_list,
                    char_wpm=char_wpm,
                    overall_wpm=current_wpm,
                    frequency=frequency,
                    force_visual=force_visual,
                    disable_audio=disable_audio,
                )

    # Post-attempt historical reveal
    print()
    print_header("ARCHIVAL RECORD REVEAL", f"Signal ID: {msg.id}")
    print(f" Source Transcript:   {style(msg.message, BOLD)}")
    print(f" Transcription Type:  {msg.transcription_type}")
    print(f" Evidence Notes:      {msg.evidence_notes}")
    print()

    if msg.id not in progress.completed_messages:
        progress.completed_messages.append(msg.id)
        progress.save()

    print_success(f"Transmission #{msg.order} successfully logged in station records.")
    safe_input("Press Enter to continue...")
    return True


def run_titanic_simulation(
    progress: ProgressManager,
    wpm: int = DEFAULT_WPM,
    char_wpm: int = DEFAULT_CHAR_SPEED,
    frequency: int = DEFAULT_FREQUENCY,
    force_visual: bool = False,
    disable_audio: bool = False,
) -> None:
    """Run Titanic simulation experience."""
    messages, errors = load_messages()
    if errors:
        print_error("Dataset validation error:")
        for e in errors:
            print(f"  - {e}")
        safe_input("Press Enter to return to menu...")
        return

    if not messages:
        # Zero verified messages in production dataset
        print_header("TITANIC TRANSMISSIONS", "HISTORICAL RECONSTRUCTION")
        print(LIMITATION_NOTICE)
        print()
        print_info("No verified transmissions are currently activated for play.")
        print("In accordance with station ground rules, all historical transmissions")
        print("remain strictly pending until verified against primary inquiry records.")
        print()
        dev_choice = safe_input("Preview pending candidate records in dev mode? [y/N]: ")
        if dev_choice and dev_choice.strip().lower() in ("y", "yes"):
            pending_messages, p_errors = load_messages(allow_unverified=True)
            if p_errors:
                print_error("Candidate validation error:")
                for e in p_errors:
                    print(f"  - {e}")
                safe_input("Press Enter to return to menu...")
                return
            messages = pending_messages
        else:
            return

    for msg in messages:
        completed = run_single_transmission(
            msg,
            progress,
            wpm=wpm,
            char_wpm=char_wpm,
            frequency=frequency,
            force_visual=force_visual,
            disable_audio=disable_audio,
        )
        if not completed:
            break
