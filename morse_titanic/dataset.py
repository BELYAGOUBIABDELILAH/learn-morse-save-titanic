"""Historical Titanic dataset loading, segmentation, and schema validation (dataset.py).

Pure logic module: independent of UI and audio.
"""

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from morse_titanic.config import TITANIC_MESSAGES_PATH
from morse_titanic.grading import normalize
from morse_titanic.morse import MorseTable, get_table

SCHEMA_VERSION = 1
PLACEHOLDER_PATTERN = re.compile(r"\b(TODO|PLACEHOLDER|XXX|LOREM)\b", re.IGNORECASE)
VALID_TIME_REFS = {"ship_time", "gmt", "new_york_time", "unknown"}
VALID_TRANSCRIPTION_TYPES = {"direct", "normalized", "reconstructed"}
VALID_STATUSES = {"pending", "verified", "disputed"}


@dataclass(frozen=True)
class TitanicSource:
    title: str
    url: str
    publisher: str
    accessed: str


@dataclass(frozen=True)
class TitanicTime:
    value: str | None
    reference: str


@dataclass(frozen=True)
class TitanicMessage:
    id: str
    order: int
    event: str
    message: str
    normalized_answer: str
    date: str | None
    time: TitanicTime
    sender: str | None
    recipient: str | None
    transcription_type: str
    context: str
    evidence_notes: str
    sources: list[TitanicSource]
    verification_status: str
    verified_by: str | None
    verified_on: str | None
    segments: list[str]
    required_characters: set[str]


def compute_segments(text: str, max_words: int = 4) -> list[str]:
    """Split message into digestible playable segments of at most max_words."""
    words = text.split()
    if not words:
        return []
    segments = []
    for i in range(0, len(words), max_words):
        chunk = " ".join(words[i : i + max_words])
        segments.append(chunk)
    return segments


def compute_required_characters(text: str) -> set[str]:
    """Extract distinct Morse characters and prosigns required to decode text."""
    required = set()
    i = 0
    length = len(text)
    while i < length:
        ch = text[i]
        if ch.isspace():
            i += 1
            continue
        if ch == "<":
            end_idx = text.find(">", i)
            if end_idx != -1:
                required.add(text[i : end_idx + 1].upper())
                i = end_idx + 1
                continue
        required.add(ch.upper())
        i += 1
    return required


