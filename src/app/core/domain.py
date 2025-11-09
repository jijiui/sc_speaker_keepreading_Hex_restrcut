from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

__all__ = ["TimelineEvent", "parse_time_to_ms", "format_ms_to_clock"]


@dataclass
class TimelineEvent:
    """Single timeline event parsed from CSV/TXT/Excel."""

    time_ms: int
    action: str
    population: Optional[str] = None
    note: Optional[str] = None


def parse_time_to_ms(text: str) -> int:
    """Convert text like ``mm:ss`` or seconds into milliseconds."""
    s = (text or "").strip()
    if not s:
        raise ValueError("空时间字符串")

    if ":" in s:
        parts = s.split(":")
        if len(parts) != 2:
            raise ValueError(f"时间格式错误：{s}")
        minutes = int(parts[0])
        seconds = float(parts[1])
        return int((minutes * 60 + seconds) * 1000)

    return int(float(s) * 1000)


def format_ms_to_clock(ms: int) -> str:
    """Format milliseconds into ``m:ss`` string."""
    total_seconds = int(ms // 1000)
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    return f"{minutes:d}:{seconds:02d}"
