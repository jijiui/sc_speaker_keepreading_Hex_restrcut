"""Reusable UI command helpers (file dialogs, window toggles, etc.)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from PyQt6 import QtWidgets, QtCore

SAMPLE_CSV_CONTENT = (
    "人口,时间,动作,备注\n"
    "14/15,0:17,一水晶,\n"
    "16/19,0:38,网关,\n"
    "18/23,0:44,一气,\n"
    "26/31,1:38,二基地（自然口）,补探机\n"
    "28/31,1:50,核心,\n"
    "30/34,2:05,二水晶,\n"
    "34/42,2:40,折跃门研究,\n"
    "36/44,3:10,暮光议会,\n"
    "40/52,3:25,熔炉（+1攻）,排队升级\n"
    "46/60,4:00,机械台,\n"
    "48/64,4:10,研究冲锋,\n"
    "50/66,4:15,研究+1攻,\n"
    "54/72,5:00,圣堂武士档案馆,\n"
    "56/74,5:05,棱镜,\n"
    "60/80,5:20,补门到7门,\n"
    "66/90,5:50,补门到10门,\n"
    "68/92,6:05,停探机至66–68,\n"
    "70/100,6:10,全门刷狂热者,\n"
    "74/106,6:50,插前哨水晶,\n"
    "82/114,7:20,撞三矿开团,\n"
)


@dataclass
class FileActions:
    open_timeline: Callable[[], None]
    export_sample: Callable[[], None]


def build_file_actions(
    parent: QtWidgets.QWidget,
    load_callback: Callable[[Path], None],
) -> FileActions:
    """Create commands for opening timelines and exporting CSV samples."""

    def open_timeline() -> None:
        path_str, _ = QtWidgets.QFileDialog.getOpenFileName(
            parent,
            "选择时间轴文件",
            filter="时间轴文件 (*.csv *.txt *.xlsx *.xls);;所有文件 (*.*)",
        )
        if not path_str:
            return
        load_callback(Path(path_str))

    def export_sample() -> None:
        path_str, _ = QtWidgets.QFileDialog.getSaveFileName(
            parent,
            "导出示例 CSV",
            filter="CSV 文件 (*.csv)",
        )
        if not path_str:
            return
        path = Path(path_str)
        try:
            path.write_text(SAMPLE_CSV_CONTENT, encoding="utf-8")
            QtWidgets.QMessageBox.information(parent, "已导出", f"示例 CSV 已保存至：\n{path}")
        except Exception as exc:
            QtWidgets.QMessageBox.critical(parent, "保存失败", f"无法保存：\n{exc}")

    return FileActions(open_timeline=open_timeline, export_sample=export_sample)


def toggle_always_on_top(window: QtWidgets.QMainWindow, enabled: bool) -> None:
    """Apply the always-on-top flag."""
    window.setWindowFlag(QtCore.Qt.WindowType.WindowStaysOnTopHint, enabled)
    window.setWindowFlags(window.windowFlags())
    window.show()
