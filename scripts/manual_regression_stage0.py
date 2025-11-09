#!/usr/bin/env python3
"""
Stage‑0 manual regression harness for PvZ timeline speaker.

The script exercises UC-01 ~ UC-07 without showing the GUI window.
It prints a JSON array describing the outcome of each use case so the
results can be attached to the refactor log.
"""

from __future__ import annotations

import json
import tempfile
import textwrap
import time
from dataclasses import dataclass
from importlib.machinery import SourceFileLoader
from pathlib import Path
from typing import Any, Dict, List, Tuple

from PyQt6 import QtCore, QtWidgets

ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "pv_z_时间轴播报器（python_py_qt_6_）.py"
OCR_AGENT_PATH = ROOT / "opencv_timer_agent.py"

import sys

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@dataclass
class UCResult:
    uc: str
    status: str
    detail: str

    def to_dict(self) -> Dict[str, str]:
        return {"uc": self.uc, "status": self.status, "detail": self.detail}


def _load_app_module():
    return SourceFileLoader("pvz_app_reg", str(APP_PATH)).load_module()


def _ensure_app() -> QtWidgets.QApplication:
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    return app


def _run_uc01(window, csv_path: Path) -> Tuple[UCResult, List[Any]]:
    events = window._read_csv_like(csv_path)
    flows = window._read_flows_from_file(csv_path)
    if events and len(flows) == 1:
        detail = f"加载 {csv_path.name} 成功：{len(events)} 条事件"
        return UCResult("UC-01", "PASS", detail), events
    detail = f"未能从 {csv_path} 解析流程"
    return UCResult("UC-01", "FAIL", detail), events


def _run_uc02(window, xlsx_path: Path) -> UCResult:
    try:
        flows = window._read_flows_from_file(xlsx_path)
        if len(flows) >= 2 and all(len(evs) for evs in flows.values()):
            return UCResult(
                "UC-02",
                "PASS",
                f"载入 {len(flows)} 个 Sheet：{', '.join(flows.keys())}",
            )
        return UCResult("UC-02", "FAIL", "未能从 Excel 提取多流程")
    except Exception as exc:  # pragma: no cover - surfaced to log
        return UCResult("UC-02", "BLOCKED", f"Excel 读取失败：{exc}")


def _run_uc03(window, events: List[Any]) -> UCResult:
    window.timeline.set_flows({"冒烟流程": events})
    window._set_active_flow("冒烟流程")
    window.start()
    start_ok = window.timeline.running and window.timer.isActive()
    window.pause()
    pause_ok = (not window.timeline.running) and (not window.timer.isActive())
    window.timeline.prime_elapsed(1234)
    window.reset()
    reset_ok = window.timeline.elapsed_ms == 0 and window.status_lbl.text() == "已重置"
    if start_ok and pause_ok and reset_ok:
        return UCResult("UC-03", "PASS", "开始/暂停/重置状态切换正常")
    return UCResult(
        "UC-03",
        "FAIL",
        f"start={start_ok}, pause={pause_ok}, reset={reset_ok}",
    )


def _run_uc04() -> UCResult:
    agent_mod = SourceFileLoader("ocr_agent_reg", str(OCR_AGENT_PATH)).load_module()
    has_cv = getattr(agent_mod, "_HAS_CV", False)
    agent = agent_mod.OcrTimerAgent()
    roi = agent_mod.Roi(0, 0, 120, 50)
    agent.set_roi(roi)
    agent.set_enabled(True)
    if has_cv and agent.is_enabled():
        agent.set_enabled(False)
        return UCResult("UC-04", "PASS", "OCR Agent 可开启并监听 ROI")
    agent.set_enabled(False)
    return UCResult(
        "UC-04",
        "BLOCKED",
        "OpenCV/NumPy 未就绪，无法启用 OCR 自动计时",
    )


