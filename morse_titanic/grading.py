"""Answer normalization, comparison, and diff feedback (grading.py).

Pure logic module: strictly independent of UI and audio.
"""

import difflib
from dataclasses import dataclass


@dataclass(frozen=True)
class GradeResult:
    """Structured result of grading an answer against historical/expected text."""

    exact: bool
    score: float
    expected_normalized: str
    actual_normalized: str
    diff_summary: str


def normalize(text: str) -> str:
    """Normalize text for consistent grading.

    - Convert to uppercase
    - Strip surrounding and collapse internal whitespace
    - Normalize dash variations (-, –, —, −) to '-'
    - Normalize quotation variations (‘, ’, ') to single quote, (“,”, ") to double quote
    - Retain punctuation (periods, commas, slashes, numbers) intact.
    """
    if not text:
        return ""

    # Whitespace collapse
    collapsed = " ".join(text.split()).upper()

    # Normalize dashes
    dash_variants = {"–": "-", "—": "-", "−": "-"}
    for var, standard in dash_variants.items():
        collapsed = collapsed.replace(var, standard)

    # Normalize single quotes
    quote_variants = {"‘": "'", "’": "'", "`": "'"}
    for var, standard in quote_variants.items():
        collapsed = collapsed.replace(var, standard)

    # Normalize double quotes
    double_quote_variants = {"“": '"', "”": '"'}
    for var, standard in double_quote_variants.items():
        collapsed = collapsed.replace(var, standard)

    return collapsed


def grade(expected: str, actual: str) -> GradeResult:
    """Grade actual user input against expected text.

    Uses difflib to compare strings and produce constructive, non-discouraging feedback.
    """
    exp_norm = normalize(expected)
    act_norm = normalize(actual)

    if exp_norm == act_norm:
        return GradeResult(
            exact=True,
            score=1.0,
            expected_normalized=exp_norm,
            actual_normalized=act_norm,
            diff_summary="Exact match.",
        )

    matcher = difflib.SequenceMatcher(None, exp_norm, act_norm)
    score = matcher.ratio()

    # Generate constructive diff summary
    exp_words = exp_norm.split()
    act_words = act_norm.split()

    if len(exp_words) > 1 or len(act_words) > 1:
        # Multi-word comparison
        word_matcher = difflib.SequenceMatcher(None, exp_words, act_words)
        matching_words = sum(
            match.size for match in word_matcher.get_matching_blocks()
        )
        total_exp = max(1, len(exp_words))
        diff_summary = f"{matching_words} of {total_exp} words matched."
    else:
        # Single-character or single-word comparison
        matching_chars = sum(
            block.size for block in matcher.get_matching_blocks()
        )
        total_chars = max(1, len(exp_norm))
        diff_summary = (
            f"{matching_chars} of {total_chars} characters matched. "
            f"Expected '{exp_norm}', got '{act_norm}'."
        )

    return GradeResult(
        exact=False,
        score=score,
        expected_normalized=exp_norm,
        actual_normalized=act_norm,
        diff_summary=diff_summary,
    )
