from __future__ import annotations

from typing import Protocol


class SpeechPort(Protocol):
    """Interface for components capable of speaking queued text."""

    def speak(self, text: str) -> None:
        ...

    def clear_queue(self) -> None:
        ...

    def stop(self) -> None:
        ...
