# -*- coding: utf-8 -*-
from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Optional, Tuple

from PyQt6 import QtCore, QtGui, QtWidgets

try:  # pragma: no cover
    import cv2  # type: ignore
    _HAS_CV = True
except Exception:  # pragma: no cover
    cv2 = None  # type: ignore
    _HAS_CV = False

from app.infra.ocr.opencv_core import DigitLibrary, preprocess, qimage_to_bgr, segment_chars


@dataclass
class Roi:
    x: int
    y: int
    w: int
    h: int

    def is_valid(self) -> bool:
        return self.w > 0 and self.h > 0


def parse_roi_string(s: str) -> Optional[Roi]:
    try:
        parts = [p.strip() for p in (s or "").split(",")]
        if len(parts) != 4:
            return None
        x, y, w, h = [int(float(p)) for p in parts]
        roi = Roi(x, y, w, h)
        return roi if roi.is_valid() else None
    except Exception:
        return None


class RegionSelectOverlay(QtWidgets.QWidget):
    regionSelected = QtCore.pyqtSignal(QtCore.QRect)

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowFlags(
            QtCore.Qt.WindowType.FramelessWindowHint
            | QtCore.Qt.WindowType.Tool
            | QtCore.Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground, True)
        vg = QtGui.QGuiApplication.primaryScreen().virtualGeometry()
        self.setGeometry(vg)
        self._dragging = False
        self._start_global = QtCore.QPoint()
        self._current_global = QtCore.QPoint()
        self._pen = QtGui.QPen(QtGui.QColor(0, 180, 255, 220), 2, QtCore.Qt.PenStyle.SolidLine)

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self._dragging = True
            self._start_global = event.globalPosition().toPoint()
            self._current_global = self._start_global
            self.update()

    def mouseMoveEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802
        if self._dragging:
            self._current_global = event.globalPosition().toPoint()
            self.update()

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802
        if self._dragging and event.button() == QtCore.Qt.MouseButton.LeftButton:
            self._dragging = False
            end_global = event.globalPosition().toPoint()
            rect = QtCore.QRect(self._start_global, end_global).normalized()
            self.regionSelected.emit(rect)
            self.hide()

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:  # noqa: N802
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        painter.fillRect(self.rect(), QtGui.QColor(0, 0, 0, 100))
        if self._dragging:
            vg = self.geometry().topLeft()
            x1 = self._start_global.x() - vg.x()
            y1 = self._start_global.y() - vg.y()
            x2 = self._current_global.x() - vg.x()
            y2 = self._current_global.y() - vg.y()
            rect = QtCore.QRect(QtCore.QPoint(x1, y1), QtCore.QPoint(x2, y2)).normalized()
            painter.save()
            painter.setCompositionMode(QtGui.QPainter.CompositionMode.CompositionMode_Source)
            painter.fillRect(rect, QtGui.QColor(0, 0, 0, 0))
            painter.restore()
            painter.setPen(self._pen)
            painter.drawRect(rect)


def _trim_components_to_digits(chars: List[Any], expected: int) -> List[Any]:
    if expected <= 0:
        return []
    trimmed = list(chars)
    if len(trimmed) <= expected:
        return trimmed
    if not _HAS_CV or cv2 is None:
        return trimmed[:expected]
    while len(trimmed) > expected:
        idx_min = min(range(len(trimmed)), key=lambda idx: int(cv2.countNonZero(trimmed[idx])))
        trimmed.pop(idx_min)
    return trimmed


def _match_digits(chars: List[Any], lib: DigitLibrary, score_thresh: float) -> Tuple[str, str, List[float]]:
    digits: List[str] = []
    scores: List[float] = []
    for ch in chars:
        pred, score = lib.best_match(ch)
        scores.append(score)
        if score >= score_thresh and pred and pred.isdigit():
            digits.append(pred)
        elif score >= score_thresh and pred == ":":
            digits.append(":")
        else:
            digits.append("?")
    raw = "".join(digits)
    digits_only = "".join(c for c in digits if c.isdigit())
    return raw, digits_only, scores


