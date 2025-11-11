"""Controller that encapsulates OCR agent wiring and ROI management."""

from __future__ import annotations

from pathlib import Path
from typing import Optional, TYPE_CHECKING

from PyQt6 import QtCore, QtWidgets

from app.core.ports.preference_store import PreferenceStore
from app.core.ports.time_source_port import TimeSourcePort
from app.core.services import TimelineService
from app.infra.ocr.qt_ocr_agent import OcrTimerAgent

if TYPE_CHECKING:  # pragma: no cover
    from app.controllers.timeline_controller import TimelineController


class OcrController(QtCore.QObject):
    """Manages OCR agent lifecycle, ROI persistence, and auto-mode toggles."""

    def __init__(
        self,
        parent: QtWidgets.QWidget,
        timeline: TimelineService,
        prefs: PreferenceStore,
        auto_checkbox: QtWidgets.QCheckBox,
        roi_edit: QtWidgets.QLineEdit,
        roi_button: QtWidgets.QPushButton,
        ocr_label: QtWidgets.QLabel,
        clock_label: QtWidgets.QLabel,
        on_time_checkbox: QtWidgets.QCheckBox,
        early_checkbox: QtWidgets.QCheckBox,
        time_source: Optional[TimeSourcePort] = None,
    ) -> None:
        super().__init__(parent)
        self.timeline = timeline
        self.prefs = prefs
        self.auto_checkbox = auto_checkbox
        self.roi_edit = roi_edit
        self.roi_button = roi_button
        self.ocr_label = ocr_label
        self.clock_label = clock_label
        self.on_time_checkbox = on_time_checkbox
        self.early_checkbox = early_checkbox
        self._time_source = time_source or OcrTimerAgent(parent, interval_ms=200, scale=3, score_thresh=0.55)

        self._timeline_controller: Optional["TimelineController"] = None
        self._running = False
        self._locked = False

        self._restore_preferences()
        self._wire_signals()
        self._sync_enabled()

    # ------------------------------------------------------------------ lifecycle hooks
    def bind_timeline_controller(self, controller: "TimelineController") -> None:
        self._timeline_controller = controller

    def on_started(self) -> None:
        self._running = True
        self._locked = False
        self._sync_enabled()

    def on_paused(self) -> None:
        self._running = False
        self._sync_enabled()

    def on_reset(self) -> None:
        self._locked = False
        self.ocr_label.setText("-")
        self._sync_enabled()

    def should_skip_tick(self) -> bool:
        if not self.auto_checkbox.isChecked() or not self._running:
            return False
        roi = self._get_roi()
        enabled = self._time_source_is_enabled()
        if not enabled or roi is None or not roi.is_valid():
            self.clock_label.setText("没检测到")
            return True
        if not self._locked:
            self.clock_label.setText("没检测到")
            return True
        return True

    # ------------------------------------------------------------------ internal wiring
    def _restore_preferences(self) -> None:
        try:
            roi_str = self.prefs.get_str("ocr/roi", "")
        except Exception:
            roi_str = ""
        if roi_str and self._time_source.set_roi_from_string(roi_str):
            self.roi_edit.setText(roi_str)

        auto_on = False
        try:
            auto_on = self.prefs.get_bool("ocr/auto", False)
        except Exception:
            pass
        self.auto_checkbox.setChecked(auto_on)

        on_time = True
        early = False
        try:
            on_time = self.prefs.get_bool("opt/on_time", True)
        except Exception:
            pass
        try:
            early = self.prefs.get_bool("opt/early", False)
        except Exception:
            pass
        self.on_time_checkbox.setChecked(on_time)
        self.early_checkbox.setChecked(early)
        self.timeline.on_time_enabled = bool(on_time)
        self.timeline.early_enabled = bool(early)

    def _wire_signals(self) -> None:
        self.roi_edit.editingFinished.connect(self._on_roi_edit_changed)
        self.roi_button.clicked.connect(self._on_roi_button_clicked)
        self.auto_checkbox.toggled.connect(self._on_auto_toggled)
        self.on_time_checkbox.toggled.connect(lambda v: self._set_broadcast_option("on_time", bool(v)))
        self.early_checkbox.toggled.connect(lambda v: self._set_broadcast_option("early", bool(v)))
        self._time_source.roiSelected.connect(self._on_roi_selected)
        self._time_source.timeDetected.connect(self._on_time_detected)

    # ------------------------------------------------------------------ slots
    def _on_roi_edit_changed(self) -> None:
        text = self.roi_edit.text().strip()
        ok = False
        try:
            ok = self._time_source.set_roi_from_string(text)
        except Exception:
            ok = False
        if ok:
            self.prefs.set_str("ocr/roi", text)
            self._locked = False
        self._sync_enabled()

    def _on_roi_button_clicked(self) -> None:
        try:
            self._time_source.select_roi(self.parent())
        except Exception:
            pass

    def _on_roi_selected(self, x: int, y: int, w: int, h: int) -> None:
        roi = f"{x},{y},{w},{h}"
        self.roi_edit.setText(roi)
        self.prefs.set_str("ocr/roi", roi)
        self._locked = False
        self._sync_enabled()

    def _on_auto_toggled(self, enabled: bool) -> None:
        self.prefs.set_bool("ocr/auto", bool(enabled))
        self._locked = False
        self._sync_enabled()

    def _set_broadcast_option(self, option: str, value: bool) -> None:
        if option == "on_time":
            self.timeline.on_time_enabled = value
            self.prefs.set_bool("opt/on_time", value)
        else:
            self.timeline.early_enabled = value
            self.prefs.set_bool("opt/early", value)

    def _on_time_detected(self, time_text: str, ms: int) -> None:
        self.ocr_label.setText(time_text)
        if not self._timeline_controller or not self._running:
            return
        handled = self._timeline_controller.handle_ocr_time(time_text, ms, self._locked)
        if handled:
            self._locked = True

    # ------------------------------------------------------------------ helpers
    def _get_roi(self):
        try:
            return self._time_source.get_roi()
        except Exception:
            return None

    def _time_source_is_enabled(self) -> bool:
        try:
            return bool(self._time_source.is_enabled())
        except Exception:
            # Not every implementation exposes the accessor.
            return True

    def _sync_enabled(self) -> None:
        roi = self._get_roi()
        want = bool(
            self.auto_checkbox.isChecked()
            and self._running
            and roi is not None
            and getattr(roi, "is_valid", lambda: False)()
        )
        try:
            self._time_source.set_enabled(want)
        except Exception:
            pass

    # Convenience APIs for other components ------------------------------------
    def select_roi(self) -> None:
        self._on_roi_button_clicked()

