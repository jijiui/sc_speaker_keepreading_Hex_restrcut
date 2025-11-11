"""Timeline controller orchestrating ticks, speech, and UI state."""

from __future__ import annotations

import time
from typing import Callable, Optional, Protocol, TYPE_CHECKING

from PyQt6 import QtCore, QtWidgets

from app.core.services import TimelineService
from app.core.ports.speech_port import SpeechPort
from app.ui.state import UiStateController

if TYPE_CHECKING:  # pragma: no cover
    from app.main import TimelineModel
    from PyQt6.QtWidgets import QTableView


class OcrControllerProtocol(Protocol):
    """Minimal contract required by the timeline controller."""

    def on_started(self) -> None: ...

    def on_paused(self) -> None: ...

    def on_reset(self) -> None: ...

    def should_skip_tick(self) -> bool: ...


class TimelineController(QtCore.QObject):
    """Encapsulates TimelineService interactions and tick handling."""

    def __init__(
        self,
        parent: QtWidgets.QWidget,
        timeline: TimelineService,
        speech: SpeechPort,
        ui_state: UiStateController,
        timer: QtCore.QTimer,
        model_provider: Callable[[], Optional["TimelineModel"]],
        table_provider: Callable[[], Optional["QTableView"]],
        mini_mode_provider: Callable[[], bool],
    ) -> None:
        super().__init__(parent)
        self.timeline = timeline
        self.speech = speech
        self.ui_state = ui_state
        self.timer = timer
        self._get_model = model_provider
        self._get_table = table_provider
        self._mini_mode_provider = mini_mode_provider

        self._last_tick = 0.0
        self._ocr_controller: Optional[OcrControllerProtocol] = None

    # ------------------------------------------------------------------ helpers
    def set_ocr_controller(self, controller: OcrControllerProtocol) -> None:
        self._ocr_controller = controller

    # ------------------------------------------------------------------ lifecycle
    def toggle_run(self) -> None:
        if self.timeline.running:
            self.pause()
        else:
            self.start()

    def start(self) -> None:
        model = self._get_model()
        if not model:
            QtWidgets.QMessageBox.information(self.parent(), "提示", "请先加载一个时间轴流程。")
            return
        try:
            self.timeline.start()
        except RuntimeError as exc:
            QtWidgets.QMessageBox.information(self.parent(), "提示", str(exc))
            return
        self.timer.start()
        self.ui_state.set_status(f"运行中：{self.timeline.current_flow_name or '--'}")
        self._last_tick = time.perf_counter()
        if self._ocr_controller:
            self._ocr_controller.on_started()

    def pause(self) -> None:
        if not self.timeline.running:
            return
        self.timeline.pause()
        self.timer.stop()
        self.ui_state.set_status("已暂停")
        self._last_tick = 0.0
        if self._ocr_controller:
            self._ocr_controller.on_paused()

    def reset(self) -> None:
        self.timeline.reset()
        self.timer.stop()
        self._last_tick = 0.0
        try:
            self.speech.clear_queue()
        except Exception:
            pass
        self._update_clock()
        self.ui_state.set_status("已重置")
        if self._ocr_controller:
            self._ocr_controller.on_reset()

    # ------------------------------------------------------------------ ticks
    def on_tick(self) -> None:
        model = self._get_model()
        if not self.timeline.running or model is None:
            return
        if self._ocr_controller and self._ocr_controller.should_skip_tick():
            self._last_tick = time.perf_counter()
            return

        now = time.perf_counter()
        if not self._last_tick:
            self._last_tick = now
            return
        delta_ms = max(0, int((now - self._last_tick) * 1000))
        self._last_tick = now
        decision = self.timeline.advance(delta_ms)
        self._update_clock()
        self._handle_decision(decision)

    def handle_ocr_time(self, time_text: str, ms: int, locked_before: bool) -> bool:
        """Process OCR-detected timestamps; returns True if handled."""
        if not self.timeline.running:
            return False

        if not locked_before:
            self.timeline.prime_elapsed(ms)
            self._update_clock()
            self._last_tick = time.perf_counter()
            return True

        decision = self.timeline.sync_elapsed(ms)
        self._update_clock()
        self._handle_decision(decision)
        self._last_tick = time.perf_counter()
        return True

    # ------------------------------------------------------------------ helpers
    def _update_clock(self) -> None:
        model = self._get_model()
        table = self._get_table()
        if not model or table is None:
            return
        self.ui_state.update_clock(model, table, self._mini_mode_provider())

    def _handle_decision(self, decision) -> None:
        if not decision:
            return
        self._speak(decision.event.action)

    def _speak(self, text: str) -> None:
        if not text.strip():
            return
        try:
            self.speech.speak(text)
        except Exception:
            print(f"[TTS failure] {text}")
            QtWidgets.QApplication.beep()
