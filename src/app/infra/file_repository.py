from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import Dict, List, Optional

from app.core.domain import TimelineEvent, parse_time_to_ms
from app.core.ports import TimelineRepository

try:
    import pandas as pd  # type: ignore

    _HAS_PANDAS = True
except Exception:  # pragma: no cover - optional dependency
    pd = None  # type: ignore
    _HAS_PANDAS = False

__all__ = ["FileTimelineRepository"]


class FileTimelineRepository(TimelineRepository):
    """Load timelines from CSV/TXT/Excel files."""

    def __init__(self) -> None:
        self.last_warning: Optional[str] = None

    def load(self, path: Path) -> Dict[str, List[TimelineEvent]]:
        suffix = path.suffix.lower()
        self.last_warning = None
        if suffix in (".csv", ".txt"):
            events = self._read_csv_like(path)
            return {path.stem: events}
        if suffix in (".xlsx", ".xls"):
            if not _HAS_PANDAS or pd is None:
                raise RuntimeError("读取 Excel 需要安装 pandas 与 openpyxl：pip install pandas openpyxl")
            flows: Dict[str, List[TimelineEvent]] = {}
            xls = pd.read_excel(path, sheet_name=None)
            for sheet, df in xls.items():
                events = self._events_from_dataframe(df)
                if events:
                    flows[f"{path.stem}/{sheet}"] = events
            return flows
        raise RuntimeError("仅支持 CSV/TXT/XLSX/XLS")

    # ------------------------------------------------------------------
    # CSV/TXT helpers
    # ------------------------------------------------------------------

    def _read_csv_like(self, path: Path) -> List[TimelineEvent]:
        text, encoding, warned = _read_text_autoenc(path)
        if warned:
            self.last_warning = (
                f"文件以 {encoding} 解码，部分字符可能显示异常。\n"
                "建议使用 UTF-8 保存以获得最佳兼容。"
            )
        csv_mod, dialect = _open_csv_stringio_guess(text)
        reader = csv_mod.DictReader(io.StringIO(text), dialect=dialect)
        headers = reader.fieldnames or []
        norm_map = {_normalize_header(h): h for h in headers}

        time_col = _resolve_header(norm_map, "time")
        action_col = _resolve_header(norm_map, "action")
        if not time_col or not action_col:
            raise RuntimeError("CSV/TXT 需包含表头：时间,动作（可选：人口/备注）")
        pop_col = _resolve_header(norm_map, "population")
        note_col = _resolve_header(norm_map, "note")

        events: List[TimelineEvent] = []
        for row in reader:
            try:
                t_ms = parse_time_to_ms(str(row.get(time_col, "")))
                action = str(row.get(action_col, "")).strip()
                if not action:
                    continue
                population = (str(row.get(pop_col, "")).strip() or None) if pop_col else None
                note = (str(row.get(note_col, "")).strip() or None) if note_col else None
                events.append(
                    TimelineEvent(
                        time_ms=t_ms,
                        action=action,
                        population=population,
                        note=note,
                    )
                )
            except Exception as exc:
                raise RuntimeError(f"CSV 解析失败：{exc}") from exc
        events.sort(key=lambda e: e.time_ms)
        return events

    def _events_from_dataframe(self, df) -> List[TimelineEvent]:
        norm_map = {_normalize_header(c): c for c in df.columns}
        time_col = _resolve_header(norm_map, "time")
        action_col = _resolve_header(norm_map, "action")
        if not time_col or not action_col:
            return []
        pop_col = _resolve_header(norm_map, "population")
        note_col = _resolve_header(norm_map, "note")

        events: List[TimelineEvent] = []
        for _, row in df.iterrows():
            t_val = row[time_col]
            a_val = row[action_col]
            if pd.isna(t_val) or pd.isna(a_val):
                continue
            try:
                t_ms = parse_time_to_ms(str(t_val))
            except Exception:
                continue
            action = str(a_val).strip()
            if not action:
                continue
            population = None
            if pop_col:
                pop_raw = str(row.get(pop_col, "")).strip()
                population = pop_raw or None
            note = None
            if note_col:
                note_raw = str(row.get(note_col, "")).strip()
                note = note_raw or None
            events.append(
                TimelineEvent(
                    time_ms=t_ms,
                    action=action,
                    population=population,
                    note=note,
                )
            )
        events.sort(key=lambda e: e.time_ms)
        return events


# ----------------------------------------------------------------------
# Shared parsing helpers
# ----------------------------------------------------------------------

_HEADER_ALIASES = {
    "time": ["time", "时间"],
    "action": ["action", "动作"],
    "population": ["人口", "supply", "population"],
    "note": ["备注", "说明", "备注信息", "注释", "remark", "note", "notes"],
}


def _normalize_header(name: str) -> str:
    text = str(name or "").replace("\ufeff", "").strip().lower()
    return "".join(text.split())


def _resolve_header(norm_map: Dict[str, str], key: str) -> Optional[str]:
    for alias in _HEADER_ALIASES.get(key, []):
        norm = _normalize_header(alias)
        if norm in norm_map:
            return norm_map[norm]
    return None


def _read_text_autoenc(path: Path) -> tuple[str, str, bool]:
    tried = [
        "utf-8",
        "utf-8-sig",
        "gbk",
        "cp936",
        "big5",
        "shift_jis",
        "cp932",
        "cp1252",
        "latin-1",
    ]
    data = path.read_bytes()
    for enc in tried:
        try:
            return data.decode(enc), enc, False
        except Exception:
            continue
    return data.decode("latin-1", errors="replace"), "latin-1", True


def _open_csv_stringio_guess(text: str):
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except Exception:
        dialect = csv.excel
    return csv, dialect
