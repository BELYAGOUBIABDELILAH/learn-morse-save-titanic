"""Tests for timing, waveform synthesis, and audio backends (audio.py)."""

import io
import math
import wave
from unittest.mock import patch

from morse_titanic.audio import (
    BackendType,
    compute_farnsworth_gap,
    compute_timing,
    detect_backend,
    play_wav_bytes,
    synthesize_wav,
)
from morse_titanic.morse import WORD_SEPARATOR, encode


def test_farnsworth_gap_hand_computed() -> None:
    """Verify Farnsworth extra gap unit matches hand-calculated value."""
    # For C=18, S=8:
    # num = 60*18 - 37.2*8 = 1080 - 297.6 = 782.4
    # den = 19*18*8 = 2736
    # ta = 782.4 / 2736 ~= 0.285964912...
    expected = (60.0 * 18.0 - 37.2 * 8.0) / (19.0 * 18.0 * 8.0)
    actual = compute_farnsworth_gap(18.0, 8.0)
    assert math.isclose(actual, expected, rel_tol=1e-6)
    assert math.isclose(actual, 0.2859649, rel_tol=1e-5)


def test_farnsworth_equals_standard_when_speeds_match() -> None:
    """When overall speed equals character speed, ta must equal tc = 1.2 / C."""
    c_speed = 15.0
    tc = 1.2 / c_speed
    ta = compute_farnsworth_gap(char_wpm=c_speed, overall_wpm=c_speed)
    assert math.isclose(ta, tc, rel_tol=1e-6)


def test_paris_standard_timing_is_exactly_50_units() -> None:
    """Standard word PARIS + trailing word gap must sum to exactly 50 units."""
    wpm = 10.0
    tc = 1.2 / wpm  # 0.12 seconds
    patterns = encode("PARIS")
    # Append trailing word gap per standard PARIS definition
    patterns.append(WORD_SEPARATOR)

    timing = compute_timing(patterns, char_wpm=wpm, overall_wpm=wpm)

    total_duration = sum(dur for _, dur in timing)
    expected_duration = 50.0 * tc
    assert math.isclose(total_duration, expected_duration, rel_tol=1e-6)

    # Count unit ratios
    tone_durations = [dur for is_tone, dur in timing if is_tone]
    silence_durations = [dur for is_tone, dur in timing if not is_tone]

    # Dots must be 1 unit, dashes must be 3 units
    for dur in tone_durations:
        assert math.isclose(dur, tc, rel_tol=1e-5) or math.isclose(dur, 3.0 * tc, rel_tol=1e-5)

    # Intra-char gaps 1, inter-char gaps 3, word gap 7
    for dur in silence_durations:
        units = dur / tc
        assert round(units) in (1, 3, 7)


def test_farnsworth_preserves_tone_durations() -> None:
    """When overall speed S < C, tone durations are identical to character speed C."""
    char_wpm = 20.0
    slow_overall = 8.0

    timing_fast = compute_timing([".-", "-."], char_wpm=char_wpm, overall_wpm=char_wpm)
    timing_farns = compute_timing([".-", "-."], char_wpm=char_wpm, overall_wpm=slow_overall)

    tones_fast = [dur for is_tone, dur in timing_fast if is_tone]
    tones_farns = [dur for is_tone, dur in timing_farns if is_tone]

    # Tone durations must be identical
    assert len(tones_fast) == len(tones_farns)
    for t1, t2 in zip(tones_fast, tones_farns, strict=False):
        assert math.isclose(t1, t2, rel_tol=1e-6)

    # Gaps in Farnsworth must be longer
    gaps_fast = [dur for is_tone, dur in timing_fast if not is_tone]
    gaps_farns = [dur for is_tone, dur in timing_farns if not is_tone]
    assert len(gaps_fast) == len(gaps_farns)
    for g1, g2 in zip(gaps_fast, gaps_farns, strict=False):
        assert g2 >= g1


def test_synthesis_wav_valid_and_amplitude_capped() -> None:
    """Synthesized WAV must have valid header, correct channels, and capped amplitude."""
    timing = [(True, 0.1), (False, 0.05), (True, 0.2)]
    # Request excessive amplitude (1.0), which should be hard-capped at 0.60
    wav_bytes = synthesize_wav(
        timing,
        frequency=650.0,
        amplitude=1.0,
        sample_rate=44100,
        leading_silence=0.05,
    )

    assert wav_bytes.startswith(b"RIFF")

    # Read back wave parameters
    with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
        assert wf.getnchannels() == 1
        assert wf.getsampwidth() == 2  # 16-bit
        assert wf.getframerate() == 44100
        frames = wf.readframes(wf.getnframes())

    # Check maximum amplitude in samples
    import array
    samples = array.array("h")
    samples.frombytes(frames)

    max_val = max(abs(s) for s in samples)
    # 0.60 * 32767 = 19660.2 -> allow slight rounding tolerance
    assert max_val <= 19670, f"Peak amplitude {max_val} exceeded 0.60 limit"
    assert min(samples) >= -32768
    assert max(samples) <= 32767


def test_backend_detection_mocked() -> None:
    """Assert backend detection chooses the expected backend per platform."""
    with patch("sys.platform", "win32"), patch.dict("sys.modules", {"winsound": True}):
        assert detect_backend() == BackendType.WINSOUND

    with patch("sys.platform", "darwin"), patch("shutil.which", return_value="/usr/bin/afplay"):
        assert detect_backend() == BackendType.AFPLAY

    with (
        patch("sys.platform", "linux"),
        patch("shutil.which", side_effect=lambda cmd: cmd == "paplay"),
    ):
        assert detect_backend() == BackendType.PAPLAY

    with patch("sys.platform", "linux"), patch("shutil.which", return_value=None):
        assert detect_backend() == BackendType.VISUAL


def test_play_wav_bytes_handles_none_backend() -> None:
    """BackendType.NONE immediately returns True without playing."""
    assert play_wav_bytes(b"dummy", BackendType.NONE) is True
