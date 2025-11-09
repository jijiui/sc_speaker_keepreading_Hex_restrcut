#!/usr/bin/env python3
"""
CLI smoke test for `_check_announcements_simple`.

This script avoids the PyQt6 GUI runtime and external dependencies, so it
can run in bare environments to validate the timeline announcement logic.
"""

from __future__ import annotations

import argparse
import csv
import io
import sys
import tempfile
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple

ENCODINGS = [
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

HEADER_ALIASES = {
    "time": ["time", "时间"],
    "action": ["action", "动作"],
    "population": ["population", "供给", "supply", "人口"],
    "note": ["note", "notes", "备注", "说明"],
}


@dataclass
class TimelineEvent:
    time_ms: int
    action: str
    population: Optional[str] = None
    note: Optional[str] = None


def normalize_header(name: str) -> str:
    text = (name or "").replace("\ufeff", "").strip().lower()
    return "".join(text.split())


def resolve_header(norm_map: dict[str, str], key: str) -> Optional[str]:
    for alias in HEADER_ALIASES.get(key, []):
        norm = normalize_header(alias)
        if norm in norm_map:
            return norm_map[norm]
    return None


def parse_time_to_ms(text: str) -> int:
    raw = (text or "").strip()
    if not raw:
        return 0
    try:
        if ":" in raw:
            minute_part, second_part = raw.split(":", 1)
            minutes = int(minute_part)
            seconds = float(second_part)
            return int(round((minutes * 60 + seconds) * 1000))
        seconds = float(raw)
        return int(round(seconds * 1000))
    except ValueError:
        return 0


def format_ms_to_clock(ms: int) -> str:
    seconds = max(0, int(ms // 1000))
    minutes, secs = divmod(seconds, 60)
    return f"{minutes}:{secs:02d}"


def read_text_autoenc(path: Path) -> Tuple[str, str]:
    for enc in ENCODINGS:
        try:
            return path.read_text(encoding=enc), enc
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="replace"), "utf-8"


def open_csv_guess(text: str) -> Tuple[csv, csv.Dialect]:
    try:
        dialect = csv.Sniffer().sniff(text[:1024], delimiters=",;\t|")
    except csv.Error:
        dialect = csv.get_dialect("excel")
    return csv, dialect


def emit(msg: str) -> None:
    sys.stdout.buffer.write(msg.encode("utf-8", "replace"))
    sys.stdout.buffer.write(b"\n")


def load_events_from_csv(path: Path) -> List[TimelineEvent]:
    text, _ = read_text_autoenc(path)
    csv_mod, dialect = open_csv_guess(text)
    reader = csv_mod.DictReader(io.StringIO(text), dialect=dialect)
    headers = reader.fieldnames or []
    norm_map = {normalize_header(h): h for h in headers}
    time_col = resolve_header(norm_map, "time")
    action_col = resolve_header(norm_map, "action")
    pop_col = resolve_header(norm_map, "population")
    note_col = resolve_header(norm_map, "note")
    if not time_col or not action_col:
        raise ValueError("CSV 需包含 时间/动作 表头")

    events: List[TimelineEvent] = []
    for row in reader:
        action = str(row.get(action_col, "")).strip()
        if not action:
            continue
        t_ms = parse_time_to_ms(str(row.get(time_col, "")))
        population = str(row.get(pop_col, "")).strip() if pop_col else ""
        note = str(row.get(note_col, "")).strip() if note_col else ""
        events.append(
            TimelineEvent(
                time_ms=t_ms,
                action=action,
                population=population or None,
                note=note or None,
            )
        )
    events.sort(key=lambda e: e.time_ms)
    return events


def detect_announcement(
    events: Sequence[TimelineEvent],
    prev_ms: int,
    curr_ms: int,
    lead_ms: int,
    on_time: bool,
    early: bool,
) -> Optional[Tuple[str, TimelineEvent]]:
    advance = lead_ms if early else 0
    for ev in events:
        if on_time and (prev_ms < ev.time_ms <= curr_ms):
            return ("on_time", ev)
        if advance > 0:
            early_start = max(0, ev.time_ms - advance)
            if prev_ms < early_start <= curr_ms and curr_ms < ev.time_ms:
                return ("early", ev)
    return None


def run_simulation(
    events: Sequence[TimelineEvent],
    tick_ms: int,
    lead_ms: int,
    duration_ms: Optional[int],
    on_time: bool,
    early: bool,
) -> None:
    if not events:
        emit("未找到任何事件，退出。")
        return
    horizon = duration_ms or (events[-1].time_ms + lead_ms + 5000)
    prev_ms = 0
    elapsed_ms = 0
    triggered = 0
    emit(
        f"开始模拟：tick={tick_ms}ms, lead={lead_ms}ms, "
        f"整点={'开' if on_time else '关'}, 提前={'开' if early else '关'}"
    )
    while elapsed_ms <= horizon:
        res = detect_announcement(events, prev_ms, elapsed_ms, lead_ms, on_time, early)
        if res:
            mode, ev = res
            tag = "提前" if mode == "early" else "整点"
            emit(
                f"[{format_ms_to_clock(elapsed_ms):>7}] {tag}播报 → "
                f"{ev.action}（事件 {format_ms_to_clock(ev.time_ms)}）"
            )
            triggered += 1
        prev_ms = elapsed_ms
        elapsed_ms += tick_ms
    emit(f"模拟结束：共触发 {triggered} 次播报。")


def write_sample_csv() -> Path:
    sample = textwrap.dedent(
        """\
        时间,动作,人口,备注
        0:17,一水晶,14/15,
        0:38,网关,16/19,
        1:38,二基地（自然口）,26/31,补探机
        2:05,二水晶,30/34,
        3:10,暮光议会,36/44,
        4:00,机械台,46/60,
        5:20,补门到7门,60/80,
        6:50,插前哨水晶,74/106,
        """
    )
    tmp = tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8", suffix=".csv")
    tmp.write(sample)
    tmp.flush()
    return Path(tmp.name)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="不启动 GUI 的时间轴播报冒烟脚本",
    )
    parser.add_argument("--file", type=Path, help="CSV/TXT 时间轴文件（默认使用示例）。")
    parser.add_argument("--tick", type=int, default=1000, help="计时步长（毫秒）。")
    parser.add_argument("--lead", type=int, default=2000, help="提前播报毫秒。")
    parser.add_argument("--duration", type=int, help="模拟总时长（毫秒）。")
    parser.add_argument("--early", action="store_true", help="开启提前播报判定。")
    parser.add_argument(
        "--no-on-time",
        dest="on_time",
        action="store_false",
        help="关闭整点播报判定。",
    )
    parser.set_defaults(on_time=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    csv_path = args.file or write_sample_csv()
    try:
        events = load_events_from_csv(csv_path)
        run_simulation(
            events=events,
            tick_ms=max(10, args.tick),
            lead_ms=max(0, args.lead),
            duration_ms=args.duration,
            on_time=args.on_time,
            early=args.early,
        )
    finally:
        if args.file is None and csv_path.exists():
            csv_path.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