def recognize_time_from_qimage(
    qimg: QtGui.QImage,
    lib: DigitLibrary,
    scale: int = 3,
    score_thresh: float = 0.55,
) -> Tuple[Optional[str], str]:
    if not _HAS_CV or cv2 is None:
        return None, ""
    if qimg is None or qimg.isNull():
        return None, ""
    bgr = qimage_to_bgr(qimg)
    if bgr is None:
        return None, ""
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    bin_img = preprocess(gray, scale)
    chars = segment_chars(bin_img)
    if not chars:
        return None, ""

    possible_counts: List[int] = []
    orig_len = len(chars)
    if orig_len >= 3:
        possible_counts.append(orig_len)
    for count in (4, 3):
        if count > orig_len:
            continue
        if count >= 3 and count not in possible_counts:
            possible_counts.append(count)
    candidates: List[Tuple[int, float, str, str]] = []
    for expected in possible_counts:
        trimmed = _trim_components_to_digits(chars, expected)
        if len(trimmed) < 3:
            continue
        raw, digits_only, scores = _match_digits(trimmed, lib, score_thresh)
        if len(digits_only) not in (3, 4):
            continue
        minutes_part = digits_only[:-2] or "0"
        seconds_part = digits_only[-2:]
        try:
            minutes_text = str(int(minutes_part))
        except ValueError:
            continue
        time_text = f"{minutes_text}:{seconds_part}"
        question_marks = raw.count("?")
        avg_score = sum(scores) / len(scores) if scores else -1.0
        candidates.append((question_marks, -avg_score, time_text, raw))

    if not candidates:
        return None, ""
    candidates.sort()
    _, _, best_time, raw_pred = candidates[0]
    return best_time, raw_pred


def _parse_time_to_ms(time_text: str) -> Optional[int]:
    try:
        parts = (time_text or "").split(":")
        if len(parts) != 2:
            return None
        minutes = int(parts[0])
        seconds = int(parts[1])
        return (minutes * 60 + seconds) * 1000
    except Exception:
        return None


class OcrTimerAgent(QtCore.QObject):
    timeDetected = QtCore.pyqtSignal(str, int)  # (time_text, ms)
    rawOcr = QtCore.pyqtSignal(str)
    roiSelected = QtCore.pyqtSignal(int, int, int, int)

    def __init__(
        self,
        parent: Optional[QtCore.QObject] = None,
        interval_ms: int = 200,
        scale: int = 3,
        score_thresh: float = 0.55,
    ) -> None:
        super().__init__(parent)
        self._enabled = False
        self._roi: Optional[Roi] = None
        self._scale = int(scale)
        self._score_thresh = float(score_thresh)
        self._last_sec: Optional[int] = None
        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(max(80, int(interval_ms)))
        self._timer.timeout.connect(self._on_tick)
        self._lib = DigitLibrary(Path.cwd() / "cv_digits")

    def reload_templates(self) -> None:
        self._lib.reload()

    def set_roi(self, roi: Roi | QtCore.QRect) -> None:
        if isinstance(roi, QtCore.QRect):
            r = Roi(roi.x(), roi.y(), roi.width(), roi.height())
        else:
            r = roi
        self._roi = r if r.is_valid() else None
        if self._roi:
            self.roiSelected.emit(self._roi.x, self._roi.y, self._roi.w, self._roi.h)

    def set_roi_from_string(self, s: str) -> bool:
        r = parse_roi_string(s)
        if r and r.is_valid():
            self.set_roi(r)
            return True
        return False

    def get_roi(self) -> Optional[Roi]:
        return self._roi

    def select_roi(self, parent: QtWidgets.QWidget | None) -> None:
        overlay = RegionSelectOverlay(parent)
        self._overlay = overlay  # type: ignore[attr-defined]

        def _on_sel(rect: QtCore.QRect) -> None:
            self.set_roi(rect)
            try:
                self._overlay.deleteLater()  # type: ignore[attr-defined]
            except Exception:
                pass
            self._overlay = None  # type: ignore[attr-defined]

        overlay.regionSelected.connect(_on_sel)
        vg = QtGui.QGuiApplication.primaryScreen().virtualGeometry()
        overlay.setGeometry(vg)
        overlay.showFullScreen()

    def set_enabled(self, enabled: bool) -> None:
        want = bool(enabled)
        if want and (not _HAS_CV or cv2 is None):
            self._enabled = False
            self._timer.stop()
            return
        self._enabled = want
        if want:
            self._timer.start()
        else:
            self._timer.stop()

    def is_enabled(self) -> bool:
        return self._enabled and self._timer.isActive()

    def _on_tick(self) -> None:
        if not self._enabled:
            return
        if self._roi is None or not self._roi.is_valid():
            return
        screen = QtGui.QGuiApplication.primaryScreen()
        if screen is None:
            return
        pix = screen.grabWindow(0, self._roi.x, self._roi.y, self._roi.w, self._roi.h)
        img = pix.toImage()
        if img is None or img.isNull():
            return
        time_text, raw_pred = recognize_time_from_qimage(
            img, self._lib, scale=self._scale, score_thresh=self._score_thresh
        )
        if raw_pred:
            self.rawOcr.emit(raw_pred)
        if not time_text:
            return
        ms = _parse_time_to_ms(time_text)
        if ms is None:
            return
        sec = ms // 1000
        if self._last_sec is not None and sec == self._last_sec:
            return
        self._last_sec = sec
        self.timeDetected.emit(time_text, ms)
