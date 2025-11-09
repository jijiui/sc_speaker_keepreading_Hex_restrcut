from __future__ import annotations

from typing import Any, Protocol


class TimeSourcePort(Protocol):
    """Interface for services that detect in-game time (e.g., OCR)."""

    timeDetected: Any
    roiSelected: Any

    def set_enabled(self, enabled: bool) -> None:
        ...

    def is_enabled(self) -> bool:
        ...

    def set_roi_from_string(self, s: str) -> bool:
        ...

    def get_roi(self) -> Any:
        ...

    def select_roi(self, parent: Any) -> None:
        ...