def _run_uc05(window) -> UCResult:
    before = window.tts._queue.qsize()
    window._speak("测试播报：确认播报线程可用")
    QtCore.QCoreApplication.processEvents()
    time.sleep(0.2)
    QtCore.QCoreApplication.processEvents()
    after = window.tts._queue.qsize()
    if after <= before:
        return UCResult("UC-05", "PASS", "队列入队并被 TTS 线程消费")
    return UCResult("UC-05", "FAIL", "播报队列未被清空")


def _run_uc06(window, export_path: Path) -> UCResult:
    original_getter = QtWidgets.QFileDialog.getSaveFileName

    def _fake_getter(*args, **kwargs):
        return str(export_path), "CSV 文件 (*.csv)"

    QtWidgets.QFileDialog.getSaveFileName = staticmethod(_fake_getter)
    try:
        window.export_sample_csv()
    finally:
        QtWidgets.QFileDialog.getSaveFileName = original_getter
    if export_path.exists() and "人口" in export_path.read_text(encoding="utf-8"):
        return UCResult("UC-06", "PASS", f"示例 CSV 已写入 {export_path}")
    return UCResult("UC-06", "FAIL", "示例 CSV 未生成")


def _run_uc07(window) -> UCResult:
    window._apply_always_on_top(True)
    flag_on = bool(
        window.windowFlags() & QtCore.Qt.WindowType.WindowStaysOnTopHint
    )
    window._apply_always_on_top(False)
    flag_off = not (
        window.windowFlags() & QtCore.Qt.WindowType.WindowStaysOnTopHint
    )
    window.act_mini.setChecked(True)
    mini_on = window._mini_mode
    window.act_mini.setChecked(False)
    mini_off = not window._mini_mode
    if flag_on and flag_off and mini_on and mini_off:
        return UCResult("UC-07", "PASS", "置顶/迷你模式切换生效")
    return UCResult(
        "UC-07",
        "FAIL",
        f"top=({flag_on},{flag_off}), mini=({mini_on},{mini_off})",
    )


def _prepare_csv(path: Path) -> None:
    data = textwrap.dedent(
        """\
        时间,动作,人口,备注
        0:10,侦查探机,14/15,开局
        0:30,补水晶,16/19,
        1:00,折跃门,20/23,保持经济
        """
    )
    path.write_text(data, encoding="utf-8")


def _prepare_xlsx(path: Path) -> None:
    import pandas as pd

    df_a = pd.DataFrame(
        {
            "时间": ["0:15", "0:40"],
            "动作": ["一水晶", "二水晶"],
            "人口": ["14/15", "18/23"],
        }
    )
    df_b = pd.DataFrame(
        {
            "时间": ["1:10", "1:50"],
            "动作": ["攻击准备", "推进"],
        }
    )
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        df_a.to_excel(writer, sheet_name="FlowA", index=False)
        df_b.to_excel(writer, sheet_name="FlowB", index=False)


def main() -> None:
    app = _ensure_app()
    mod = _load_app_module()
    window = mod.MainWindow()
    window.hide()
    results: List[UCResult] = []
    tmp_dir = Path(tempfile.mkdtemp(prefix="pvz_stage0_"))

    try:
        csv_path = tmp_dir / "uc01.csv"
        _prepare_csv(csv_path)
        uc1, events = _run_uc01(window, csv_path)
        results.append(uc1)

        xlsx_path = tmp_dir / "uc02.xlsx"
        _prepare_xlsx(xlsx_path)
        results.append(_run_uc02(window, xlsx_path))

        if events:
            results.append(_run_uc03(window, events))
        else:
            results.append(UCResult("UC-03", "BLOCKED", "UC-01 未返回事件"))

        results.append(_run_uc04())
        results.append(_run_uc05(window))

        export_path = tmp_dir / "sample.csv"
        results.append(_run_uc06(window, export_path))

        results.append(_run_uc07(window))
    finally:
        try:
            window.tts.stop()
        except Exception:
            pass
        window.close()
        app.quit()

    payload = json.dumps([r.to_dict() for r in results], ensure_ascii=False, indent=2)
    sys.stdout.buffer.write(payload.encode("utf-8"))
    sys.stdout.buffer.write(b"\n")


if __name__ == "__main__":
    main()
