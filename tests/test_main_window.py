"""UI-level tests for MainWindow wiring and OCR bindings."""

from __future__ import annotations

import unittest
from pathlib import Path

from PyQt6 import QtCore, QtWidgets

if QtWidgets.QApplication.instance() is None:  # pragma: no cover
    QtWidgets.QApplication([])

from app.core.domain import TimelineEvent
from app.core.ports.preference_store import PreferenceStore
from app.core.ports.speech_port import SpeechPort
from app.core.ports.timeline_repository import TimelineRepository
from app.core.ports.time_source_port import TimeSourcePort
from app.core.services import TimelineService
from app.main import MainWindow


class DummyPreferenceStore(PreferenceStore):
    def __init__(self) -> None:
        self._bool: dict[str, bool] = {}
        self._str: dict[str, str] = {}

    def get_bool(self, key: str, default: bool = False) -> bool:
        return self._bool.get(key, default)

    def set_bool(self, key: str, value: bool) -> None:
        self._bool[key] = value

    def get_str(self, key: str, default: str = "") -> str:
        return self._str.get(key, default)

    def set_str(self, key: str, value: str) -> None:
        self._str[key] = value


class DummySpeechPort(SpeechPort):
    def __init__(self) -> None:
        self.spoken: list[str] = []
        self.cleared = 0
        self.stopped = 0

    def speak(self, text: str) -> None:
        self.spoken.append(text)

    def clear_queue(self) -> None:
        self.cleared += 1

    def stop(self) -> None:
        self.stopped += 1


class DummyRepository(TimelineRepository):
    def __init__(self, flows: dict[str, list[TimelineEvent]]) -> None:
        self._flows = flows
        self.loaded_paths: list[Path] = []

    def load(self, path: Path) -> dict[str, list[TimelineEvent]]:
        self.loaded_paths.append(path)
        return self._flows


class FakeROI:
    def __init__(self, valid: bool = True) -> None:
        self._valid = valid

    def is_valid(self) -> bool:
        return self._valid


class FakeTimeSource(QtCore.QObject):
    roiSelected = QtCore.pyqtSignal(int, int, int, int)  # type: ignore[assignment]
    timeDetected = QtCore.pyqtSignal(str, int)  # type: ignore[assignment]

    def __init__(self) -> None:
        super().__init__()
        self.enabled_calls: list[bool] = []
        self.select_roi_parent = None
        self._roi = FakeROI()

    def set_enabled(self, enabled: bool) -> None:
        self.enabled_calls.append(enabled)

    def is_enabled(self) -> bool:
        return bool(self.enabled_calls and self.enabled_calls[-1])

    def set_roi_from_string(self, s: str) -> bool:
        self._roi_string = s
        return True

    def get_roi(self) -> FakeROI:
        return self._roi

    def select_roi(self, parent: QtWidgets.QWidget) -> None:
        self.select_roi_parent = parent


def _build_sample_event() -> TimelineEvent:
    return TimelineEvent(time_ms=1000, action="Test Event", population="", note="")


class MainWindowTests(unittest.TestCase):
    def _create_window(
        self,
        flows: dict[str, list[TimelineEvent]] | None = None,
        time_source: FakeTimeSource | None = None,
    ) -> tuple[MainWindow, DummyRepository, FakeTimeSource]:
        repo = DummyRepository(flows or {"Alpha": [_build_sample_event()]})
        prefs = DummyPreferenceStore()
        speech = DummySpeechPort()
        source = time_source or FakeTimeSource()
        window = MainWindow(
            timeline=TimelineService(),
            repository=repo,
            preference_store=prefs,
            speech_port=speech,
            time_source=source,
        )
        return window, repo, source

    def test_load_timeline_uses_injected_repository(self):
        window, repo, _ = self._create_window()
        path = Path("dummy.csv")

        window.load_timeline(path)

        self.assertEqual([path], repo.loaded_paths)
        self.assertEqual(window.flow_list.count(), 1)
        self.assertEqual(window.timeline.current_flow_name, "Alpha")

        window.close()
        window.deleteLater()

    def test_ocr_controls_toggle_time_source(self):
        window, _, time_source = self._create_window()
        window.load_timeline(Path("dummy.csv"))
        window.timeline_controller.start()

        window.auto_chk.setChecked(True)

        self.assertTrue(time_source.enabled_calls, "OCR agent should receive enable calls")
        self.assertTrue(time_source.enabled_calls[-1], "OCR agent should be enabled when auto mode is on")

        window.ocr_controller.select_roi()
        self.assertIs(
            time_source.select_roi_parent,
            window,
            "ROI selection should call the injected time source",
        )

        window.close()
        window.deleteLater()


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
