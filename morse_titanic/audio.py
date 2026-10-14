"""Audio timing math, waveform synthesis, and platform playback backends.

Pure logic functions (compute_timing, compute_farnsworth_gap, synthesize_wav)
remain strictly decoupled from playback and terminal UI.
"""

import array
import io
import math
import os
import shutil
import subprocess
import sys
import tempfile
import time
import wave
from enum import Enum
from typing import Final

from morse_titanic.config import (
    DEFAULT_AMPLITUDE,
    DEFAULT_CHAR_SPEED,
    DEFAULT_FREQUENCY,
    DEFAULT_WPM,
    FADE_SECONDS,
    LEADING_SILENCE_SECONDS,
    MAX_AMPLITUDE,
    SAMPLE_RATE,
)
from morse_titanic.morse import WORD_SEPARATOR


# Playback backends
class BackendType(Enum):
    WINSOUND = "winsound"
    WINBEEP = "winbeep"
    AFPLAY = "afplay"
    PAPLAY = "paplay"
    APLAY = "aplay"
    VISUAL = "visual"
    NONE = "none"


# Module-level tracking for active playback interruption
_ACTIVE_SUBPROCESS: subprocess.Popen | None = None
_CURRENT_BACKEND: BackendType | None = None


# --- 1. Pure Timing Math ---


def compute_farnsworth_gap(char_wpm: float, overall_wpm: float) -> float:
    """Compute Farnsworth extra gap unit duration 'ta' in seconds.

    Formula from ARRL / ITU standard:
    ta = (60.0 * char_wpm - 37.2 * overall_wpm) / (19.0 * char_wpm * overall_wpm)
    When overall_wpm == char_wpm, ta equals tc (1.2 / char_wpm).
    """
    if overall_wpm >= char_wpm:
        return 1.2 / char_wpm
    numerator = 60.0 * char_wpm - 37.2 * overall_wpm
    denominator = 19.0 * char_wpm * overall_wpm
    return max(0.0, numerator / denominator)


def compute_timing(
    patterns: list[str],
    char_wpm: float = DEFAULT_CHAR_SPEED,
    overall_wpm: float = DEFAULT_WPM,
) -> list[tuple[bool, float]]:
    """Convert a sequence of Morse patterns into tone and silence durations.

    Returns an ordered list of (is_tone, duration_seconds).
    A word boundary is represented by WORD_SEPARATOR ('/').
    """
    tc = 1.2 / char_wpm
    ta = compute_farnsworth_gap(char_wpm, overall_wpm)

    dot_dur = tc
    dash_dur = 3.0 * tc
    intra_char_gap = tc
    inter_char_gap = 3.0 * ta
    word_gap = 7.0 * ta

    events: list[tuple[bool, float]] = []

    for idx, pattern in enumerate(patterns):
        if pattern == WORD_SEPARATOR:
            # Word separator overrides preceding inter-character gap with full word gap
            if events and not events[-1][0]:
                events.pop()
            events.append((False, word_gap))
            continue

        for elem_idx, symbol in enumerate(pattern):
            if symbol == ".":
                events.append((True, dot_dur))
            elif symbol == "-":
                events.append((True, dash_dur))

            # Intra-character gap between dots/dashes in the same symbol
            if elem_idx < len(pattern) - 1:
                events.append((False, intra_char_gap))

        # Inter-character gap after each letter/digit, unless followed by word boundary
        if idx < len(patterns) - 1 and patterns[idx + 1] != WORD_SEPARATOR:
            events.append((False, inter_char_gap))

    return events


# --- 2. Pure Synthesis Math ---


