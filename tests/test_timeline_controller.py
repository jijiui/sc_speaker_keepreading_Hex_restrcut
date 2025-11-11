"""Unit tests for the TimelineController."""

from __future__ import annotations

import unittest
from typing import Optional

from PyQt6 import QtWidgets

if QtWidgets.QApplication.instance() is None:  # pragma: no cover
    QtWidgets.QApplication([])

from app.controllers.timeline_controller import TimelineController
from app.core.domain import TimelineEvent
from app.core.services import TimelineService
from app.core.ports.speech_port import SpeechPort
from app.ui.state import UiStateController
from app.main import TimelineModel


class DummySpeech(SpeechPort):
    def __init__(self) -> None:
        self.lines: list[str] = []

    def speak(self, text: str) -> None:
        self.lines.append(text)

    def clear_queue(self) -> None:  # pragma: no cover - unused but required
        self.lines.clear()

    def stop(self) -> None:  # pragma: no cover - unused but required
        pass


class FakeTimer:
    def __init__(self) -> None:
        self.started = False
        self.stopped = False

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.stopped = True


class TimelineControllerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.timeline = TimelineService()
        self.timer = FakeTimer()
        self.speech = DummySpeech()
        self.parent = QtWidgets.QWidget()
        self.status = QtWidgets.QLabel()
        self.clock = QtWidgets.QLabel()
        self.countdown = QtWidgets.QLabel()
        self.ui_state = UiStateController(self.timeline, self.status, self.clock, self.countdown)
        self.table = QtWidgets.QTableView()
        self.model: Optional[TimelineModel] = None

        self.controller = TimelineController(
            parent=self.parent,
            timeline=self.timeline,
            speech=self.speech,
            ui_state=self.ui_state,
            timer=self.timer,  # type: ignore[arg-type]
            model_provider=lambda: self.model,
            table_provider=lambda: self.table,
            mini_mode_provider=lambda: False,
        )

    def _load_flow(self) -> None:
        events = [TimelineEvent(time_ms=1000, action="Test", population="", note="")]
        self.timeline.set_flows({"Alpha": events})
        self.timeline.set_current_flow("Alpha")
        self.model = TimelineModel(events, parent=None)
        self.table.setModel(self.model)

    def test_start_requires_model(self) -> None:
        self.controller.start()
        self.assertFalse(self.timeline.running)
        self.assertFalse(self.timer.started)

    def test_start_and_pause_flow(self) -> None:
        self._load_flow()
        self.controller.start()
        self.assertTrue(self.timeline.running)
        self.assertTrue(self.timer.started)

        self.controller.pause()
        self.assertFalse(self.timeline.running)
        self.assertTrue(self.timer.stopped)

    def test_handle_ocr_time_triggers_speech(self) -> None:
        self._load_flow()
        self.controller.start()
        # prime with first detection
        handled = self.controller.handle_ocr_time("0:01", 900, locked_before=False)
        self.assertTrue(handled)
        handled = self.controller.handle_ocr_time("0:02", 1200, locked_before=True)
        self.assertTrue(handled)
        self.assertEqual(self.speech.lines[-1], "Test")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
