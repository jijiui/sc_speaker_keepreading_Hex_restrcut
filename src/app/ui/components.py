"""Reusable Qt components for the PvZ timeline speaker UI."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from PyQt6 import QtCore, QtGui, QtWidgets

if TYPE_CHECKING:  # pragma: no cover
    from typing import Any as MainWindow


@dataclass
class LeftPanelWidgets:
    widget: QtWidgets.QWidget
    clock_label: QtWidgets.QLabel
    flow_list: QtWidgets.QListWidget
    start_btn: QtWidgets.QPushButton
    pause_btn: QtWidgets.QPushButton
    reset_btn: QtWidgets.QPushButton
    top_checkbox: QtWidgets.QCheckBox
    auto_checkbox: QtWidgets.QCheckBox
    roi_edit: QtWidgets.QLineEdit
    roi_button: QtWidgets.QPushButton
    ocr_label: QtWidgets.QLabel
    lead_spin: QtWidgets.QDoubleSpinBox
    on_time_checkbox: QtWidgets.QCheckBox
    early_checkbox: QtWidgets.QCheckBox
    status_label: QtWidgets.QLabel


@dataclass
class MiniToolbarWidgets:
    widget: QtWidgets.QWidget
    countdown_label: QtWidgets.QLabel
    restore_button: QtWidgets.QToolButton
    close_button: QtWidgets.QToolButton
    size_grip: QtWidgets.QSizeGrip


@dataclass
class RightPanelWidgets:
    widget: QtWidgets.QWidget
    table: QtWidgets.QTableView


def build_left_panel(main: "MainWindow") -> LeftPanelWidgets:
    panel = QtWidgets.QWidget(main)
    layout = QtWidgets.QVBoxLayout(panel)
    layout.setContentsMargins(8, 8, 8, 8)
    layout.setSpacing(6)

    clock_font = QtGui.QFont()
    clock_font.setPointSize(26)
    clock_font.setBold(True)
    clock_label = QtWidgets.QLabel("0:00")
    clock_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)
    clock_label.setFont(clock_font)
    layout.addWidget(clock_label)

    open_btn = QtWidgets.QPushButton("打开时间轴文件（CSV/TXT/Excel）")
    open_btn.clicked.connect(main.open_file)  # type: ignore[arg-type]
    layout.addWidget(open_btn)

    flow_list = QtWidgets.QListWidget()
    flow_list.itemDoubleClicked.connect(main.on_flow_double_clicked)  # type: ignore[arg-type]
    layout.addWidget(flow_list, 1)

    controls = QtWidgets.QHBoxLayout()
    start_btn = QtWidgets.QPushButton("开始")
    start_btn.clicked.connect(main.start)  # type: ignore[arg-type]
    pause_btn = QtWidgets.QPushButton("暂停")
    pause_btn.clicked.connect(main.pause)  # type: ignore[arg-type]
    reset_btn = QtWidgets.QPushButton("重置")
    reset_btn.clicked.connect(main.reset)  # type: ignore[arg-type]
    for btn in (start_btn, pause_btn, reset_btn):
        controls.addWidget(btn)
    top_checkbox = QtWidgets.QCheckBox("置顶")
    top_checkbox.setToolTip("窗口始终置顶（快捷键: T）")
    top_checkbox.toggled.connect(main._sync_on_top_from_checkbox)  # type: ignore[attr-defined]
    controls.addWidget(top_checkbox)
    layout.addLayout(controls)

    ocr_row1 = QtWidgets.QHBoxLayout()
    auto_checkbox = QtWidgets.QCheckBox("自动计时")
    ocr_row1.addWidget(auto_checkbox)
    ocr_row1.addWidget(QtWidgets.QLabel("检测到游戏时间："))
    ocr_label = QtWidgets.QLabel("-")
    ocr_label.setMinimumWidth(80)
    ocr_row1.addWidget(ocr_label, 1)
    layout.addLayout(ocr_row1)

    ocr_row2 = QtWidgets.QHBoxLayout()
    roi_edit = QtWidgets.QLineEdit()
    roi_edit.setPlaceholderText("x,y,w,h")
    roi_button = QtWidgets.QPushButton("框选区域")
    ocr_row2.addWidget(roi_edit, 1)
    ocr_row2.addWidget(roi_button)
    layout.addLayout(ocr_row2)

    lead_layout = QtWidgets.QHBoxLayout()
    lead_layout.addWidget(QtWidgets.QLabel("提前播报（秒）："))
    lead_spin = QtWidgets.QDoubleSpinBox()
    lead_spin.setRange(0.0, 30.0)
    lead_spin.setDecimals(1)
    lead_spin.setSingleStep(0.5)
    lead_layout.addWidget(lead_spin)
    on_time_checkbox = QtWidgets.QCheckBox("整点播报")
    on_time_checkbox.setChecked(True)
    lead_layout.addWidget(on_time_checkbox)
    early_checkbox = QtWidgets.QCheckBox("提前播报")
    lead_layout.addWidget(early_checkbox)
    layout.addLayout(lead_layout)

    status_label = QtWidgets.QLabel("未加载时间轴")
    layout.addWidget(status_label)

    roi_button.clicked.connect(lambda: main.ocr_agent.select_roi(main) if getattr(main, "ocr_agent", None) else None)  # type: ignore[arg-type]

    return LeftPanelWidgets(
        widget=panel,
        clock_label=clock_label,
        flow_list=flow_list,
        start_btn=start_btn,
        pause_btn=pause_btn,
        reset_btn=reset_btn,
        top_checkbox=top_checkbox,
        auto_checkbox=auto_checkbox,
        roi_edit=roi_edit,
        roi_button=roi_button,
        ocr_label=ocr_label,
        lead_spin=lead_spin,
        on_time_checkbox=on_time_checkbox,
        early_checkbox=early_checkbox,
        status_label=status_label,
    )


def build_mini_toolbar(main: "MainWindow") -> MiniToolbarWidgets:
    toolbar = QtWidgets.QWidget(main)
    mini_layout = QtWidgets.QHBoxLayout(toolbar)
    mini_layout.setContentsMargins(0, 0, 0, 0)
    mini_layout.setSpacing(4)
    countdown_label = QtWidgets.QLabel("--")
    mini_layout.addWidget(countdown_label)
    mini_layout.addStretch()
    restore_button = QtWidgets.QToolButton()
    restore_button.setText("恢复")
    restore_button.setAutoRaise(True)
    restore_button.clicked.connect(lambda: main.act_mini.setChecked(False))  # type: ignore[arg-type]
    mini_layout.addWidget(restore_button)
    close_button = QtWidgets.QToolButton()
    close_button.setText("关闭")
    close_button.setAutoRaise(True)
    close_button.clicked.connect(main.close)  # type: ignore[arg-type]
    mini_layout.addWidget(close_button)
    size_grip = QtWidgets.QSizeGrip(toolbar)
    mini_layout.addWidget(size_grip, 0, QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignBottom)
    toolbar.hide()
    return MiniToolbarWidgets(toolbar, countdown_label, restore_button, close_button, size_grip)


def build_right_panel(main: "MainWindow", mini_toolbar: QtWidgets.QWidget) -> RightPanelWidgets:
    panel = QtWidgets.QWidget(main)
    layout = QtWidgets.QVBoxLayout(panel)
    layout.setContentsMargins(8, 8, 8, 8)
    layout.setSpacing(6)
    layout.addWidget(mini_toolbar)
    table = QtWidgets.QTableView()
    table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
    table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
    table.horizontalHeader().setStretchLastSection(True)
    table.verticalHeader().setVisible(False)
    layout.addWidget(table, 1)
    return RightPanelWidgets(panel, table)