def validate_dataset(data: dict[str, Any], table: MorseTable | None = None) -> list[str]:
    """Validate Titanic dataset dictionary against schema and historical rules.

    Returns a list of error strings; an empty list indicates full compliance.
    """
    errors: list[str] = []
    tbl = table or get_table()

    schema = data.get("schema_version")
    if schema != SCHEMA_VERSION:
        errors.append(f"Unsupported schema_version: {schema}. Expected {SCHEMA_VERSION}.")

    messages = data.get("messages", [])
    if not isinstance(messages, list):
        errors.append("'messages' field must be a list.")
        return errors

    seen_ids: set[str] = set()
    seen_orders: set[int] = set()

    for idx, entry in enumerate(messages):
        msg_id = entry.get("id")
        if not msg_id or not isinstance(msg_id, str):
            errors.append(f"Message index {idx} has invalid or missing 'id'.")
        elif msg_id in seen_ids:
            errors.append(f"Duplicate message id '{msg_id}'.")
        else:
            seen_ids.add(msg_id)

        order = entry.get("order")
        if not isinstance(order, int) or order <= 0:
            errors.append(f"Message '{msg_id}' has invalid order '{order}'.")
        elif order in seen_orders:
            errors.append(f"Duplicate order {order} for message '{msg_id}'.")
        else:
            seen_orders.add(order)

        # Check for placeholder markers in all string fields
        for key, val in entry.items():
            if isinstance(val, str) and PLACEHOLDER_PATTERN.search(val):
                errors.append(f"Placeholder marker found in message '{msg_id}', field '{key}'.")

        # Time validation
        time_data = entry.get("time")
        if not isinstance(time_data, dict):
            errors.append(f"Message '{msg_id}' missing 'time' object.")
        else:
            t_val = time_data.get("value")
            t_ref = time_data.get("reference")
            if t_val is not None and t_ref not in VALID_TIME_REFS:
                errors.append(
                    f"Message '{msg_id}' time value requires valid reference in {VALID_TIME_REFS}."
                )

        # Answer normalization check
        raw_msg = entry.get("message", "")
        norm_ans = entry.get("normalized_answer", "")
        expected_norm = normalize(raw_msg)
        # Account for angle-bracketed prosigns e.g. <SOS>
        stripped_norm = norm_ans.replace("<", "").replace(">", "")
        if stripped_norm != expected_norm:
            errors.append(
                f"Message '{msg_id}' normalized_answer '{norm_ans}' does not match "
                "normalized message text."
            )

        # Character existence in Morse table
        req_chars = compute_required_characters(norm_ans)
        for rc in req_chars:
            if rc not in tbl.char_to_pattern:
                errors.append(f"Message '{msg_id}' contains character '{rc}' not in Morse table.")

        # Verification rules
        status = entry.get("verification_status")
        if status not in VALID_STATUSES:
            errors.append(f"Message '{msg_id}' has invalid verification_status '{status}'.")

        if status == "verified":
            if not entry.get("verified_by"):
                errors.append(f"Verified message '{msg_id}' missing 'verified_by'.")
            if not entry.get("verified_on"):
                errors.append(f"Verified message '{msg_id}' missing 'verified_on'.")
            if entry.get("transcription_type") not in VALID_TRANSCRIPTION_TYPES:
                errors.append(f"Verified message '{msg_id}' invalid transcription_type.")
            if not entry.get("context", "").strip():
                errors.append(f"Verified message '{msg_id}' missing context description.")

    return errors


def load_messages(
    path: Path | None = None,
    allow_unverified: bool = False,
    table: MorseTable | None = None,
) -> tuple[list[TitanicMessage], list[str]]:
    """Load and validate Titanic wireless messages.

    By default returns only messages with verification_status == 'verified'.
    """
    f_path = path or TITANIC_MESSAGES_PATH
    if not f_path.exists():
        return [], [f"File not found: {f_path}"]

    with open(f_path, encoding="utf-8") as f:
        data = json.load(f)

    errors = validate_dataset(data, table=table)
    if errors:
        return [], errors

    loaded: list[TitanicMessage] = []
    for entry in data.get("messages", []):
        status = entry.get("verification_status", "pending")
        if not allow_unverified and status != "verified":
            continue

        raw_time = entry.get("time", {})
        t_obj = TitanicTime(
            value=raw_time.get("value"),
            reference=raw_time.get("reference", "unknown"),
        )

        sources = [
            TitanicSource(
                title=s.get("title", ""),
                url=s.get("url", ""),
                publisher=s.get("publisher", ""),
                accessed=s.get("accessed", ""),
            )
            for s in entry.get("sources", [])
        ]

        norm_ans = entry.get("normalized_answer", "")
        segments = compute_segments(norm_ans)
        req_chars = compute_required_characters(norm_ans)

        loaded.append(
            TitanicMessage(
                id=entry["id"],
                order=entry["order"],
                event=entry.get("event", "Wireless Message"),
                message=entry.get("message", ""),
                normalized_answer=norm_ans,
                date=entry.get("date"),
                time=t_obj,
                sender=entry.get("sender"),
                recipient=entry.get("recipient"),
                transcription_type=entry.get("transcription_type", "reconstructed"),
                context=entry.get("context", ""),
                evidence_notes=entry.get("evidence_notes", ""),
                sources=sources,
                verification_status=status,
                verified_by=entry.get("verified_by"),
                verified_on=entry.get("verified_on"),
                segments=segments,
                required_characters=req_chars,
            )
        )

    # Sort loaded messages by order
    loaded.sort(key=lambda m: m.order)
    return loaded, []
