"""Application bootstrap utilities for PvZ timeline speaker."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Optional

from PyQt6 import QtWidgets

from app.core.ports.preference_store import PreferenceStore
from app.core.ports.speech_port import SpeechPort
from app.core.ports.timeline_repository import TimelineRepository
from app.core.ports.time_source_port import TimeSourcePort
from app.core.services import TimelineService
from app.infra.file_repository import FileTimelineRepository
from app.infra.qsettings_store import QtPreferenceStore
from app.main import MainWindow


@dataclass
class BootstrapConfig:
    """Optional overrides for dependency injection when creating MainWindow."""

    headless: bool = False
    timeline: Optional[TimelineService] = None
    repository: Optional[TimelineRepository] = None
    preference_store: Optional[PreferenceStore] = None
    speech_port: Optional[SpeechPort] = None
    time_source: Optional[TimeSourcePort] = None


class HeadlessSpeechPort:
    """SpeechPort implementation used for headless/testing scenarios."""

    def __init__(self) -> None:
        self.spoken: list[str] = []

    def speak(self, text: str) -> None:
        if not text or not text.strip():
            return
        self.spoken.append(text)

    def clear_queue(self) -> None:
        self.spoken.clear()

    def stop(self) -> None:
        """Headless speech port has no threads to stop."""
        return


def create_main_window(config: Optional[BootstrapConfig] = None) -> MainWindow:
    """Instantiate MainWindow with configured dependencies."""
    cfg = config or BootstrapConfig()

    timeline = cfg.timeline or TimelineService(global_lead_ms=2000)
    repository = cfg.repository or FileTimelineRepository()
    preference_store = cfg.preference_store or QtPreferenceStore()

    speech_port: Optional[SpeechPort] = cfg.speech_port
    if speech_port is None and cfg.headless:
        speech_port = HeadlessSpeechPort()

    window = MainWindow(
        timeline=timeline,
        repository=repository,
        preference_store=preference_store,
        speech_port=speech_port,
        time_source=cfg.time_source,
    )
    return window


def _ensure_app() -> QtWidgets.QApplication:
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication(sys.argv)
    return app


def run(config: Optional[BootstrapConfig] = None) -> int:
    """Create QApplication, show MainWindow, and start the event loop."""
    app = _ensure_app()
    window = create_main_window(config)
    window.show()
    return app.exec()


def main() -> int:
    """Module entry point compatible with `python -m app.bootstrap`."""
    return run()


__all__ = ["BootstrapConfig", "HeadlessSpeechPort", "create_main_window", "run", "main"]
