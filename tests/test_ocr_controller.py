"""Unit tests for the OCR controller."""

from __future__ import annotations

import unittest

from PyQt6 import QtCore, QtWidgets

if QtWidgets.QApplication.instance() is None:  # pragma: no cover
    QtWidgets.QApplication([])

from app.controllers.ocr_controller import OcrController
from app.core.domain import TimelineEvent
from app.core.services import TimelineService
from app.core.ports.preference_store import PreferenceStore
from app.controllers.timeline_controller import TimelineController
from app.ui.state import UiStateController
from app.main import TimelineModel


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


class FakeROI:
    def is_valid(self) -> bool:
        return True


class FakeTimeSource(QtCore.QObject):
    roiSelected = QtCore.pyqtSignal(int, int, int, int)  # type: ignore[assignment]
    timeDetected = QtCore.pyqtSignal(str, int)  # type: ignore[assignment]

    def __init__(self) -> None:
        super().__init__()
        self.enabled: list[bool] = []
        self.selected_parent = None
        self._roi = FakeROI()

    def set_enabled(self, enabled: bool) -> None:
        self.enabled.append(enabled)

    def is_enabled(self) -> bool:
        return bool(self.enabled and self.enabled[-1])

    def set_roi_from_string(self, s: str) -> bool:
        self._roi_text = s
        return True

    def get_roi(self):
        return self._roi

    def select_roi(self, parent: QtWidgets.QWidget) -> None:
        self.selected_parent = parent


class DummySpeech:
    def __init__(self) -> None:
        self.lines: list[str] = []

    def speak(self, text: str) -> None:
        self.lines.append(text)

    def clear_queue(self) -> None:
        self.lines.clear()

    def stop(self) -> None:
        pass


class OcrControllerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.timeline = TimelineService()
        self.prefs = DummyPreferenceStore()
        self.auto_chk = QtWidgets.QCheckBox()
        self.roi_edit = QtWidgets.QLineEdit()
        self.roi_button = QtWidgets.QPushButton()
        self.ocr_label = QtWidgets.QLabel("-")
        self.clock_label = QtWidgets.QLabel("0:00")
        self.on_time_chk = QtWidgets.QCheckBox()
        self.early_chk = QtWidgets.QCheckBox()
        self.time_source = FakeTimeSource()
        self.parent = QtWidgets.QWidget()

        # Minimal timeline controller to satisfy binding.
        status = QtWidgets.QLabel()
        clock = QtWidgets.QLabel()
        countdown = QtWidgets.QLabel()
        table = QtWidgets.QTableView()
        speech = DummySpeech()
        self.model = None

        self.timeline.set_flows({"Alpha": [TimelineEvent(time_ms=1000, action="Test", population="", note="")]})
        self.timeline.set_current_flow("Alpha")

        events = self.timeline.get_events()
        self.model = TimelineModel(events, parent=None)
        table.setModel(self.model)

        self.timeline_controller = TimelineController(
            parent=self.parent,
            timeline=self.timeline,
            speech=speech,
            ui_state=UiStateController(self.timeline, status, clock, countdown),
            timer=self._fake_timer(),
            model_provider=lambda: self.model,
            table_provider=lambda: table,
            mini_mode_provider=lambda: False,
        )

        self.controller = OcrController(
            parent=self.parent,
            timeline=self.timeline,
            prefs=self.prefs,
            auto_checkbox=self.auto_chk,
            roi_edit=self.roi_edit,
            roi_button=self.roi_button,
            ocr_label=self.ocr_label,
            clock_label=self.clock_label,
            on_time_checkbox=self.on_time_chk,
            early_checkbox=self.early_chk,
            time_source=self.time_source,
        )
        self.timeline_controller.set_ocr_controller(self.controller)
        self.controller.bind_timeline_controller(self.timeline_controller)

    def _fake_timer(self):
        class _Timer:
            def start(self): ...
            def stop(self): ...

        return _Timer()

    def test_auto_toggle_enables_time_source(self):
        self.timeline_controller.start()
        self.auto_chk.setChecked(True)
        self.assertTrue(self.time_source.enabled, "Time source should receive enable command")

    def test_select_roi_invokes_time_source(self):
        self.controller.select_roi()
        self.assertIs(self.time_source.selected_parent, self.parent)

    def test_time_detection_notifies_timeline(self):
        self.timeline_controller.start()
        self.auto_chk.setChecked(True)
        handled_before = self.controller.should_skip_tick()
        self.assertTrue(handled_before)
        self.time_source.timeDetected.emit("0:01", 900)
        # second detection to trigger announcement
        self.time_source.timeDetected.emit("0:02", 1200)
        # Expect the controller to lock and timeline to stay in auto mode.
        self.assertTrue(self.controller.should_skip_tick())
        self.assertEqual(self.timeline.elapsed_ms, 1200)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
