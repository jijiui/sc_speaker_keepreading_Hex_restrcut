from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, List

from core.domain import TimelineEvent


class TimelineRepository(ABC):
    """Port that loads timeline flows from a given source."""

    @abstractmethod
    def load(self, path: Path) -> Dict[str, List[TimelineEvent]]:
        """Return {flow_name: [events]} parsed from the given file path."""
        raise NotImplementedError
