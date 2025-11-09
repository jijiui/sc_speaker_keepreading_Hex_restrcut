# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:  # pragma: no cover
    import cv2  # type: ignore
    import numpy as np  # type: ignore
    _HAS_CV = True
except Exception:  # pragma: no cover
    cv2 = None  # type: ignore
    np = None  # type: ignore
    _HAS_CV = False

from PyQt6 import QtGui


def has_opencv() -> bool:
    """Return True when OpenCV + NumPy are available."""
    return _HAS_CV and cv2 is not None and np is not None


def qimage_to_bgr(qimg: QtGui.QImage):
    """Convert a QImage to a BGR numpy array."""
    if not has_opencv():
        return None
    if qimg is None or qimg.isNull():
        return None
    fmt = QtGui.QImage.Format.Format_RGBA8888
    img = qimg.convertToFormat(fmt)
    width, height = img.width(), img.height()
    ptr = img.constBits()
    ptr.setsize(img.sizeInBytes())
    arr = np.frombuffer(ptr, np.uint8).reshape((height, width, 4))
    return cv2.cvtColor(arr, cv2.COLOR_RGBA2BGR)


def preprocess(gray, scale: int = 3):
    """Upscale and binarise a grayscale image for digit extraction."""
    if not has_opencv():
        return gray
    if scale > 1:
        gray = cv2.resize(
            gray,
            (gray.shape[1] * scale, gray.shape[0] * scale),
            interpolation=cv2.INTER_CUBIC,
        )
    blur = cv2.GaussianBlur(gray, (3, 3), 0)
    try:
        _, th = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    except Exception:
        th = cv2.adaptiveThreshold(
            blur,
            255,
            cv2.ADAPTIVE_THRESH_MEAN_C,
            cv2.THRESH_BINARY,
            15,
            2,
        )
    white = int(cv2.countNonZero(th))
    total = th.size
    if white > total // 2:
        th = cv2.bitwise_not(th)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 3))
    return cv2.morphologyEx(th, cv2.MORPH_CLOSE, kernel, iterations=1)