def synthesize_wav(
    timing: list[tuple[bool, float]],
    frequency: float = DEFAULT_FREQUENCY,
    amplitude: float = DEFAULT_AMPLITUDE,
    sample_rate: int = SAMPLE_RATE,
    leading_silence: float = LEADING_SILENCE_SECONDS,
) -> bytes:
    """Synthesize 16-bit mono PCM WAV bytes from timing events.

    Uses raised-cosine envelope (Hann window edge) to prevent audible key clicks.
    Amplitude is hard-capped at MAX_AMPLITUDE (0.60).
    """
    safe_amplitude = min(max(0.0, amplitude), MAX_AMPLITUDE)
    max_pcm_value: Final = 32767.0
    peak_value = safe_amplitude * max_pcm_value

    fade_samples = max(1, int(FADE_SECONDS * sample_rate))
    samples = array.array("h")

    # Optional leading silence to prevent OS audio device clipping
    if leading_silence > 0.0:
        leading_count = int(round(leading_silence * sample_rate))
        samples.extend([0] * leading_count)

    phase = 0.0
    phase_increment = (2.0 * math.pi * frequency) / sample_rate

    for is_tone, duration in timing:
        count = int(round(duration * sample_rate))
        if count <= 0:
            continue

        if not is_tone:
            samples.extend([0] * count)
            continue

        # Tone with raised-cosine fade in/out
        cur_fade = min(fade_samples, count // 2)
        tone_buf = [0] * count

        for i in range(count):
            val = math.sin(phase)
            phase += phase_increment
            if phase > 2.0 * math.pi:
                phase -= 2.0 * math.pi

            envelope = 1.0
            if cur_fade > 0:
                if i < cur_fade:
                    # Raised-cosine fade in: 0.5 * (1 - cos(pi * i / cur_fade))
                    envelope = 0.5 * (1.0 - math.cos(math.pi * i / cur_fade))
                elif i >= count - cur_fade:
                    # Raised-cosine fade out
                    rem = i - (count - cur_fade)
                    envelope = 0.5 * (1.0 + math.cos(math.pi * rem / cur_fade))

            sample_int = int(round(val * peak_value * envelope))
            # Clamp to int16
            tone_buf[i] = max(-32768, min(32767, sample_int))

        samples.extend(tone_buf)

    # Trailing silence (100 ms) so final dot/dash is never clipped by device closure
    trailing_count = int(round(0.100 * sample_rate))
    samples.extend([0] * trailing_count)

    # Encode to WAV format in memory
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(samples.tobytes())

    return buf.getvalue()


# --- 3. Playback Backends & Hardware Selection ---


def detect_backend() -> BackendType:
    """Detect the most appropriate playback backend for the current platform."""
    if sys.platform == "win32":
        try:
            import winsound  # noqa: F401
            return BackendType.WINSOUND
        except ImportError:
            pass

    if sys.platform == "darwin":
        if shutil.which("afplay"):
            return BackendType.AFPLAY

    # Linux / BSD: check pulse, alsa
    if shutil.which("paplay"):
        return BackendType.PAPLAY
    if shutil.which("aplay"):
        return BackendType.APLAY

    return BackendType.VISUAL


def get_active_backend(
    requested_backend: str | None = None,
    force_visual: bool = False,
    disable_audio: bool = False,
) -> BackendType:
    """Get or initialize the current backend."""
    global _CURRENT_BACKEND
    if disable_audio:
        _CURRENT_BACKEND = BackendType.NONE
        return _CURRENT_BACKEND
    if force_visual:
        _CURRENT_BACKEND = BackendType.VISUAL
        return _CURRENT_BACKEND
    if requested_backend:
        try:
            _CURRENT_BACKEND = BackendType(requested_backend.lower())
            return _CURRENT_BACKEND
        except ValueError:
            pass
    if _CURRENT_BACKEND is None:
        _CURRENT_BACKEND = detect_backend()
    return _CURRENT_BACKEND


def set_active_backend(backend: BackendType) -> None:
    """Explicitly set the active audio backend."""
    global _CURRENT_BACKEND
    _CURRENT_BACKEND = backend


def stop_audio() -> None:
    """Stop any currently playing audio immediately."""
    global _ACTIVE_SUBPROCESS
    if _ACTIVE_SUBPROCESS is not None:
        try:
            _ACTIVE_SUBPROCESS.terminate()
            _ACTIVE_SUBPROCESS.wait(timeout=0.2)
        except Exception:
            try:
                _ACTIVE_SUBPROCESS.kill()
            except Exception:
                pass
        _ACTIVE_SUBPROCESS = None

    if sys.platform == "win32":
        try:
            import winsound
            winsound.PlaySound(None, winsound.SND_PURGE)
        except Exception:
            pass


def play_winbeep(
    timing: list[tuple[bool, float]],
    frequency: float = DEFAULT_FREQUENCY,
) -> None:
    """Direct tone playback via Windows system sound card (winsound.Beep)."""
    if sys.platform != "win32":
        return
    import winsound
    try:
        for is_tone, duration in timing:
            ms = max(1, int(round(duration * 1000)))
            if is_tone:
                winsound.Beep(int(frequency), ms)
            else:
                time.sleep(duration)
    except KeyboardInterrupt:
        stop_audio()
        raise


def play_wav_bytes(wav_data: bytes, backend: BackendType) -> bool:
    """Play WAV bytes using the specified backend.

    Returns True if successfully played, False otherwise.
    """
    global _ACTIVE_SUBPROCESS
    if backend == BackendType.NONE:
        return True

    if backend == BackendType.WINSOUND:
        try:
            import winsound
            # 1. Try memory playback
            winsound.PlaySound(wav_data, winsound.SND_MEMORY)
            return True
        except Exception:
            pass

        # 2. Fall back to temp file on Windows
        tmp_fd, tmp_path = tempfile.mkstemp(suffix=".wav")
        try:
            with os.fdopen(tmp_fd, "wb") as f:
                f.write(wav_data)
            import winsound
            winsound.PlaySound(tmp_path, winsound.SND_FILENAME)
            return True
        except Exception:
            return False
        finally:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

    if backend in (BackendType.AFPLAY, BackendType.PAPLAY, BackendType.APLAY):
        cmd = backend.value
        tmp_fd, tmp_path = tempfile.mkstemp(suffix=".wav")
        try:
            with os.fdopen(tmp_fd, "wb") as f:
                f.write(wav_data)

            _ACTIVE_SUBPROCESS = subprocess.Popen(
                [cmd, tmp_path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            _ACTIVE_SUBPROCESS.wait()
            _ACTIVE_SUBPROCESS = None
            return True
        except KeyboardInterrupt:
            stop_audio()
            raise
        except Exception:
            return False
        finally:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

    return False


def play_visual(timing: list[tuple[bool, float]]) -> None:
    """Fallback visual playback flashing dots and dashes with real timing."""
    print(" [Visual Morse]: ", end="", flush=True)
    try:
        for is_tone, duration in timing:
            if is_tone:
                symbol = "." if duration < 0.15 else "-"
                print(symbol, end="", flush=True)
            time.sleep(duration)
        print()
    except KeyboardInterrupt:
        print()
        raise


def play_morse(
    patterns: list[str],
    char_wpm: float = DEFAULT_CHAR_SPEED,
    overall_wpm: float = DEFAULT_WPM,
    frequency: float = DEFAULT_FREQUENCY,
    amplitude: float = DEFAULT_AMPLITUDE,
    force_visual: bool = False,
    disable_audio: bool = False,
) -> None:
    """High-level function to synthesize and play a list of Morse patterns."""
    timing = compute_timing(patterns, char_wpm=char_wpm, overall_wpm=overall_wpm)
    backend = get_active_backend(force_visual=force_visual, disable_audio=disable_audio)

    if backend == BackendType.NONE:
        return

    if backend == BackendType.VISUAL:
        play_visual(timing)
        return

    if backend == BackendType.WINBEEP:
        play_winbeep(timing, frequency=frequency)
        return

    wav_bytes = synthesize_wav(timing, frequency=frequency, amplitude=amplitude)
    success = play_wav_bytes(wav_bytes, backend)
    if not success:
        # If Windows sound failed, try Beep before falling back to visual
        if sys.platform == "win32":
            play_winbeep(timing, frequency=frequency)
        else:
            play_visual(timing)


def audio_check(prompt_fn) -> bool:
    """Run interactive audio check.

    Plays a clear test tone and provides options to replay, switch to
    hardware Beep (on Windows), or switch to visual fallback.
    """
    print("\n--- Audio Configuration Check ---")

    # Three clear, unmistakable dashes (Morse 'O')
    test_patterns = ["-", "-", "-"]

    while True:
        current = get_active_backend()
        print(f"Active backend: {current.value}")
        print("Playing test signal: 3 audible dashes (650 Hz)...")

        try:
            play_morse(test_patterns, overall_wpm=8, char_wpm=18)
        except Exception:
            print("[!] Audio device error.")

        print("\nAudio options:")
        print(" [Y] Yes - I heard the tone clearly")
        print(" [R] Replay test tone")
        if sys.platform == "win32":
            print(" [B] Switch to Windows hardware Beep buzzer")
        print(" [V] Switch to Visual mode (flashing)")

        choice = prompt_fn("Choice [Y/R/B/V]: ")
        if choice is None:
            return False

        c = choice.strip().upper()
        if c in ("Y", "YES", ""):
            print("[+] Audio verified.")
            return True
        elif c in ("R", "REPLAY"):
            continue
        elif c in ("B", "BEEP") and sys.platform == "win32":
            set_active_backend(BackendType.WINBEEP)
            print("[*] Backend set to Windows hardware Beep.")
            continue
        elif c in ("V", "VISUAL", "N", "NO"):
            set_active_backend(BackendType.VISUAL)
            print("[*] Switching to visual fallback mode.")
            return False
        else:
            print("[!] Unrecognized option.")
