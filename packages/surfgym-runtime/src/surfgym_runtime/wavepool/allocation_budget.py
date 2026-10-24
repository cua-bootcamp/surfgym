from __future__ import annotations

import math


ALLOCATION_REMAINING_HEADER = "X-SurfGym-Allocate-Remaining-Ms"


def encode_remaining_seconds(seconds: float) -> str:
    if not math.isfinite(seconds) or seconds <= 0:
        raise ValueError("allocation remaining budget must be finite and positive")
    milliseconds = seconds * 1000.0
    if not math.isfinite(milliseconds) or milliseconds <= 0:
        raise ValueError("allocation remaining budget must be finite and positive")
    return repr(milliseconds)


def parse_remaining_seconds(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        milliseconds = float(value)
    except ValueError as exc:
        raise ValueError("allocation remaining budget header must be numeric") from exc
    seconds = milliseconds / 1000.0
    if not math.isfinite(seconds) or seconds <= 0:
        raise ValueError("allocation remaining budget header must be finite and positive")
    return seconds
