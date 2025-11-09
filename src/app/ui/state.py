"""State helpers for keeping UI labels and countdowns in sync."""

from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from PyQt6 import QtWidgets

from app.core.domain import format_ms_to_clock
from app.core.services import TimelineService

if TYPE_CHECKING:  # pragma: no cover
    from typing import Any as TimelineModel


class UiStateController:
    """Centralizes clock/status updates for the main window."""

    def __init__(
        self,
        timeline: TimelineService,
        status_label: QtWidgets.QLabel,
        clock_label: QtWidgets.QLabel,
        countdown_label: QtWidgets.QLabel,
    ) -> None:
        self.timeline = timeline
        self.status_label = status_label
        self.clock_label = clock_label
        self.countdown_label = countdown_label

    def set_status(self, text: str) -> None:
        self.status_label.setText(text)

    def update_clock(
        self,
        model: Optional["TimelineModel"],
        table: Optional[QtWidgets.QTableView],
        mini_mode: bool,
    ) -> None:
        elapsed = self.timeline.elapsed_ms
        self.clock_label.setText(format_ms_to_clock(elapsed))
        if not model or table is None:
            self.countdown_label.setText("--")
            return

        events = model.events
        idx = self.timeline.next_event_index()
        if idx is None or idx < 0:
            self.countdown_label.setText("--")
            table.clearSelection()
            return

        idx = min(idx, len(events) - 1)
        table.selectRow(idx)
        hint = (
            QtWidgets.QAbstractItemView.ScrollHint.PositionAtTop
            if mini_mode
            else QtWidgets.QAbstractItemView.ScrollHint.PositionAtCenter
        )
        table.scrollTo(model.index(idx, 0), hint)
        next_ev = events[idx]
        diff_ms = max(0, next_ev.time_ms - elapsed)
        self.countdown_label.setText(format_ms_to_clock(diff_ms))
