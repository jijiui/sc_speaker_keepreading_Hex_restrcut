from __future__ import annotations

from PyQt6 import QtCore

from core.ports import PreferenceStore

__all__ = ["QtPreferenceStore"]


class QtPreferenceStore(PreferenceStore):
    """PreferenceStore backed by Qt's QSettings."""

    def __init__(self, organization: str = "sc_speaker", application: str = "pvz_timeline") -> None:
        self._settings = QtCore.QSettings(organization, application)

    def get_bool(self, key: str, default: bool = False) -> bool:
        try:
            value = self._settings.value(key, default, type=bool)
        except Exception:
            value = default
        return bool(value)

    def set_bool(self, key: str, value: bool) -> None:
        self._settings.setValue(key, bool(value))

    def get_str(self, key: str, default: str = "") -> str:
        try:
            value = self._settings.value(key, default, type=str)
        except Exception:
            value = default
        if value is None:
            return default
        return str(value)

    def set_str(self, key: str, value: str) -> None:
        self._settings.setValue(key, value)
