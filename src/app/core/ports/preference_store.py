from __future__ import annotations

from abc import ABC, abstractmethod


class PreferenceStore(ABC):
    """Key-value store used for user preferences."""

    @abstractmethod
    def get_bool(self, key: str, default: bool = False) -> bool:
        raise NotImplementedError

    @abstractmethod
    def set_bool(self, key: str, value: bool) -> None:
        raise NotImplementedError

    @abstractmethod
    def get_str(self, key: str, default: str = "") -> str:
        raise NotImplementedError

    @abstractmethod
    def set_str(self, key: str, value: str) -> None:
        raise NotImplementedError
