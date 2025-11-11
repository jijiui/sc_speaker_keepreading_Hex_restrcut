"""Signal-binding helpers to keep MainWindow wiring centralized."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Optional

from PyQt6 import QtCore, QtGui, QtWidgets

from app.ui.components import LeftPanelWidgets, MiniToolbarWidgets


@dataclass
class LeftPanelCallbacks:
    on_open_file: Callable[[], None]
    on_flow_double_clicked: Callable[[QtWidgets.QListWidgetItem], None]
    on_start: Callable[[], None]
    on_pause: Callable[[], None]
    on_reset: Callable[[], None]
    on_reset_cleanup: Optional[Callable[[], None]] = None
    on_controls_changed: Optional[Callable[[], None]] = None
    on_top_toggled: Optional[Callable[[bool], None]] = None
    on_auto_toggled: Optional[Callable[[bool], None]] = None
    on_roi_button: Optional[Callable[[], None]] = None


@dataclass
class MiniToolbarCallbacks:
    on_restore: Callable[[], None]
    on_close: Callable[[], None]


@dataclass
class ShortcutCallbacks:
    toggle_run: Callable[[], None]
    reset: Callable[[], None]
    open_file: Callable[[], None]
    toggle_always_on_top: Callable[[], None]
    exit_mini: Callable[[], None]


@dataclass
class MenuCallbacks:
    open_file: Callable[[], None]
    export_sample: Callable[[], None]
    quit_app: Callable[[], None]
    toggle_mini_mode: Callable[[bool], None]
    toggle_left_panel: Callable[[bool], None]
    toggle_on_top: Callable[[bool], None]


@dataclass
class MenuActions:
    open_file: QtGui.QAction
    export_sample: QtGui.QAction
    quit_app: QtGui.QAction
    mini_mode: QtGui.QAction
    toggle_left_panel: QtGui.QAction
    toggle_on_top: QtGui.QAction


def bind_left_panel(widgets: LeftPanelWidgets, callbacks: LeftPanelCallbacks) -> None:
    """Connect left-panel widgets to business callbacks."""

    widgets.open_button.clicked.connect(callbacks.on_open_file)
    widgets.flow_list.itemDoubleClicked.connect(callbacks.on_flow_double_clicked)

    widgets.start_btn.clicked.connect(callbacks.on_start)
    if callbacks.on_controls_changed:
        widgets.start_btn.clicked.connect(lambda: QtCore.QTimer.singleShot(0, callbacks.on_controls_changed))

    widgets.pause_btn.clicked.connect(callbacks.on_pause)
    if callbacks.on_controls_changed:
        widgets.pause_btn.clicked.connect(lambda: QtCore.QTimer.singleShot(0, callbacks.on_controls_changed))

    widgets.reset_btn.clicked.connect(callbacks.on_reset)
    if callbacks.on_controls_changed:
        widgets.reset_btn.clicked.connect(lambda: QtCore.QTimer.singleShot(0, callbacks.on_controls_changed))
    if callbacks.on_reset_cleanup:
        widgets.reset_btn.clicked.connect(callbacks.on_reset_cleanup)

    if callbacks.on_top_toggled:
        widgets.top_checkbox.toggled.connect(callbacks.on_top_toggled)
    if callbacks.on_auto_toggled:
        widgets.auto_checkbox.toggled.connect(callbacks.on_auto_toggled)
    if callbacks.on_roi_button:
        widgets.roi_button.clicked.connect(callbacks.on_roi_button)


def bind_mini_toolbar(widgets: MiniToolbarWidgets, callbacks: MiniToolbarCallbacks) -> None:
    """Wire up mini-toolbar buttons."""

    widgets.restore_button.clicked.connect(callbacks.on_restore)
    widgets.close_button.clicked.connect(callbacks.on_close)


def setup_shortcuts(window: QtWidgets.QWidget, callbacks: ShortcutCallbacks) -> List[QtGui.QShortcut]:
    """Create keyboard shortcuts and keep references for lifecycle management."""

    shortcuts = [
        QtGui.QShortcut(QtGui.QKeySequence("Space"), window, activated=callbacks.toggle_run),
        QtGui.QShortcut(QtGui.QKeySequence("R"), window, activated=callbacks.reset),
        QtGui.QShortcut(QtGui.QKeySequence("O"), window, activated=callbacks.open_file),
        QtGui.QShortcut(QtGui.QKeySequence("T"), window, activated=callbacks.toggle_always_on_top),
        QtGui.QShortcut(QtGui.QKeySequence("Esc"), window, activated=callbacks.exit_mini),
    ]
    return shortcuts


def setup_menus(
    window: QtWidgets.QMainWindow,
    top_checkbox: QtWidgets.QCheckBox,
    callbacks: MenuCallbacks,
) -> MenuActions:
    """Build the menu bar and return created actions."""

    bar = window.menuBar()
    file_menu = bar.addMenu("文件")

    act_open = QtGui.QAction("打开…", window)
    act_open.triggered.connect(callbacks.open_file)
    file_menu.addAction(act_open)

    act_sample = QtGui.QAction("导出示例 CSV…", window)
    act_sample.triggered.connect(callbacks.export_sample)
    file_menu.addAction(act_sample)

    act_quit = QtGui.QAction("退出", window)
    act_quit.triggered.connect(callbacks.quit_app)
    file_menu.addAction(act_quit)

    view_menu = bar.addMenu("视图")
    act_mini = QtGui.QAction("极简小窗模式", window, checkable=True)
    act_mini.toggled.connect(callbacks.toggle_mini_mode)
    view_menu.addAction(act_mini)

    view_menu.addSeparator()
    act_toggle_left = QtGui.QAction("显示左侧控制区", window, checkable=True, checked=True)
    act_toggle_left.toggled.connect(callbacks.toggle_left_panel)
    view_menu.addAction(act_toggle_left)

    act_top = QtGui.QAction("窗口置顶", window, checkable=True)
    act_top.toggled.connect(callbacks.toggle_on_top)
    act_top.toggled.connect(top_checkbox.setChecked)
    view_menu.addAction(act_top)

    return MenuActions(
        open_file=act_open,
        export_sample=act_sample,
        quit_app=act_quit,
        mini_mode=act_mini,
        toggle_left_panel=act_toggle_left,
        toggle_on_top=act_top,
    )