def remove_border_components(bin_img, margin: int = 1):
    """Drop large components touching the border to reduce noise."""
    if not has_opencv():
        return bin_img
    h, w = bin_img.shape[:2]
    out = bin_img.copy()
    area_img = float(w * h) if w and h else 1.0
    try:
        cnts, _ = cv2.findContours(bin_img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    except Exception:
        return out
    for c in cnts:
        x, y, ww, hh = cv2.boundingRect(c)
        touches = 0
        if x <= margin:
            touches += 1
        if y <= margin:
            touches += 1
        if (x + ww) >= (w - 1 - margin):
            touches += 1
        if (y + hh) >= (h - 1 - margin):
            touches += 1
        area_ratio = (ww * hh) / area_img
        if (area_ratio >= 0.30) or (ww >= int(w * 0.90)) or (hh >= int(h * 0.70)):
            cv2.drawContours(out, [c], -1, 0, thickness=-1)
            continue
        if touches >= 2 and (area_ratio >= 0.18 or ww >= int(w * 0.85) or hh >= int(h * 0.85)):
            cv2.drawContours(out, [c], -1, 0, thickness=-1)
    return out


def segment_chars(bin_img) -> List:
    """Segment connected components and return cropped digit patches."""
    if not has_opencv():
        return []
    bin_img = remove_border_components(bin_img)
    cnts, _ = cv2.findContours(bin_img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    rects: List[Tuple[int, int, int, int]] = []
    h, w = bin_img.shape[:2]
    area_img = w * h
    for c in cnts:
        x, y, ww, hh = cv2.boundingRect(c)
        area = ww * hh
        if area < max(25, int(area_img * 0.002)):
            continue
        if hh < int(h * 0.25):
            continue
        if ww >= int(w * 0.9) and hh >= int(h * 0.8):
            continue
        rects.append((x, y, ww, hh))
    rects.sort(key=lambda r: r[0])
    chars: List = []
    for (x, y, ww, hh) in rects:
        pad = max(1, int(min(ww, hh) * 0.15))
        xs, ys = max(0, x - pad), max(0, y - pad)
        xe, ye = min(w, x + ww + pad), min(h, y + hh + pad)
        ch = bin_img[ys:ye, xs:xe]
        if ch.size == 0:
            continue
        ch = cv2.resize(ch, (32, 48), interpolation=cv2.INTER_AREA)
        chars.append(ch)
    return chars


def split_by_projection(bin_img, expected: int) -> List:
    """Segment digits by projection when the number of components is known."""
    if not has_opencv():
        return []
    bin_img = remove_border_components(bin_img)
    h, w = bin_img.shape[:2]
    ys, xs = np.where(bin_img > 0)
    if ys.size and xs.size:
        top, bottom = int(ys.min()), int(ys.max())
        left, right = int(xs.min()), int(xs.max())
        bin_img = bin_img[max(0, top - 1):min(h, bottom + 2), max(0, left - 1):min(w, right + 2)]
        h, w = bin_img.shape[:2]
    col_sum = bin_img.sum(axis=0).astype(np.float32)
    if col_sum.max() > 0:
        col_sum /= col_sum.max()
    col_sum = cv2.GaussianBlur(col_sum.reshape(1, -1), (1, 9), 0).flatten()
    min_w = max(6, int(w / (expected * 3)))
    est = [int((i + 1) * w / expected) for i in range(expected - 1)]
    splits: List[int] = []
    for center in est:
        l = max(1, center - min_w)
        r = min(w - 2, center + min_w)
        seg = col_sum[l:r + 1]
        pos = int(np.argmin(seg)) + l
        if not splits or pos - splits[-1] >= min_w:
            splits.append(pos)
    while len(splits) < expected - 1:
        splits.append(int((len(splits) + 1) * w / expected))
    splits = splits[:expected - 1]
    parts: List = []
    xs2 = [0] + splits + [w]
    for i in range(expected):
        a, b = xs2[i], xs2[i + 1]
        if b - a < min_w:
            continue
        ch = bin_img[:, a:b]
        ch = cv2.resize(ch, (32, 48), interpolation=cv2.INTER_AREA)
        parts.append(ch)
    return parts


def compose_debug_panel(bgr, bin_img):
    """Compose a side-by-side debug panel for GUI preview."""
    if not has_opencv():
        return None
    bin_img = remove_border_components(bin_img)
    cnts, _ = cv2.findContours(bin_img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    rects: List[Tuple[int, int, int, int]] = []
    h, w = bin_img.shape[:2]
    area_img = w * h
    for c in cnts:
        x, y, ww, hh = cv2.boundingRect(c)
        area = ww * hh
        if area < max(25, int(area_img * 0.002)):
            continue
        if hh < int(h * 0.25):
            continue
        if ww >= int(w * 0.9) and hh >= int(h * 0.8):
            continue
        rects.append((x, y, ww, hh))
    rects.sort(key=lambda r: r[0])
    color_bin = cv2.cvtColor(bin_img, cv2.COLOR_GRAY2BGR)
    for (x, y, ww, hh) in rects:
        cv2.rectangle(color_bin, (x, y), (x + ww, y + hh), (0, 255, 0), 1)

    def resize_h(img, h_new):
        return cv2.resize(
            img,
            (int(img.shape[1] * (h_new / img.shape[0])), h_new),
            interpolation=cv2.INTER_NEAREST,
        )

    H = max(bgr.shape[0], color_bin.shape[0])
    left = resize_h(bgr, H)
    right = resize_h(color_bin, H)
    return np.hstack([left, right])


class DigitLibrary:
    """Template-based digit matcher with simple persistence."""

    def __init__(self, folder: Path) -> None:
        self.folder = folder
        self.folder.mkdir(parents=True, exist_ok=True)
        self.bank: Dict[str, List] = {str(d): [] for d in range(10)}
        self.bank[":"] = []
        self.load()

    def load(self) -> None:
        if not has_opencv():
            return
        for p in self.folder.glob("*.png"):
            name = p.stem
            if "_" not in name:
                continue
            ch = name.split("_")[0]
            if ch == "COLON":
                ch = ":"
            if ch not in self.bank:
                continue
            img = cv2.imread(str(p), cv2.IMREAD_GRAYSCALE)
            if img is not None and img.size:
                self.bank[ch].append(img)

    def reload(self) -> None:
        self.bank = {str(d): [] for d in range(10)}
        self.bank[":"] = []
        self.load()

    def save_image(self, ch: str, img) -> None:
        if not has_opencv():
            return
        idx = len(self.bank.get(ch, [])) + 1
        safe = "COLON" if ch == ":" else ch
        out = self.folder / f"{safe}_{idx:03d}.png"
        cv2.imwrite(str(out), img)
        self.bank.setdefault(ch, []).append(img)

    def best_match(self, img) -> Tuple[str, float]:
        if not has_opencv():
            return "?", -1.0
        best_ch, best_score = "?", -1.0
        for ch, lst in self.bank.items():
            for tpl in lst:
                try:
                    res = cv2.matchTemplate(img, tpl, cv2.TM_CCOEFF_NORMED)
                    score = float(res.max())
                except Exception:
                    score = -1.0
                if score > best_score:
                    best_score, best_ch = score, ch
        return best_ch, best_score


__all__ = [
    "DigitLibrary",
    "compose_debug_panel",
    "has_opencv",
    "preprocess",
    "qimage_to_bgr",
    "remove_border_components",
    "segment_chars",
    "split_by_projection",
]

